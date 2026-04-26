"""Unaccent + pg_trgm — diakritik-insensitive search nad srpskom latinicom.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-27

KORAK 10 iz CURSOR_PROMPT_1_BACKEND_COMPLETION.md.

Postavlja infrastrukturu za pretragu „Petrovic" → matchuje „Petrović",
„djordjevic" → matchuje „Đorđević", „vestacka" → matchuje „Veštačka
inteligencija". Pre ove migracije, ``search_service.search_professors``
i ``admin_user_service.list_users`` su radili plain ``ILIKE`` koji ne
hvata dijakritičke razlike — dokumentovano kao bug u CURRENT_STATE2 §3.1
punkt 2.

Šta migracija radi:
  1. Instalira ``unaccent`` ekstenziju (uklanja akcente iz teksta) i
     ``pg_trgm`` (trigram operator klase za GIN indekse).
  2. Definiše IMMUTABLE wrapper ``public.f_unaccent(text)``.
  3. Definiše IMMUTABLE wrapper ``public.f_unaccent_array(text[])``
     koji obavi ``array_to_string`` + ``f_unaccent`` u jednom potezu.
  4. Pravi 5 GIN trigram indeksa nad ``f_unaccent(...)`` izrazima.

Zašto ``f_unaccent`` wrapper a ne direktno ``unaccent()``:
  - PostgreSQL ``unaccent()`` je deklarisano kao ``STABLE``, ne
    ``IMMUTABLE`` (jer može da pročita rečnik koji se menja). Functional
    indeks zahteva IMMUTABLE izraz, pa se mora obmotati.
  - Eksplicitna ``public.unaccent('public.unaccent', ...)`` pozivna
    forma fiksira rečnik bez oslanjanja na ``search_path`` — bez ovog
    indeks bi vraćao pogrešne rezultate ako neko izmeni search_path
    između sesija.

Zašto ``replace(replace(...), ...)`` korak pre ``unaccent``:
  - Standardni ``unaccent`` rečnik mapira ``ć→c``, ``č→c``, ``š→s``,
    ``ž→z``, ali ``đ→d`` (NE ``đ→dj``). Bez extra koraka, „Đorđević"
    postaje „Dordevic", pa search „djordjevic" ne hvata.
  - Rešenje: pre ``unaccent`` poziva, eksplicitno mapiramo ``đ→dj`` i
    ``Đ→Dj``. Posle toga, ``unaccent`` skida sve ostale akcente.
  - Primer: „Đorđević" → ``replace`` → „Djordjević" → ``unaccent`` →
    „Djordjevic". Query „djordjevic" → no-op kroz wrapper → matchuje.
  - ``replace`` je IMMUTABLE PARALLEL SAFE, kompozicija ostaje
    IMMUTABLE.

Zašto GIN ``gin_trgm_ops`` indeksi a ne B-tree:
  - ``ILIKE '%q%'`` ima vodeći wildcard, što B-tree functional indeks
    NE može efikasno da iskoristi → uvek Sequential Scan.
  - Trigram GIN indeks razbija string na 3-gramove i pretražuje preko
    njih, što je subsecond čak i za 100K redova.
  - Acceptance kriterijum (CURSOR_PROMPT_1 §10) eksplicitno traži
    ``Bitmap Index Scan`` u ``EXPLAIN ANALYZE``-u — bez ``pg_trgm``-a
    bi pao bez obzira na veličinu tabele.

Zašto array_to_string za ``professors.areas_of_interest``:
  - Kolona je ``TEXT[]`` (3–7 oblasti po profesoru u praksi).
  - ``array_to_string(arr, ' ')`` daje plain string preko kog trigram
    radi normalno. Alternativa (GIN nad ``unnest``-om kroz lateral)
    je kompleksnija; za realne brojeve nema benefita.
  - PostgreSQL ``array_to_string`` je deklarisana kao ``STABLE``
    (ne IMMUTABLE), pa NE može direktno u functional indeks. Zato
    pravimo poseban ``f_unaccent_array(text[])`` IMMUTABLE wrapper
    koji ovaj poziv obmotava — ovo je standardan pattern (developer
    garantuje IMMUTABLE semantiku za TEXT[] input).

Downgrade:
  - Briše indekse → briše funkciju → briše ekstenzije.
  - ``DROP EXTENSION IF EXISTS unaccent`` se radi iako je ekstenzija
    bila pre-instalirana u dev kontejneru (van migracija): 0004 je
    prva formalna migracija koja je traži, pa je claim-ujemo. Posle
    downgrade-a + upgrade-a stanje je isto (``CREATE EXTENSION IF NOT
    EXISTS`` je idempotent).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Funkcionalni indeksi koje pravi/brise ova migracija ──────────────────────
#
# Lista (indeks_ime, tabela, izraz) — dupli put da bi upgrade i downgrade
# delili izvor istine. Svaki indeks koristi ``gin_trgm_ops`` operator
# klasu iz ``pg_trgm`` ekstenzije.

_FUNCTIONAL_INDEXES: tuple[tuple[str, str, str], ...] = (
    (
        "ix_users_first_name_unaccent_trgm",
        "users",
        "public.f_unaccent(first_name)",
    ),
    (
        "ix_users_last_name_unaccent_trgm",
        "users",
        "public.f_unaccent(last_name)",
    ),
    (
        "ix_professors_department_unaccent_trgm",
        "professors",
        "public.f_unaccent(department)",
    ),
    (
        "ix_professors_areas_unaccent_trgm",
        "professors",
        "public.f_unaccent_array(areas_of_interest)",
    ),
    (
        "ix_subjects_name_unaccent_trgm",
        "subjects",
        "public.f_unaccent(name)",
    ),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.f_unaccent(text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        STRICT
        AS $$
            SELECT public.unaccent(
                'public.unaccent',
                replace(replace($1, 'đ', 'dj'), 'Đ', 'Dj')
            )
        $$;
        """
    )

    # ``array_to_string`` je STABLE u PG-u, pa ne može direktno u functional
    # indeks. Obmotavamo ga u IMMUTABLE wrapper — semantika ostaje
    # deterministična jer TEXT[] → text konverzija nema lokalizacijskih
    # zavisnosti. NULL ulaz (prazan array tipa NULL) → vraća NULL, dok
    # ``ARRAY[]::text[]`` vraća prazan string (PG default ponašanje).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.f_unaccent_array(text[])
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        STRICT
        AS $$
            SELECT public.f_unaccent(array_to_string($1, ' '))
        $$;
        """
    )

    for index_name, table_name, expression in _FUNCTIONAL_INDEXES:
        op.execute(
            f"CREATE INDEX {index_name} ON {table_name} "
            f"USING gin ({expression} public.gin_trgm_ops)"
        )


def downgrade() -> None:
    for index_name, _table, _expr in _FUNCTIONAL_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

    op.execute("DROP FUNCTION IF EXISTS public.f_unaccent_array(text[])")
    op.execute("DROP FUNCTION IF EXISTS public.f_unaccent(text)")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
