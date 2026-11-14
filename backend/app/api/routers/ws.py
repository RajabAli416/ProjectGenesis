"""WebSocket live channel. Server → client frames follow the frontend's ServerMessage union:
hello, clock, snapshot, event, universe.changed. Client → server: {type: 'subscribe', universeIds}."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import orjson
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.version import ENGINE_VERSION

router = APIRouter()
log = logging.getLogger(__name__)


@router.websocket("/ws")
async def live(ws: WebSocket) -> None:
    host = ws.app.state.host
    await ws.accept()
    host.ws_clients += 1
    sub = host.bus.subscribe(universe_filter=None)
    try:
        await ws.send_text(orjson.dumps({"type": "hello", "engineVersion": ENGINE_VERSION}).decode())

        async def reader() -> None:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = orjson.loads(raw)
                except orjson.JSONDecodeError:
                    continue
                if isinstance(msg, dict) and msg.get("type") == "subscribe":
                    ids = msg.get("universeIds")
                    sub.universe_filter = set(ids) if isinstance(ids, list) else None

        async def writer() -> None:
            while True:
                msg = await sub.queue.get()
                await ws.send_text(orjson.dumps(msg).decode())

        reader_task = asyncio.create_task(reader())
        writer_task = asyncio.create_task(writer())
        done, pending = await asyncio.wait({reader_task, writer_task}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        for t in done:
            exc = t.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                log.debug("ws task ended: %s", exc)
    except WebSocketDisconnect:
        pass
    finally:
        host.bus.unsubscribe(sub)
        host.ws_clients -= 1
