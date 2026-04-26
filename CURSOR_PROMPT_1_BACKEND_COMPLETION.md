# CURSOR PROMPT 1 — Backend Completion (do pune funkcionalnosti postojećeg frontend-a)

> **Namena:** Ovaj prompt vodi Cursor (sa najjačim agentima) kroz **Fazu 3.3 → 5.1** backend-a Studentske Platforme. Cilj: **svaki 🟡 placeholder na frontendu postaje 🟢 (live)**. Ne diraj frontend osim ako ti to izričito tražim u nekom koraku — sve što je frontendu potrebno već je tu (axios klijenti, hooks, tipovi, UI), čeka samo backend.
>
> **Kako da radiš sa Cursor-om:** Prosleđuj jedan po jedan korak (npr. „uradi KORAK 1: 3.3 appointment detail + files"). Ne preskači korake. Posle svakog koraka pokreni acceptance testove iz tog koraka pre nego što pređeš na sledeći.

---

## 0. KONTEKST KOJI MORAŠ PROČITATI PRE PRVE LINIJE KODA

Pročitaj **redom** i drži otvorene u Cursor tabovima:

1. `CURRENT_STATE2.md` — autoritativno trenutno stanje (gde smo, šta radi, šta ne).
2. `CLAUDE.md` — pravila stack-a; **posebno sekcija 11 (zabranjena ponašanja)** i sekcija 6 (Redis Lua lock).
3. `docs/ROADMAP.md` — sekcija „Plan faza", od 3.3 do 5.1.
4. `docs/websocket-schema.md` — autoritativan WS ugovor (potreban za KORAK 3 i 4).
5. `docs/PRD_Studentska_Platforma.md` — poslovna pravila (max 20 chat poruka, 24h chat close, strike sistem, document requests tok).
6. **Pre svakog Pydantic šemo-pisanja:** otvori odgovarajući `frontend/types/*.ts` fajl i uparuj polja **red za red** (snake_case ostaje na obe strane). Ovo je u `CURRENT_STATE2.md §7`.
7. Pre svakog endpoint-a otvori odgovarajući `frontend/lib/api/*.ts` da vidiš **tačan URL, metod i query parametre** koje frontend već zove.

### Kritična pravila (kratka verzija — pre svakog koraka mentalno proveri)

- ❌ Nema `localStorage`/`sessionStorage` za tokene — ali ovo je backend; relevantno za WS auth (token se prima kao `Query(...)` param, ne header).
- ❌ Nema raw SQL — samo SQLAlchemy `select()`/ORM.
- ❌ Nema sync SQLAlchemy — sve `async def` + `AsyncSession`.
- ❌ Nema email iz endpoint funkcije — uvek `task.delay(...)`.
- ✅ Pydantic V2 — `model_config = {"from_attributes": True}` na svim Response šemama.
- ✅ UUID PK uvek.
- ✅ Pre commit-a: pokreni `alembic upgrade head` u kontejneru, otvori Swagger (`http://localhost/docs`) i ručno proveri novi endpoint.
- ✅ Commit format: `feat(backend): ...` / `fix(backend): ...`. PR ide na `dev`, nikad `main`.

### Workflow za svaki korak

1. Otvori odgovarajući frontend tip i API klijent → razumeš tačan ugovor.
2. Napiši Pydantic šemu uparenu sa tipom.
3. Napiši service metodu (sva business logika ide tu, **ne u router**).
4. Napiši router endpoint (thin layer — samo dependency, poziv service-a, return).
5. Ako ima izmene baze → Alembic migracija (`alembic revision --autogenerate -m "..."`, pa ručno proveri generisano).
6. Ako ima novi Celery task → registruj ga u `celery_app.py` autodiscover.
7. **Test ručno kroz Swagger** + (poželjno) integracioni `pytest-asyncio` test.
8. Commit + push.

---

## KORAK 1 — Faza 3.3: Appointment detail + files (MinIO presigned URL)

**Zašto prvo:** Odblokirava `/appointments/[id]` stranicu (trenutno polling fallback) i preduslov je za KORAK 3 (chat WS).

### 1.1 Pre koda — pročitaj

- `CURRENT_STATE2.md §4` (Sledeći korak — 3.3 detalji + acceptance).
- `frontend/types/appointment.ts` — **ovo je ugovor**. `AppointmentDetailResponse`, `ChatMessageResponse`, `FileResponse`, `ParticipantResponse` su zakucani.
- `frontend/lib/api/appointments.ts` — vidi tačne URL-ove i metode (`getDetail`, `listMessages`, `uploadFile`, `listFiles`, `deleteFile`, `confirmParticipant`, `declineParticipant`).
- `ROADMAP.md §3.3` — acceptance kriterijumi.

### 1.2 Lista fajlova koje pravi/menjaš

Pre nego što počneš, vrati mi (u Cursor chatu) **ovu listu sa kratkim opisom svakog fajla**. Tek posle moje potvrde piši kod.

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/schemas/appointment.py` | NEW | `AppointmentDetailResponse`, `ChatMessageResponse`, `ChatMessageCreate`, `FileResponse`, `ParticipantResponse`, `ParticipantConfirmResponse` — Pydantic V2, uparene sa `frontend/types/appointment.ts` |
| 2 | `backend/app/services/appointment_detail_service.py` | NEW | `get_detail()`, `list_messages()`, `confirm_participant()`, `decline_participant()` + RBAC (lead, participant, profesor, delegirani asistent) |
| 3 | `backend/app/services/file_service.py` | NEW | MinIO klijent (`minio` Python SDK), `upload()`, `presigned_get_url(ttl=3600)`, `delete()`, MIME whitelist + 5MB limit |
| 4 | `backend/app/api/v1/appointments.py` | NEW | `GET /{id}`, `GET /{id}/messages`, `POST /{id}/files` (multipart), `GET /{id}/files`, `DELETE /{id}/files/{file_id}`, `POST /{id}/participants/confirm`, `POST /{id}/participants/decline` |
| 5 | `backend/app/main.py` | EDIT | Odkomentariši `from app.api.v1 import appointments` i `app.include_router(appointments.router, ...)` |
| 6 | `backend/requirements.txt` | EDIT (ako fali) | `minio` SDK ako još nije tu |

### 1.3 Kritične detalje koje ne smeš zaboraviti

- **MIME whitelist** (PRD §2.2): `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `image/png`, `image/jpeg`, `application/zip`, `text/x-python`, `text/x-java-source`, `text/x-c++src`. Svi ostali → 422.
- **Max 5MB** → vraćaj 413, ne 422.
- **MinIO bucket:** `appointment-files` (već kreiran u `infra/minio/init-buckets.sh`).
- **Object key konvencija:** `{appointment_id}/{file_uuid}__{sanitized_filename}`.
- **RBAC za `GET /{id}`:** lead_student | participanti (preko `appointment_participants`) | profesor (vlasnik slot-a) | asistent (delegiran preko `subject_assistants`). Svi ostali → 403.
- **DELETE fajla:** samo uploader može.
- **`chat_open` flag u response-u:** `true` ako `slot_datetime + 24h > now`, inače `false` (PRD: chat se zatvara 24h posle).
- **`can_chat_until` polje:** `slot_datetime + 24h`.

### 1.4 Acceptance kriterijumi (ručno + automatski)

- [ ] Swagger prikazuje 7 novih endpoint-a pod „Appointments".
- [ ] Login kao student koji je lead → `GET /api/v1/appointments/{id}` vraća 200 sa svim poljima.
- [ ] Login kao student koji nije učesnik → 403.
- [ ] Upload `test.pdf` 1MB → 200 + presigned URL koji se može preuzeti u browseru.
- [ ] Upload `test.exe` → 422.
- [ ] Upload 6MB fajla → 413.
- [ ] DELETE od ne-uploader-a → 403.
- [ ] Frontend `/appointments/[id]` se otvara bez konzolnih grešaka i prikazuje fajlove (već postoji `<FileList>` i `<FileUploadZone>`).

**Procena:** 1.5–2 dana.

---

## KORAK 2 — Faza 3.8: Recurring slots ekspanzija

**Zašto sada:** Profesor portal endpoint `POST /api/v1/professors/slots` trenutno pravi 1 zapis čak i kada je `recurring_rule` prosleđeno. Frontend `<RecurringRuleModal />` već šalje pun JSON. Bez ovog koraka, kalendar prikazuje samo prvi termin serije.

### 2.1 Pre koda

- `ROADMAP.md §3.8`.
- `frontend/components/calendar/recurring-rule-modal.tsx` (videti šta tačno frontend šalje kao `recurring_rule`).
- `backend/app/services/availability_service.py::create_slot` (trenutno pravi 1 zapis).

### 2.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/schemas/professor.py` | EDIT | Dodaj `RecurringRule` Pydantic model: `freq: Literal["WEEKLY","MONTHLY"]`, `by_weekday: list[int]` (0=Mon..6=Sun), `count: int \| None`, `until: date \| None`. Stavi ga kao `SlotCreate.recurring_rule: RecurringRule \| None` |
| 2 | `backend/app/services/availability_service.py` | EDIT | `create_slot`: ako `recurring_rule is None` → trenutno ponašanje. Inače: parsiraj pravilo → generiši listu `slot_datetime`-ova → bulk insert N zapisa, svi sa **istim** `recurring_rule` JSONB i istim `recurring_group_id` (UUID, novi server-side default ili manualno generisan) |
| 3 | `backend/alembic/versions/20260427_0002_recurring_group_id.py` | NEW | `ALTER TABLE availability_slots ADD COLUMN recurring_group_id UUID NULL; CREATE INDEX ix_avail_recurring_group ON availability_slots(recurring_group_id)` |
| 4 | `backend/app/models/availability_slot.py` | EDIT | Dodaj `recurring_group_id: Mapped[UUID \| None]` |
| 5 | `backend/app/api/v1/professors.py` | EDIT | Dodaj `DELETE /slots/recurring/{recurring_group_id}` — briše sve **buduće** slotove iste grupe (filter `slot_datetime > now()`) i odbija ako neki ima APPROVED appointments |

### 2.3 Detalji ekspanzije

- **WEEKLY**: za svaki `weekday` u `by_weekday`, generiši slotove počev od `slot_datetime` do `until` (ili dok `count` ne istekne).
- **MONTHLY**: zadrži dan u mesecu od `slot_datetime` (npr. „svakog 5. u mesecu").
- **Sanity check:** ako bi se generisalo > 100 slotova → 422 sa porukom „prevelik raspon, smanji `count` ili `until`".
- **Konfliktna provera:** ne dozvoli da neki novi slot upadne u **postojeći** APPROVED appointment vremenski (overlap detect — već postoji helper u `availability_service`).

### 2.4 Acceptance

- [ ] POST `/professors/slots` sa `recurring_rule={freq:"WEEKLY", by_weekday:[1], count:8}` i `slot_datetime: 2026-05-05T10:00:00+02:00` → 8 zapisa u bazi, svi imaju isti `recurring_group_id`.
- [ ] GET `/professors/slots` vraća svih 8 (sortirano po datumu).
- [ ] DELETE `/professors/slots/recurring/{group_id}` → svi budući brišu se, prošli ostaju.
- [ ] Student `GET /students/professors/{id}/slots` normalno vraća svih 8 slobodnih.

**Procena:** 1 dan.

---

## KORAK 3 — Faza 4.1: WebSocket chat + Redis Pub/Sub

**Zašto sada:** Chat je već implementiran kroz polling (TicketChat komponenta). Frontend `lib/ws/chat-socket.ts` je spreman po `websocket-schema.md §5`. Posle ovog koraka frontend automatski prelazi sa polling-a na WS (samo prebaciš flag u `use-chat` hook-u).

### 3.1 Pre koda — pročitaj

- `docs/websocket-schema.md` **kompletno** — naročito §5 (chat), §2 (handshake), §3 (envelope), §2.3 (close kodovi).
- `frontend/types/ws.ts` — `WsEnvelope`, `ChatEvents`, `WS_CLOSE_CODES`.
- `frontend/lib/ws/chat-socket.ts` — vidi tačan format envelope-a koji frontend šalje i očekuje.

### 3.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/services/chat_service.py` | NEW | `send_message(db, redis, appointment_id, sender, content)`: RBAC, max 20 msg per appointment (PRD), 24h close check, persist u `ticket_chat_messages`, `await redis.publish(f"chat:pub:{appointment_id}", envelope_json)`. `list_messages(db, appointment_id, limit=20)`. `is_chat_closed(appointment)`. |
| 2 | `backend/app/api/v1/appointments.py` | EDIT (postojeći iz KORAKA 1) | Dodaj `@router.websocket("/{id}/chat")`. Tok: validate JWT (`Query(...)` token), RBAC, ako zatvoren → close(4430), ako 21. msg → close(4409). Subscribe na Redis `chat:pub:{id}`. Dva taska: receive_loop (klijent→server) i publish_loop (Redis→klijent). |
| 3 | `backend/app/core/ws_deps.py` | NEW | `decode_ws_token(token: str) -> User \| None` — helper koji parsira JWT iz query param-a i validira active flag. Koristiti i u KORAKU 4. |

### 3.3 Kritični detalji

- **Envelope format** mora biti **identičan** sa `frontend/types/ws.ts::WsEnvelope`:
  ```json
  { "event": "chat.message", "ts": "2026-04-26T...", "data": { "id": "...", "sender_id": "...", "sender_role": "STUDENT", "content": "...", "created_at": "..." } }
  ```
- **Close kodovi** (websocket-schema.md §2.3 — striktno):
  - 4401 invalid/expired JWT
  - 4403 RBAC fail (nije učesnik)
  - 4404 appointment ne postoji
  - 4409 limit poruka prebačen
  - 4430 chat zatvoren (24h posle)
- **Validacija samo pri handshake-u**, ne pri svakoj poruci (CLAUDE.md §12).
- **Idempotency:** ako Redis padne između `INSERT` i `PUBLISH` → poruka je u bazi, samo ne stiže live; klijent će je videti pri reconnect-u kroz `GET /messages`.
- **Heartbeat:** po `websocket-schema.md §3.1` + §7.1, server šalje `{ "event": "system.ping", ... }` **svakih 25s**; klijent odgovara `system.pong` (auto, isti `seq`). Ako 60s nema pong-a → close(1001). (Ovaj fajl je ranije pominjao 30s — schema je autoritativna; poravnano na 25s.)

### 3.4 Acceptance

- [ ] Otvori `/appointments/{id}` u dva browser-a (student + profesor) → poruka iz jednog stiže u drugi < 1s.
- [ ] 21. poruka → 4409 close + frontend toast „Limit od 20 poruka dostignut".
- [ ] 24h posle `slot_datetime` → connection attempt → 4430 close + `<ChatClosedNotice />` se prikazuje.
- [ ] Drugi user (ne učesnik) → 4403.
- [ ] U `frontend/lib/hooks/use-chat.ts` prebaci flag sa polling na WS i potvrdi da TicketChat radi bez izmene UI-a.

**Procena:** 1.5 dan.

---

## KORAK 4 — Faza 4.2: Notifications REST + WS stream

**Zašto sada:** `<NotificationCenter />` u top-baru trenutno pollinguje na 30s. Frontend `lib/ws/notification-socket.ts` već postoji. Posle ovog koraka bell counter postaje real-time.

### 4.1 Pre koda

- `docs/websocket-schema.md §4` — notifications kanal.
- `frontend/types/notification.ts` — `NotificationResponse`, `NotificationType` (16 vrednosti — **MORA da se poklope sa backend enum-om**).
- `frontend/lib/api/notifications.ts` — endpoint signature.
- `backend/app/models/notification.py` — već postoji.

### 4.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/schemas/notification.py` | NEW | `NotificationResponse` (id, type, title, body, data, is_read, created_at), `NotificationListResponse` (items + unread_count), `MarkReadRequest` |
| 2 | `backend/app/services/notification_service.py` | NEW | `create(db, user_id, type, title, body, data)` — INSERT + `redis.publish(f"notif:pub:{user_id}", envelope)`. `list(db, user_id, unread_only, limit, offset)`. `mark_read(db, user_id, ids)`. `mark_all_read(db, user_id)`. `unread_count(db, user_id)`. |
| 3 | `backend/app/api/v1/notifications.py` | NEW | `GET /` (paginated + `unread_only` flag), `POST /mark-read` (ids), `POST /mark-all-read`, `GET /unread-count`, `@router.websocket("/stream")` (token query param). |
| 4 | `backend/app/main.py` | EDIT | Odkomentariši `notifications.router` import + include. |
| 5 | `backend/app/tasks/notifications.py` | EDIT | **Sve postojeće email taskove obavi i in-app notif:** posle `send_email.delay(...)`, dodaj `notification_service.create(...)` (kroz async wrapper, jer Celery task je sync — koristi `asyncio.run`). Pokriti sve 16 vrednosti `NotificationType`. |

### 4.3 Kritični detalji

- **`NotificationType` enum** mora imati **istih 16 vrednosti** kao `frontend/types/notification.ts::NotificationType`. Otvori taj fajl, prepiši listu, napravi PG enum (Alembic migracija ako ne postoji).
- **WS envelope:**
  ```json
  { "event": "notification.new", "ts": "...", "data": { /* NotificationResponse */ } }
  ```
- **`notif:pub:{user_id}`** — kanal po korisniku, ne globalan (sigurnost).
- **Backpressure:** ako Redis Pub/Sub queue na klijentu raste preko 100 poruka → close(4429).
- **Async u Celery sync task-u:**
  ```python
  import asyncio
  @celery_app.task
  def send_appointment_confirmed(appointment_id: str):
      asyncio.run(_send_appointment_confirmed_async(appointment_id))
  ```

### 4.4 Acceptance

- [ ] Profesor odobri zahtev → student vidi novi notif u zvonu **bez reload-a** (< 2s).
- [ ] Counter se ažurira (badge na bell ikonici).
- [ ] `POST /mark-read` skida `is_read=true` i counter pada.
- [ ] `WS /stream` odbija invalid JWT sa 4401.
- [ ] Frontend `lib/stores/notification-ws-status.ts` prelazi iz `disconnected` u `connected`.

**Procena:** 1.5 dan.

---

## KORAK 5 — Faza 4.3: Admin users CRUD + bulk CSV import

**Zašto sada:** `/admin/users` stranica ima kompletan UI (tabela + filteri + form modal + bulk import dialog). Čeka samo backend endpoint-e.

### 5.1 Pre koda

- `frontend/types/admin.ts` — `AdminUserResponse`, `BulkImportPreview`, `BulkImportResult`.
- `frontend/lib/api/admin.ts` — endpoint signatures.
- `frontend/components/admin/users-table.tsx` + `bulk-import-dialog.tsx` — vidi šta tačno frontend očekuje u response-u.
- `ROADMAP.md §4.3 / §4.7`.

### 5.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/schemas/admin.py` | NEW | `AdminUserResponse`, `AdminUserCreate` (sa optional `professor` polje za PROFESOR/ASISTENT), `AdminUserUpdate`, `BulkImportPreview` (valid_rows, invalid_rows + reason, duplicates), `BulkImportResult` (created, skipped) |
| 2 | `backend/app/services/user_service.py` | NEW | `list_users(db, role, faculty, q, page, size)`, `create_user(db, data)` (kreira `User`, ako je PROFESOR i `Professor` zapis sa default-ima), `update_user(db, id, data)`, `deactivate_user(db, id)`, `bulk_import_preview(db, csv_bytes)`, `bulk_import_confirm(db, csv_bytes)` |
| 3 | `backend/app/api/v1/admin.py` | EDIT (postojeći iz Faze 3.2) | Dodaj: `GET /users` (filteri), `POST /users`, `PUT /users/{id}`, `DELETE /users/{id}` (soft delete: is_active=false), `POST /users/bulk-import/preview` (multipart), `POST /users/bulk-import/confirm` (multipart) |

### 5.3 Bulk CSV detalji

- **CSV header:** `ime, prezime, email, indeks, smer, godina_upisa` (PRD §3.1).
- **Validacija po redu:**
  - Email mora biti `*@student.fon.bg.ac.rs` ili `*@student.etf.bg.ac.rs` (bulk je samo za studente).
  - Email mora biti unique (provera u bazi + provera duplikata u istom CSV-u).
  - `godina_upisa` ∈ [2015, current_year].
- **Preview** vraća listu `valid_rows` i `invalid_rows[]` sa razlogom + `duplicates[]`.
- **Confirm** kreira `User` zapise sa **random privremenom lozinkom** koja se hashuje + šalje email „dobrodošli, postavite lozinku ovde". (Iskoristi postojeći password-reset flow.)
- **Trans akcioni princip:** ili svi prolaze ili nijedan (savepoint) — admin treba da vidi preview pre confirm-a.

### 5.4 Acceptance

- [ ] Admin → `/admin/users` → tabela se popunjava live podacima.
- [ ] „Dodaj korisnika" → kreiran PROFESOR sa email-om `nesto@fon.bg.ac.rs` → vidi se u tabeli.
- [ ] Bulk import sa CSV-om koji ima 5 valid + 2 duplikata + 1 invalid domen → preview pokazuje sve 3 kategorije → confirm kreira 5.
- [ ] Edit user (promena fakulteta) → reflektuje se u tabeli.
- [ ] Deactivate → user više ne može da se uloguje (401).

**Procena:** 2 dana.

---

## KORAK 6 — Faza 4.4: Impersonation + audit log

**Zašto sada:** `<ImpersonationBanner />` već postoji u top-baru, `useImpersonationStore` već tracking-uje state. Treba samo backend.

### 6.1 Pre koda

- `frontend/lib/stores/impersonation.ts` — kako frontend baratu impersonation tokenom.
- `frontend/types/admin.ts::AuditLogRow`.
- `docs/websocket-schema.md §6` — ugovor za impersonation JWT (TTL 30 min, **bez refresh-a**).
- `CLAUDE.md` pravila 14 i 15.

### 6.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/schemas/admin.py` | EDIT | Dodaj `ImpersonateResponse` (access_token, target_user, exp), `AuditLogRow` |
| 2 | `backend/app/services/impersonation_service.py` | NEW | `start(db, admin, target_user_id, ip)` → kreira poseban JWT sa custom claim-ovima (`imp: true`, `imp_email: <admin>`, `imp_name`, TTL 30 min), upisuje audit log; `end(db, admin, ip)` — upisuje audit log (token sam istekne) |
| 3 | `backend/app/services/audit_log_service.py` | NEW | `log(db, action, target, admin_user, ip, metadata)`, `list(db, filters, page, size)` |
| 4 | `backend/app/core/security.py` | EDIT | `create_access_token(...)` mora da podrži dodatne claim-ove (`imp`, `imp_email`, `imp_name`). `decode_access_token` čita ih i proslijeđuje u `current_user` dependency tako da `request.state.is_impersonation` postoji |
| 5 | `backend/app/api/v1/admin.py` | EDIT | Dodaj `POST /impersonate/{user_id}` → `ImpersonateResponse`; `POST /impersonate/end` → 204; `GET /audit-log` (filteri: admin_id, action, date range) |

### 6.3 Kritični detalji

- **Impersonation token NEMA refresh** — kad istekne (30 min) → 401 → admin re-impersonira (frontend već to handle-uje).
- **Audit log obavezan** za:
  - `IMPERSONATION_START` (admin_id, target_user_id, ip, ua)
  - `IMPERSONATION_END`
- **IP adresa**: čitaj iz `request.client.host` (ili `X-Forwarded-For` ako nginx prosleđuje). Tip kolone već je `INET`.
- **`current_user` dependency**: ako je `imp: true`, `current_user` je **target** (ne admin), ali RBAC i dalje vidi target-ovu rolu. Audit log uvek log-uje pravog admin-a iz `imp_email` claim-a.

### 6.4 Acceptance

- [ ] Admin → klik „Impersonate" na profesoru → ulogovan kao profesor → `<ImpersonationBanner />` crveni banner.
- [ ] `/admin/audit-log` lista pokazuje START + END events sa IP.
- [ ] Posle 30 min → 401 → frontend prikaže toast „Impersonation istekao, vrati se na admin".

**Procena:** 1 dan.

---

## KORAK 7 — Faza 4.5: Admin strikes + broadcast fan-out

**Zašto sada:** `/admin/strikes` i `/admin/broadcast` UI postoje. Strike sistem već radi automatski (no-show task), samo nedostaju admin endpoint-i da vidi/manage-uje.

### 7.1 Pre koda

- `frontend/types/admin.ts::StrikeRow, BroadcastRequest`.
- `frontend/lib/api/admin.ts` strikes + broadcast pozivi.
- `ROADMAP.md §4.5`.

### 7.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/schemas/admin.py` | EDIT | `StrikeRow` (student_id, full_name, email, total_points, active_block_until, last_strike_at), `UnblockRequest` (reason), `BroadcastRequest` (title, body, target, channels) |
| 2 | `backend/app/services/broadcast_service.py` | NEW | `create_broadcast(db, admin, data)` → INSERT u Notifications batch + queue Celery fan-out task |
| 3 | `backend/app/tasks/broadcast_tasks.py` | NEW | `fanout_broadcast_task(broadcast_id)` — učitaj listu user_id na osnovu `target` (FACULTY:FON / FACULTY:ETF / YEAR:2024 / ROLE:PROFESOR) → za svaki: `send_email.delay()` + `notification_service.create()` |
| 4 | `backend/app/api/v1/admin.py` | EDIT | `GET /strikes` (paginated, sort by points desc), `POST /strikes/{student_id}/unblock` (reason), `POST /broadcast`, `GET /broadcasts` (history) |
| 5 | `backend/app/services/strike_service.py` | EDIT | Dodaj `unblock_student(db, admin, student_id, reason)` ako ne postoji već — upiše u audit log, postavi `active_block_until=None`, kreira `NotificationType.BLOCK_LIFTED` notif |

### 7.3 Acceptance

- [ ] `/admin/strikes` tabela popunjava listom studenata sa `points >= 1`, sortiranu desc.
- [ ] „Unblock" sa razlogom → block se skida → student dobija notif + email.
- [ ] Broadcast sa target=FACULTY:FON → svi FON useri dobijaju email + in-app (proveri u Celery flower / SMTP log-u).
- [ ] Audit log beleži broadcast event.

**Procena:** 1 dan.

---

## KORAK 8 — Faza 4.6: Reminder Celery beat taskovi

**Zašto sada:** PRD §5.2 traži automatske podsetnike 24h i 1h pre termina. Trenutno postoji `send_appointment_reminder` ali nije vezan za beat schedule.

### 8.1 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/tasks/reminder_tasks.py` | NEW | `send_reminders_24h_task()` — scan APPROVED termini sa `slot_datetime` u prozoru `[now+23.5h, now+24.5h]` → za svaki proveri Redis idempotency key `reminder:24h:{appointment_id}` (TTL 25h) — ako ne postoji, set + `send_appointment_reminder.delay(id, 24)`. `send_reminders_1h_task()` — isto, prozor `[now+0.75h, now+1.25h]`, key `reminder:1h:...` |
| 2 | `backend/app/celery_app.py` | EDIT | U `beat_schedule`: `send-reminders-24h` (crontab `*/30 * * * *`), `send-reminders-1h` (crontab `*/15 * * * *`) |
| 3 | `backend/app/tasks/notifications.py` | EDIT | Dodaj `send_appointment_cancelled(appointment_id)` task (PRD §5.2 — fali u listi) |

### 8.2 Acceptance

- [ ] Kreiraj test slot za 24h od sad → sledeći beat tick (30 min) → student + profesor dobijaju email + in-app notif.
- [ ] Idempotency: ručno pokreni task 2x — drugi put nema slanja.
- [ ] Otkaži termin → student dobija „termin otkazan" email (ako je profesor otkazao) ili profesor dobija (ako je student otkazao).

**Procena:** 1 dan.

---

## KORAK 9 — Faza 5.1: Google PSE proxy

**Zašto na kraju ove faze:** PRD §2.5 traži pretragu po fakultetskim domenima. Frontend ima disabled stub `<GlobalSearchBox />` koji čeka ovaj endpoint.

### 9.1 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/services/pse_service.py` | NEW | `search(q: str) -> list[SearchResult]` — HTTP poziv na `https://www.googleapis.com/customsearch/v1` sa `cx=GOOGLE_PSE_CX` i `key=GOOGLE_PSE_API_KEY`. Cache u Redis-u (key `pse:{q}`, TTL 1h). |
| 2 | `backend/app/schemas/search.py` | NEW | `SearchResult` (title, link, snippet, source_domain), `SearchResponse` (items, total) |
| 3 | `backend/app/api/v1/search.py` | NEW | `GET /university?q=...&page=1` — proxy + cache. Rate limit (10 req/min po user-u). |
| 4 | `backend/app/main.py` | EDIT | Odkomentariši `search.router` |
| 5 | `backend/.env.example` | EDIT | Dodaj `GOOGLE_PSE_API_KEY=`, `GOOGLE_PSE_CX=` |
| 6 | `frontend/components/shared/global-search-box.tsx` | EDIT (mali) | Skini `disabled` flag jednom kad backend stigne |

### 9.2 Acceptance

- [ ] U Google Cloud Console kreiraj Programmable Search Engine restrikovan na `fon.bg.ac.rs` i `etf.bg.ac.rs`. Ubaci CX i API key u `.env`.
- [ ] `GET /api/v1/search/university?q=informatika` → 200 sa rezultatima.
- [ ] Drugi poziv sa istim `q` → cache hit (proveri Redis, treba da bude < 50ms response time).
- [ ] Frontend search box otvara dropdown sa rezultatima.

**Procena:** 0.5 dana.

---

## KORAK 10 — Migracija 0002: unaccent extension

**Zašto:** ROADMAP §1.3 i §1.7 pominju da search radi „sa unaccent od migracije 0002" — ali to još ne postoji. Trenutno query „Petrovic" ne nalazi „Petrović".

### 10.1 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/alembic/versions/20260428_0002_unaccent.py` | NEW | `op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")` + kreiraj IMMUTABLE wrapper `f_unaccent(text) RETURNS text` (jer `unaccent()` nije immutable u PG-u, pa ne može u functional index direktno) + funkcionalni indeksi nad `users.first_name`, `users.last_name`, `professors.areas_of_interest`, `subjects.name` |
| 2 | `backend/app/services/search_service.py` | EDIT | Zameni `User.first_name.ilike(f"%{q}%")` sa `func.f_unaccent(User.first_name).ilike(func.f_unaccent(f"%{q}%"))`. Isto za sva ostala polja. |

### 10.2 Acceptance

- [ ] Student kuca „Petrovic" → dobija „Milovan Petrović" u rezultatima.
- [ ] Student kuca „djordjevic" → dobija „Đorđević" (čak i sa zamenom dj/đ — proveri da li je dovoljno samo unaccent ili treba dodatni `replace(...)` korak).
- [ ] EXPLAIN ANALYZE pokazuje da search koristi indeks (`Index Scan using ix_users_first_name_unaccent...`).

**Procena:** 0.5 dana.

---

## ZAVRŠNI ČEK-LIST POSLE SVIH 10 KORAKA

Pre nego što kažeš da je gotovo, prođi kroz ovo:

- [ ] `docker compose --profile app up -d --build` diže sve servise bez greške.
- [ ] `alembic upgrade head` primenjuje 2 migracije (0001 + 0002).
- [ ] Swagger (`http://localhost/docs`) prikazuje sve nove endpoint-e pod tagovima Appointments / Notifications / Search / Admin.
- [ ] Sve frontend stranice koje su bile 🟡 sada su 🟢. Konkretno:
  - [ ] `/appointments/[id]` — detail + chat + files (live).
  - [ ] `/document-requests` — već je 🟢 iz Faze 3.2 (ostaje).
  - [ ] `/admin` — metrics se popunjava (kraj KORAKA 5 ili može stub do KORAKA 5.5).
  - [ ] `/admin/users` — CRUD + bulk import.
  - [ ] `/admin/strikes` — lista + unblock.
  - [ ] `/admin/broadcast` — pošalji broadcast.
  - [ ] `/admin/audit-log` — pregled.
  - [ ] `<NotificationCenter />` — real-time bell counter.
  - [ ] `<GlobalSearchBox />` — Google PSE radi.
- [ ] Svi notifikacioni email-ovi rade (proveri u Celery worker logu da nema neuhvaćenih izuzetaka).
- [ ] `pytest backend/tests/` prolazi (ako si pisao testove).
- [ ] Commit-ovi su clean: `feat(backend): step 3.3 appointment detail`, itd.
- [ ] Ažuriran `CURRENT_STATE2.md` (sekcija 0 TL;DR i sekcija 2 backend endpoint tabela) da reflektuje novo stanje.
- [ ] PR otvoren na `dev`.

---

## AKO ZAPNEM

Ako u nekom koraku Cursor počne da haluciniše ili predlaže nešto van stack-a (npr. „dodajmo Redis Streams umesto Pub/Sub" ili „prebacimo na sync FastAPI"), zaustavi ga i podsjeti:

> „Drži se CLAUDE.md sekcije 11 (zabranjena ponašanja) i `docs/websocket-schema.md`. Ne predlaži alternative stack-a. Ako ne razumeš ugovor, otvori `frontend/types/*.ts` ili `frontend/lib/api/*.ts` i prepiši odande."

Ako endpoint ne radi a frontend ga zove → otvori network tab, prokopaj request, uporedi sa Pydantic šemom red za red. 90% problema je razlika u jednom polju.

Ako Celery beat ne pokreće taskove → `docker logs studentska_celery_beat` mora prikazati linije „Scheduler: Sending due task ...". Ako fali — proveri `celery_app.py beat_schedule` registraciju i `--scheduler celery.beat.PersistentScheduler` u compose-u.

Ako MinIO presigned URL vrati 403 → bucket policy. Pokreni `infra/minio/init-buckets.sh` ručno protiv kontejnera.

---

**Total procena za sve korake:** 11–12 dana fokusiranog rada (jedan developer, sa Cursor pomoći).

Posle ovog prompta sve trenutne frontend stranice su funkcionalne. Sledeći prompt (`CURSOR_PROMPT_2_FEATURE_EXPANSION.md`) dodaje feature-e koji nisu u trenutnom UI-u (group consultations, push notifikacije, prod infra, testovi).
