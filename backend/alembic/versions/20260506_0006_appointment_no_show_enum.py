"""Add NO_SHOW value to appointmentstatus PG enum.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-06

Background:
    Initial migration `0001` kreirala je `appointmentstatus` PG enum sa
    pet vrednosti: PENDING, APPROVED, REJECTED, CANCELLED, COMPLETED.
    Python enum `app.models.enums.AppointmentStatus` je u međuvremenu
    dobio šestu vrednost — `NO_SHOW = "NO_SHOW"` — koju koristi
    `strike_tasks.detect_no_show` task za automatsko obeležavanje
    propuštenih termina (PRD §5.3 strike sistem).

    Bez ove migracije, svaki INSERT/UPDATE u `appointments.status` sa
    vrednošću `NO_SHOW` baca `InvalidTextRepresentation` na commit-u, a
    pošto `strike_service.add_strike` već flush-uje strike rekord i
    dispatch-uje `send_strike_added.delay()` PRE postavljanja
    `appointment.status = NO_SHOW`, dolazi do bizarne race-condition
    ponašanja: rollback briše strike rekord ali notifikacija je već u
    Redis broker-u → student dobija fantomske strike notifikacije a
    `strike_records` tabela ostaje prazna.

PostgreSQL caveat (PG 12+):
    `ALTER TYPE ... ADD VALUE` može da se izvrši unutar transakcije, ali
    novouvedena vrednost se ne sme koristiti u toj istoj transakciji
    (npr. INSERT/UPDATE sa novom vrednošću). Pošto ova migracija samo
    dodaje vrednost u enum (bez korišćenja iste), dovoljno je
    `op.execute(...)` u standardnom Alembic transakcionom režimu.
    `IF NOT EXISTS` čini operaciju idempotentnom — bezbedno za re-run.

Downgrade:
    PG ne podržava `ALTER TYPE ... DROP VALUE`. Da bismo „skinuli" ovu
    vrednost, morali bismo da kreiramo novi enum, migriramo sve kolone,
    drop-ujemo stari, rename-ujemo novi. To je destruktivno i traži
    backfill (svi `NO_SHOW` redovi bi morali da pređu u, npr.,
    `CANCELLED`). Pošto je NO_SHOW deo strike sistema koji se ne sme
    izgubiti (audit/poene), downgrade je `pass` — nije moguć bez
    eksplicitnog odbacivanja podataka, što ne sme biti deo automatskog
    Alembic koraka.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE appointmentstatus ADD VALUE IF NOT EXISTS 'NO_SHOW'")


def downgrade() -> None:
    # PG nema ALTER TYPE ... DROP VALUE. Vidi docstring — ručno bi se
    # tražio data-migration plan; za sada ostavljamo no-op da Alembic
    # downgrade ne pukne, ali enum vrednost ostaje u tipu.
    pass
