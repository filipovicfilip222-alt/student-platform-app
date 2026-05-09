-- seed_subjects_demo.sql — Brzi seed za delegate flow demo (Faza V1).
--
-- Tabela `subjects` i M:N `subject_assistants` postoje od inicijalne
-- migracije, ali ne postoji UI/endpoint za upravljanje predmetima
-- (CRUD je out-of-scope za V1). Bez bar jednog reda u `subjects`,
-- `professor_portal_service.list_assistants` vraća praznu listu i
-- `<RequestDelegateDialog>` se renderuje sa "Nemate asistenta za delegiranje".
--
-- Ova skripta kreira 3 demo predmeta i povezuje ih sa postojećim
-- profesorima i asistentima na FON-u tako da delegate flow ima šta da
-- pokaže. Idempotent je: koristi (code) UNIQUE constraint pa ponovno
-- pokretanje ne pravi duplikate.
--
-- Pokretanje:
--   docker exec -i studentska_postgres psql -U studentska \
--     -d studentska_platforma < backend/scripts/seed_subjects_demo.sql
--
-- ETF profesor (profesor1@etf.bg.ac.rs) ostaje bez predmeta jer u
-- bazi trenutno nema nijednog ETF asistenta da se poveže — delegate
-- flow za njega i dalje će biti prazan dok se ne kreira ETF asistent.

BEGIN;

-- ── Predmeti za profesor1@fon.bg.ac.rs ─────────────────────────────────────
INSERT INTO subjects (id, name, code, faculty, professor_id)
VALUES (
  gen_random_uuid(),
  'Baze podataka',
  'FON-BP-2026',
  'FON',
  '5fa5a7f7-a180-4c40-95a4-c0da6fe7a8f8'
)
ON CONFLICT (code) DO NOTHING;

INSERT INTO subjects (id, name, code, faculty, professor_id)
VALUES (
  gen_random_uuid(),
  'Operativni sistemi',
  'FON-OS-2026',
  'FON',
  '5fa5a7f7-a180-4c40-95a4-c0da6fe7a8f8'
)
ON CONFLICT (code) DO NOTHING;

-- ── Predmet za profesor2@fon.bg.ac.rs ──────────────────────────────────────
INSERT INTO subjects (id, name, code, faculty, professor_id)
VALUES (
  gen_random_uuid(),
  'Programiranje 1',
  'FON-PR1-2026',
  'FON',
  '3a4cf287-9a09-45e7-adcf-4d80bcca56dd'
)
ON CONFLICT (code) DO NOTHING;

-- ── Asistenti dodeljeni predmetima (M:N) ───────────────────────────────────
-- Baze podataka → oba asistenta (asistent1, asistent12)
INSERT INTO subject_assistants (subject_id, assistant_id)
SELECT s.id, '73832fb6-42a9-4512-a659-8e9e4526a791'::uuid
FROM subjects s
WHERE s.code = 'FON-BP-2026'
ON CONFLICT DO NOTHING;

INSERT INTO subject_assistants (subject_id, assistant_id)
SELECT s.id, 'd4dee0be-677d-4458-8db6-f6da632763e0'::uuid
FROM subjects s
WHERE s.code = 'FON-BP-2026'
ON CONFLICT DO NOTHING;

-- Operativni sistemi → samo asistent1
INSERT INTO subject_assistants (subject_id, assistant_id)
SELECT s.id, '73832fb6-42a9-4512-a659-8e9e4526a791'::uuid
FROM subjects s
WHERE s.code = 'FON-OS-2026'
ON CONFLICT DO NOTHING;

-- Programiranje 1 → samo asistent12 (drugi profesor)
INSERT INTO subject_assistants (subject_id, assistant_id)
SELECT s.id, 'd4dee0be-677d-4458-8db6-f6da632763e0'::uuid
FROM subjects s
WHERE s.code = 'FON-PR1-2026'
ON CONFLICT DO NOTHING;

COMMIT;

-- ── Verifikacija (samo log) ───────────────────────────────────────────────
SELECT s.code, s.name, u.email AS prof_email,
       array_agg(au.email ORDER BY au.email) FILTER (WHERE au.email IS NOT NULL) AS assistants
FROM subjects s
JOIN professors p ON s.professor_id = p.id
JOIN users u ON p.user_id = u.id
LEFT JOIN subject_assistants sa ON sa.subject_id = s.id
LEFT JOIN users au ON sa.assistant_id = au.id
GROUP BY s.id, s.code, s.name, u.email
ORDER BY u.email, s.name;
