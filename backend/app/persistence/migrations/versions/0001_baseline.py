"""baseline schema

Revision ID: 0001
Revises:
Create Date: 2026-11-02
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import op

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.persistence.models import Base  # noqa: E402

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The baseline is generated from the ORM metadata so that model and schema cannot drift at v1.
    # Later revisions must be written as explicit ALTERs.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
