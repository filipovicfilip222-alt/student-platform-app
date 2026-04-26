"""Push subscriptions tabela (Web Push, KORAK 1 Prompta 2 / PRD §5.3).

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-27

Per-uređaj zapis o Web Push pretplati. Browser ``PushManager.subscribe()``
vraća JSON sa 3 polja (``endpoint``, ``keys.p256dh``, ``keys.auth``);
ovde ih čuvamo zajedno sa ``user_id`` i opcionim ``user_agent``-om za
debug.

Tabela koju kreira ova migracija:

  ``push_subscriptions``:
    - ``id``           UUID PK (server default ``gen_random_uuid()``)
    - ``user_id``      UUID FK → users.id, ON DELETE CASCADE
    - ``endpoint``     TEXT (URL do push servisa, ~250-700 karaktera)
    - ``p256dh_key``   VARCHAR(255) (base64-url ECDH javni ključ)
    - ``auth_key``     VARCHAR(255) (base64-url auth secret)
    - ``user_agent``   TEXT NULL (browser/OS string za debug)
    - ``created_at``   TIMESTAMP WITH TIME ZONE (server default ``now()``)
    - ``last_used_at`` TIMESTAMP WITH TIME ZONE (server default ``now()``)
    - ``UNIQUE (user_id, endpoint)`` — UPSERT target

Zašto ``UNIQUE (user_id, endpoint)`` umesto samo ``UNIQUE (endpoint)``:
  - Endpoint je teorijski globalno jedinstven (push servisi ga generišu),
    ali oslanjati se na to bi otvaralo cross-account leakage rizik ako
    bi 2 korisnika nekako delila isti endpoint (npr. shared device sa
    klonom browser profila).
  - UPSERT pattern u ``push_service.subscribe`` koristi ovaj par kao
    on-conflict target.

Zašto ``ON DELETE CASCADE`` umesto SET NULL ili RESTRICT:
  - Push pretplata bez user-a je smeće. CASCADE je čistiji od TTL-a.
  - Razlika u odnosu na ``broadcasts.admin_id`` (RESTRICT zbog audit
    trail-a): ovde nema audit zahteva — push subscribe je per-user
    self-service akcija (vidi: notification mark_read pattern).

Zašto ``last_used_at`` polje:
  - 410 Gone cleanup u ``push_service.send_push`` može da bude lazy:
    umesto da odmah brišemo subscription posle prve 410 greške, pratimo
    ``last_used_at`` da bismo posle 30 dana nekorišćenja mogli da pokrenemo
    sweep zadatak (Prompt 3 polish, ne za V1).
  - Za V1: 410 odgovor → odmah delete; ``last_used_at`` se ažurira na
    svako uspešno slanje (debug signal kada otkriva da li push uopšte
    radi za nekog korisnika).

Indeksi (samo jedan extra pored UNIQUE):
  - ``ix_push_subscriptions_user_id`` (B-tree) — fan-out query u
    ``send_push`` filtrira po ``user_id``; UNIQUE compound indeks
    je takođe ovde upotrebljiv kao prefix scan, ali eksplicitan
    indeks osigurava plan stabilnost na manjim tabelama (PG planer
    može preferirati Sequential Scan na <1000 redova).

Downgrade:
  - Briše indeks → briše tabelu. Bez složenih cleanup-ova jer tabela
    nema ništa što bi se referenciralo iz drugih tabela.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh_key", sa.String(length=255), nullable=False),
        sa.Column("auth_key", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "endpoint", name="uq_push_subscriptions_user_endpoint"
        ),
    )
    op.create_index(
        "ix_push_subscriptions_user_id",
        "push_subscriptions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_push_subscriptions_user_id", table_name="push_subscriptions"
    )
    op.drop_table("push_subscriptions")
