"""Structured output contracts between model and backend. The JSON schema is passed to the provider
(Ollama enforces it with a grammar); the Pydantic models validate what comes back."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BeliefUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    topic: str = Field(max_length=120)
    statement: str = Field(max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ProposedHypothesis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(default="", max_length=200)
    statement: str = Field(default="", max_length=800)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class OutgoingMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    to: str = Field(default="nearby", max_length=40)
    text: str = Field(default="", max_length=400)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: ProposedAction
    rationale: str = Field(default="", max_length=600)
    belief_updates: list[BeliefUpdate] = Field(default_factory=list, alias="beliefUpdates")
    message: OutgoingMessage | None = None
    hypothesis: ProposedHypothesis | None = None


class Reflection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str = Field(max_length=300)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)


class ReflectionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reflections: list[Reflection] = Field(default_factory=list)
    belief_updates: list[BeliefUpdate] = Field(default_factory=list, alias="beliefUpdates")
    hypothesis: ProposedHypothesis | None = None


def _belief_updates_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "maxItems": 3,
        "items": {
            "type": "object",
            "properties": {"topic": {"type": "string"}, "statement": {"type": "string"}, "confidence": {"type": "number"}},
            "required": ["topic", "statement", "confidence"],
        },
    }


def _hypothesis_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"title": {"type": "string"}, "statement": {"type": "string"}, "confidence": {"type": "number"}},
        "required": ["title", "statement", "confidence"],
    }


def decision_schema(action_types: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "object",
                "properties": {"type": {"type": "string", "enum": sorted(action_types) or ["rest"]}, "params": {"type": "object"}},
                "required": ["type", "params"],
            },
            "rationale": {"type": "string"},
            "beliefUpdates": _belief_updates_schema(),
            "message": {"type": "object", "properties": {"to": {"type": "string"}, "text": {"type": "string"}}, "required": ["to", "text"]},
            "hypothesis": _hypothesis_schema(),
        },
        "required": ["action", "rationale", "beliefUpdates"],
    }


def reflection_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reflections": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {"summary": {"type": "string"}, "salience": {"type": "number"}}, "required": ["summary", "salience"]}},
            "beliefUpdates": _belief_updates_schema(),
            "hypothesis": _hypothesis_schema(),
        },
        "required": ["reflections", "beliefUpdates"],
    }
