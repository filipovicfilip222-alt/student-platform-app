"""Broadcasts table — admin globalna obaveštenja (Faza 4.5).

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27

Tabela ``broadcasts`` čuva istoriju globalnih obaveštenja koje admin
šalje preko ``POST /api/v1/admin/broadcast``. Frontend hook
``useBroadcastHistory`` dohvata poslednjih N redova preko
``GET /api/v1/admin/broadcast`` (vidi ``frontend/lib/api/admin.ts``).

Šta NIJE u ovoj tabeli:
  - ``delivered_count`` — fan-out greške se loguju per-user u Celery
    worker logu, recipient_count je "ciljani" broj u trenutku dispatch-a
    (resolve-ovan SELECT-om PRE Celery task-a). Eventualni delivered
    metric se dodaje u Prompt 2 ako bude potrebno.
  - audit log entry — to ide u zasebnu ``audit_log`` tabelu (kolona
    ``action`` = ``BROADCAST_SENT``, samo činjenica + admin ip; bez
    title/body redundancije).

Zašto ``ON DELETE RESTRICT`` na ``admin_id``:
  - Ako bi bilo SET NULL, gubili bismo audit trag (ko je poslao broadcast).
  - U praksi: admin se ne briše dok god ima broadcast-ova; ako baš mora,
    prvo se obrišu broadcast-ovi (administrativna procedura).

Zašto ``VARCHAR(50)[]`` umesto ``TEXT[]``:
  - Eksplicitni limit (channels su mali enum-ovi, "IN_APP"/"EMAIL"; nema
    potrebe za neograničenom dužinom). Čistiji ``\\d broadcasts`` u psql-u.

Zašto NEMA ``CHECK constraint`` na ``target``/``faculty``:
  - Pydantic V2 (``BroadcastRequest``) već striktno validira na entry
    point-u. DB-level constraint bi udvostručio logiku i opao bi pri
    eventualnoj evoluciji enum-a (npr. dodavanje "BY_YEAR" target-a kad
    se ``enrollment_year`` kolona implementira) — radije se oslanjamo
    na servisni sloj.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("faculty", sa.String(length=10), nullable=True),
        sa.Column(
            "channels",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
        ),
        sa.Column("recipient_count", sa.Integer(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broadcasts_admin_id", "broadcasts", ["admin_id"])
    op.create_index(
        "ix_broadcasts_sent_at",
        "broadcasts",
        [sa.text("sent_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_broadcasts_sent_at", table_name="broadcasts")
    op.drop_index("ix_broadcasts_admin_id", table_name="broadcasts")
    op.drop_table("broadcasts")
