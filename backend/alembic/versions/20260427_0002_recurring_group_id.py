"""Recurring slots — recurring_group_id column

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27

Adds nullable UUID column ``recurring_group_id`` to ``availability_slots``
plus a partial B-tree index that only covers rows where the column is
NOT NULL.

Why a dedicated column and not a JSONB equality filter?
  - Two independently created series with the same RRULE payload would
    collide if grouped by JSONB equality + valid_from. With a UUID per
    series we guarantee a clean group identity for the "delete entire
    series" operation (ROADMAP §3.8 acceptance).
  - B-tree on UUID is cheap; partial WHERE NOT NULL keeps the index
    tiny since most slots are still single-shot.
  - JSONB equality is byte-level — the moment another client emits
    keys in a different order or includes explicit `null` fields the
    equality breaks. A UUID is deterministic.

The column is nullable: legacy rows (single-shot slots) stay NULL.
The partial index never indexes those rows, so its size scales only
with the number of recurring slots.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "availability_slots",
        sa.Column(
            "recurring_group_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_availability_slots_recurring_group_id",
        "availability_slots",
        ["recurring_group_id"],
        postgresql_where=sa.text("recurring_group_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_availability_slots_recurring_group_id",
        table_name="availability_slots",
    )
    op.drop_column("availability_slots", "recurring_group_id")
