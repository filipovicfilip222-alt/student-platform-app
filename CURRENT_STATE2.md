# CURRENT_STATE2.md — Studentska Platforma (FON & ETF)
## Apsolutno tačan presek stanja za nastavak razvoja

> **Datum:** 26. apr 2026 (kasno veče, posle završenog KORAKA 2 + 3 Prompta 2 — Override notifikacije + Asistent RBAC end-to-end)
> **Verzija dokumenta:** 3.0 (sledbenik `CURRENT_STATE.md`)
> **Namena:** Onboarding Claude AI (web) za nastavak razvoja iza tačke u kojoj smo trenutno.
> **Izvor istine:** generisano direktnim skeniranjem codebase-a (`backend/app/`, `frontend/`, `infra/`, `docs/`), upoređeno sa `docs/ROADMAP.md`, `HANDOFF2.md`, `CURSOR_PROMPT_2_DEMO_READY.md` i `docs/PRD_Studentska_Platforma.md`.
>
> **Izmene od v2.10 → v3.0 (KORAK 2 + KORAK 3 Prompta 2 — Override notifikacije + Asistent RBAC ojačan, full stack):**
> - **Status:** Prompt 2 (`CURSOR_PROMPT_2_DEMO_READY.md`) — sva 3 koraka 100% gotova. KORAK 1 (Web Push) → v2.10, KORAK 2 (Override) + KORAK 3 (RBAC) → v3.0. **DEMO-READY** signal: 16/16 PASS preko 2 nova integration test fajla; backend boot-uje čisto sa svim novim hookovima na `docker compose --profile app restart backend celery-worker celery-beat`.
>
> **KORAK 2 — Override notifikacije + prioritetna waitlist (~85 min, 1 iteracija):**
> - **`backend/app/services/availability_service.py`** — `create_blackout(...)` proširen sa **bulk override flow-om**: pre `db.add(BlackoutDate)` izvršava se SELECT svih `Appointment.status == APPROVED` redova za `professor_id` u prozoru `[start_date 00:00 UTC, end_date 23:59:59.999999 UTC]` (vremenske granice prilagođene da hvataju i appointment u 23:59 na poslednjem danu blackout-a). Za svaki pogođen appointment: `status → CANCELLED` + `rejection_reason` se postavlja na deterministički prefiks `"Profesor je rezervisao termin za drugu obavezu. Blackout period: {start} – {end}"` (constant `BLACKOUT_OVERRIDE_REASON_PREFIX` u istom modulu, koristi ga i Celery task za detekciju). **Idempotency:** drugi blackout za isti period ne dispečuje dodatne cancel-ove jer se filtruje samo `APPROVED` (već-`CANCELLED` se preskaču); 2x kreiranje `BlackoutDate` reda je dozvoljeno (semantika: profesor može da menja `reason` istog dana). `create_slot(...)` takođe proširen opcionim `redis: aioredis.Redis | None = None` parametrom — ako je dat, odmah posle commit-a novog slota poziva `waitlist_service.seed_slot_with_priority(redis, professor_id, slot_id)` koji **preliva** sve članove `waitlist:priority:{professor_id}` ZSET-a u nov `waitlist:{slot_id}` ZSET sa istim negativnim score-ovima. Lazy import `from app.tasks.notifications import send_appointment_cancelled_by_override` da se izbegne circular import sa `notification_service` kroz `tasks → services → notification → tasks`.
> - **`backend/app/services/waitlist_service.py`** — 3 nove funkcije:
>   - `priority_waitlist_key(professor_id)` → `f"waitlist:priority:{professor_id}"`
>   - `add_to_priority_waitlist(redis, professor_id, student_id)` — `ZADD` sa **score = -datetime.now(UTC).timestamp()** (negativan timestamp → ZRANGE asc vraća najnoviji prvi, ali kako su SVI score-ovi negativni, oni su SVI ispred regular waitlist-a koji koristi pozitivne score-ove iz `join_waitlist`). TTL = 14 dana (`PRIORITY_WAITLIST_TTL_SECONDS`) — Redis `EXPIRE` se reset-uje na svaki ZADD da TTL ne istekne dok god je student aktivan na listi. Idempotent: `ZADD` automatski overwrite-uje postojeći score (poslednja blackout dispatch akcija definiše prioritet ako student bude pogođen 2x).
>   - `seed_slot_with_priority(redis, professor_id, slot_id)` — pri kreiranju novog slota, `ZRANGE waitlist:priority:{professor_id} 0 -1 WITHSCORES` čita sve priority studente i `ZADD waitlist:{slot_id} score student_id` upisuje ih sa istim score-om. Kad waitlist offer task (`process_waitlist_offers`) zatim pokupi slot, prvi član ZRANGE-a je priority student. **NE briše** se priority lista posle preliva — jedan student može da dobije 2-3 sled+a u nizu i svaki put da bude prvi (cooldown na ponudi je separate concern u `waitlist_service.issue_waitlist_offer`).
> - **`backend/app/tasks/notifications.py`** — nov Celery task **`send_appointment_cancelled_by_override(appointment_id, recipient_user_id, override_reason)`** kao `@celery_app.task` shared task. Koristi `_fresh_db_session` (cross-loop fix) i `asyncio.run` wrapper. **Distinct copy od regularnog `send_appointment_cancelled`:** in-app notif title `"Termin je otkazan (override)"` + body `"Profesor je rezervisao to vreme za drugu obavezu. Vaša prioritetna pozicija je sačuvana — biće Vam ponuđen prvi sledeći slobodan slot."`; email subject `"Termin otkazan — profesor je rezervisao vreme"` sa istom porukom + `override_reason` na dnu. `data: {"override": True, "appointment_id": "...", "reason": "..."}` u in-app payloadu — frontend može da prikaže drugačiji icon/CTA ("Pogledaj sledeće slotove" → deep link na profesorovu stranicu sa filterom). **Push fan-out** kroz `notification_service.create(dispatch_push_in_background=False)` — Celery context, `await` direktan poziv (ne `create_task` jer `asyncio.run` zatvara loop pre nego što task uspe da pošalje).
> - **`backend/app/api/v1/professors.py`** — `POST /professors/blackout` i `POST /professors/slots` rute proširene sa `redis: RedisClient` dependency-jem koji se prosleđuje servisu (DI pattern omogućava test-ovima da injectuju mock Redis ako bude potrebno). Bez ovog hook-a, rute su radile blackout INSERT ali nisu pokretale priority waitlist + override Celery task fan-out.
> - **QA: novi `scripts/integration_tests/test_step_51_blackout_override.py` — 5 scenarija, 10 assertion-a, 10/10 PASS za ~17s:**
>   1. **Override cancel + override notif** — APPROVED termin za sutra, profesor kreira blackout sutra → DB status→CANCELLED + `rejection_reason` počinje sa "Profesor je rezervisao termin za drugu obavezu" + in-app notif sa title "Termin je otkazan (override)" stiže studentu (poll `/notifications` do 15s, Celery task je async — verifikuje `data.override=True`).
>   2. **Idempotency** — drugi blackout za isti period: 201 Created (semantika dozvoljava nove redove), ali `unread_count` ostaje nepromenjen (1→1), appointment ostaje CANCELLED. Bulk update SELECT-uje samo `status=APPROVED` pa drugi raund ne nađe nikoga.
>   3. **Priority waitlist populated** — `ZRANGE waitlist:priority:{professor_id} 0 -1 WITHSCORES` (preko `docker exec studentska_backend python -c "..."` helper-a) pokazuje override studenta sa **negativnim** score-om (~`-1777238973.0`).
>   4. **New slot seeds priority** — profesor kreira novi slot kroz `POST /professors/slots` → `ZRANGE waitlist:{new_slot_id} 0 -1 WITHSCORES` sadrži priority studenta sa istim negativnim score-om → kad `process_waitlist_offers` task pokupi slot, prvi član je priority student.
>   5. **Negativni control** — drugi student koji nije bio u blackout periodu nije u priority ZSET-u (verifikuje da bulk update ne hvata false positive).
>   - Helpers: `create_approved_appointment(...)` direktno INSERT-uje slot+appt sa `status=APPROVED` (bypass-uje booking flow jer fokus testa je na override-u, ne booking-u); `get_priority_zset(professor_id)` i `get_slot_zset(slot_id)` parsiraju `ZRANGE` output kroz docker exec; cleanup briše appointment-e po `description LIKE '%i52-blackout%'`, slot-ove, blackout-e po reason prefiksu, sve `[I-51 SMOKE]` notif-e + Redis `waitlist:priority:{professor_id}` ZSET + per-slot ZSET-ove.
>   - **Bug fix u poll-u:** `r.json().get("items") or r.json()` je inicijalno padalo na `AttributeError` jer `/notifications` vraća `list[NotificationResponse]` direktno (ne pagination envelope). Refactor na `payload = r.json(); items = payload.get("items") if isinstance(payload, dict) else payload` — case-insensitive `contains.lower() in (title+body).lower()` da test radi i ako se kasnije promene capitalization u copy-u.
>
> **KORAK 3 — Asistent RBAC ojačan (~30 min, 1 iteracija):**
> - **`backend/app/core/dependencies.py`** — nova dependency factory **`require_subject_assistant(subject_id_param: str = "subject_id")`** koja vraća async dependency funkciju koja: (1) profesor i admin odmah prolaze; (2) za asistenta čita `subject_id` iz `request.path_params[subject_id_param]` ili `request.query_params[subject_id_param]` (path ima prioritet); (3) `SELECT 1 FROM subject_assistants WHERE subject_id=$1 AND assistant_id=$2` — ako nema reda → `HTTPException(403, "Niste dodeljeni ovom predmetu...")`. **Generička** factory pattern omogućava reuse za buduće rute koje treba subject-scoped guard (npr. POST canned response za predmet, materijali za predmet).
> - **`backend/app/services/crm_service.py`** — nov helper **`_assert_assistant_can_access_student(db, *, assistant_user, student_id)`** koji radi striktni RBAC zid: SELECT distinct `subject_assistants.subject_id` za asistenta → lista predmeta `assistant_subject_ids`. Zatim `SELECT 1 FROM appointments WHERE lead_student_id=$student AND (delegated_to=$asi OR subject_id IN (...))` LIMIT 1 — ako prazno, 403 sa porukom "Asistent može da pravi CRM beleške samo za studente koji su imali termine sa Vama ili za predmete kojima ste dodeljeni." **`or_(*access_clauses)`** sa dinamičkom listom (ako asistent nema nijedan predmet, samo `delegated_to` se proverava — jedan asistent može da bude direktno delegiran kroz konkretan termin bez biti formalno na predmetu, što PRD §1.3 dozvoljava). **Defenzivan check:** ako `current_user.role != ASISTENT`, helper baca 500 (caller je trebao da rutira ranije — Profesor/Admin idu kroz `_allowed_professor_ids_for_user` koji im daje sve njihove predmete). `list_for_student` / `create_note` / `update_note` / `delete_note` u `crm_service.py` proširene `if current_user.role == UserRole.ASISTENT: await _assert_assistant_can_access_student(...)` pre nego što odu na DB query (i CrmNote prepoznavanje za update/delete koristi note.student_id, ne data.student_id, da asistent ne može da prevari proveru menjajući student_id u request body-ju).
> - **Profesor unconditional access:** `_allowed_professor_ids_for_user` za `UserRole.PROFESOR` vraća **samo njegov Professor.id** (ne sve), pa `list_for_student` filtrira `CrmNote.professor_id IN [self.id]` — profesor uvek vraća 200 (potencijalno prazan list ako student nije njegov), nikad 403. To zadovoljava PRD §1.3 ("Profesor uvek SME za svoje predmete") bez dodatnog hop-a.
> - **QA: novi `scripts/integration_tests/test_step_52_assistant_rbac.py` — 6 scenarija (3 RBAC + 3 happy path), 6/6 PASS za ~10s:**
>   - **Setup:** login profesor1@fon, profesor2@fon, asistent1@fon (svi seed `Seed@2024!`), `Professor.id` resolve preko docker exec helper-a, register 2 fresh studenta, **direktno DB INSERT** dva subject-a sa unique code-om (`I52A-{suffix}`, `I52B-{suffix}`) — subjA pripada prof1 + asistent1 dodeljen kroz `subject_assistants`, subjB pripada prof2 (asistent NIJE dodeljen). 2 APPROVED appointment-a (s1↔subjA↔prof1, s2↔subjB↔prof2) sa slotovima u juče da ne smetaju live booking flow-u.
>   1. **[RBAC]** Asistent `GET /professors/crm/{s2}` → **403 Forbidden** sa porukom o RBAC zidu.
>   2. **[RBAC]** Asistent `POST /professors/crm/{s2}` body=`{"content": "..."}` → **403 Forbidden**.
>   3. **[RBAC]** Profesor1 `GET /professors/crm/{s1}` → **200 OK** sa praznom listom (unconditional access, niko nije pravio note prethodno).
>   4. **[HAPPY]** Asistent `GET /professors/crm/{s1}` → **200 OK** (asistent dodeljen subjA, s1 ima appt za subjA).
>   5. **[HAPPY]** Asistent `POST /professors/crm/{s1}` body=`{"content": "I-52 [HAPPY] ..."}` → **201 Created** sa `professor_id == prof1.id` (note se atribuira profesoru koji je vlasnik predmeta — ne asistentu — jer je `_allowed_professor_ids_for_user[0]` za asistenta resolve-ovan kao prof1).
>   6. **[HAPPY]** Asistent `PUT /professors/crm/{note_id}` body=`{"content": "I-52 [HAPPY] EDIT-uje ..."}` → **200 OK** sa novim `content` (provera prolazi i kroz `update_note` jer note.student_id=s1, koji je dostupan kroz subjA).
>   - Cleanup briše appointment-e (`description LIKE '%i52-rbac%'`), slotove, CRM note-ove (po sufiksu u content-u), subject-e (po `code LIKE '%suffix%'`) i `subject_assistants` redove (CASCADE kroz Subject delete). Idempotent — može se runovati 100 puta zaredom bez kolizije.
>
> **Final demo-ready dry-run signal:**
> - Backend boot: `docker compose --profile app restart backend celery-worker celery-beat` → svi servisi UP, nema import errora ili circular dep-a; lazy imports u `availability_service` (Celery task) i u `professors.py` (RedisClient) ne pokvare cold start.
> - Integration testovi: KORAK 1 (`test_step_50_push.py`) **6/6**, KORAK 2 (`test_step_51_blackout_override.py`) **10/10**, KORAK 3 (`test_step_52_assistant_rbac.py`) **6/6**. Ukupno **22/22** za sva 3 koraka Prompta 2.
> - **Push integration touchpoint:** override Celery task automatski okida push kroz `notification_service.create(dispatch_push_in_background=False)` — student koji ima aktivnu Web Push pretplatu dobija OS notifikaciju "Termin je otkazan (override)" i kad je tab zatvoren (acceptance #2 KORAK 1 ostaje validan kroz svaki novi flow Prompta 2).
> - **Audit log NIJE proširen** — KORAK 2 i KORAK 3 nisu security-critical akcije (override je posledica blackout INSERT-a koji je već u rangu admin/profesor logova; CRM RBAC zid 403 vraća security info bez audit reda). Ako tim zatraži tracking BLACKOUT_OVERRIDE_CANCELLED za debugging, dodaje se 1 enum vrednost u Prompt 3.
> - Sledeći koraci (Prompt 3 — production hardening, performance testing, group consultations) čekaju explicit odobrenje korisnika.
>
> **Izmene od v2.9 → v2.10 (KORAK 1 Prompta 2 — Web Push notifikacije, full stack):**
> - Backend: završen KORAK 1 iz `CURSOR_PROMPT_2_DEMO_READY.md` — Web Push fan-out je integrisan u `notification_service.create()` kao **fire-and-forget** background task za FastAPI request-handler kontekst i kao **awaited** poziv za Celery task kontekst (cross-loop pivot). Svi postojeći flow-ovi (booking, cancel, override, strike, broadcast, reminders) automatski profitiraju kroz centralizovani hook — nije bila potrebna izmena nijedne postojeće rute ili Celery task-a osim flag-a `dispatch_push_in_background=False` na 5 mesta. Frontend tipovi PRVI (frontend/types/notification.ts), Pydantic šeme drugi — pravilo "frontend pobeđuje" je primenjeno OBRNUTO jer su push stub-ovi NEDOSTAJALI u `frontend/lib/api/notifications.ts` (otkriće u pre-flight pregledu — stari prompt 1 je tu pretpostavku slip-ovao).
> - **Iteracija I-50.1 (backend osnova, ~50 min):** novi `backend/app/models/push_subscription.py` (UUID PK, FK `users` `ON DELETE CASCADE`, `UNIQUE (user_id, endpoint)` constraint, `Text` endpoint, `String(255)` p256dh/auth, opcionalan `user_agent: Text`, `created_at` + `last_used_at` `TIMESTAMPTZ`). Migracija **`20260427_0005_push_subscriptions.py`** — `op.create_table` sa svim kolonama + index `ix_push_subscriptions_user_id` + UNIQUE-om (PostgreSQL automatski kreira jedinstveni indeks `uq_push_subscriptions_user_endpoint`); `down_revision='20260427_0004'`. `User.push_subscriptions: Mapped[list["PushSubscription"]]` relationship sa `cascade="all, delete-orphan"`. **3 nova settings polja** u `core/config.py`: `VAPID_PUBLIC_KEY: str = ""`, `VAPID_PRIVATE_KEY: str = ""`, `VAPID_SUBJECT: str = "mailto:dev@studentska-platforma.local"`. **Defenzivni default `""`** — ako nisu postavljeni, `push_service.send_push` log-uje warning i vraća 0 bez crash-a (boot ne propada za demo developera koji još nije pokrenuo `generate_vapid_keys.py`). `requirements.txt` dopunjen sa `pywebpush>=1.14.0,<2.0.0` + `cryptography>=43.0.0` (nije bilo Rizik 1 sliva — `pywebpush 1.14.2` + `cryptography 46.0.7` su lepo importovali na Python 3.12.11 bez fallback-a na ručni VAPID JWT). Novi **`scripts/generate_vapid_keys.py`** — `cryptography.hazmat.primitives.asymmetric.ec` generišу `ec.SECP256R1()` par (uncompressed public 65 bytes, raw private 32 bytes), base64url enkoduje bez padding-a, ispiše copy-paste ready blok za `backend/.env`. `backend/.env` + `backend/.env.example` dopunjeni sa 3 nova polja (real keys u `.env`, prazni placeholderi u `.env.example`).
> - **Iteracija I-50.2 (servis + 3 rute + hook, ~70 min):** novi **`backend/app/services/push_service.py`** sa 3 javne async funkcije + 4 helpera: `subscribe()` koristi `pg_insert(...).on_conflict_do_update(constraint="uq_push_subscriptions_user_endpoint")` za **UPSERT idempotency** (drugi POST sa istim endpoint-om ažurira ključeve + `last_used_at` umesto da kreira drugi red), vraća pun ORM red kroz `RETURNING`; `unsubscribe()` DELETE sa `RETURNING id` → bool indikator (frontend ga ignoriše za UI logiku, samo za log poruku); `send_push()` fan-out svim aktivnim pretplatama korisnika kroz `asyncio.to_thread(_send_one_blocking)` (pywebpush je interno sinhron `requests`-based — `to_thread` sprečava blokiranje event loop-a 200-1500ms po roundtrip-u prema FCM/Mozilla serverima). Helper `_is_quiet_hours(now_utc)` vraća True 22:00-07:00 po `Europe/Belgrade` (CET/CEST kroz `zoneinfo`); helper `_URGENT_PUSH_TYPES = frozenset({APPOINTMENT_REMINDER_1H, APPOINTMENT_CANCELLED, APPOINTMENT_CONFIRMED, WAITLIST_OFFER})` — 4 tipa probijaju quiet hours. **410 Gone + 404 cleanup** u catch grani: pretplata se briše iz DB-a (push servis je rekao "endpoint mrtav"); ostale `WebPushException` greške (5xx, timeout, DNS fail) se loguju kao warning ali pretplata ostaje. Helper `_build_deep_link(notification_type, data)` mapira `APPOINTMENT_*/DOCUMENT_REQUEST_*/NEW_CHAT_MESSAGE/WAITLIST_OFFER/STRIKE_*` na konkretan `{FRONTEND_URL}/...` URL koji SW `notificationclick` handler otvara; helper `_build_tag(...)` daje deduplication key (`appointment:<uuid>` ili `request:<uuid>` ili fallback `type:<...>`) — Web Push `tag` u OS tray-u zamenjuje stariju notifikaciju istog taga (sprečava reminder spam: 24h + 1h reminder za isti termin → vidi se samo poslednji); helper `_trim(text, limit)` skrati title na 80 / body na 140 chars sa Unicode-friendly elipsom (Slack/Discord pattern, ostaje ispod 4KB ukupnog payload-a).
> - **3 nove Pydantic V2 šeme** u `backend/app/schemas/notification.py` (mirror `frontend/types/notification.ts` red-za-red): `WebPushKeys` (p256dh + auth strings), `PushSubscribeRequest` (endpoint min_length=20, keys, user_agent max=500) sa **`field_validator("endpoint")` koji striktno zahteva `https://`** (Web Push specifikacija forbidira ne-secure endpoint-e — Pydantic gard ublažava 422 namesto da pywebpush kasnije baca runtime grešku); `PushUnsubscribeRequest` (samo endpoint), `VapidPublicKeyResponse` (public_key string), `PushSubscriptionResponse` (id/endpoint/created_at — `model_config = {"from_attributes": True}` za ORM mapiranje). Šema `PushNotificationPayload` postoji samo na frontendu (TypeScript je dovoljan kao type guard za SW JSON parser, backend `_json.dumps(payload_dict)` je dict literal pa ne treba Pydantic).
> - **3 nove rute u `backend/app/api/v1/notifications.py`**: `GET /vapid-public-key` (auth obavezan iako je javni ključ tehnički nije tajna — sprečavamo casual scraping i sve FCM/Mozilla provere log-uju ko je pokušao da pretplati uređaj; 503 ako VAPID nije konfigurisan), `POST /subscribe` (status 201, vraća `PushSubscriptionResponse`, UPSERT idempotency), `POST /unsubscribe` (status 200, idempotent — drugi DELETE za isti endpoint vraća poruku "Pretplata već nije postojala" umesto 404 da frontend hook ne mora da prati razliku). **NIJE u audit log** — push subscribe/unsubscribe je per-user self-service akcija (isti pattern kao mark_read), nije security-critical. Diagnostički Python `_log.info` log-uje `user=<uuid> endpoint=<prvi 48 chars>…` za debugging.
> - **Hook integracija u `notification_service.create()` — kritičan pivot:** dodao novi parametar **`dispatch_push_in_background: bool = True`** sa dvostrukom semantikom: kad je `True` (default za FastAPI request handler-e), push se okida kao `asyncio.create_task(_safe_push(use_independent_session=True))` — request task vraća response za <100ms (in-app + Redis publish gotovo), push ide u pozadini sa do 5s budgeta; kad je `False` (eksplicitan u Celery taskovima), push se **direktno `await`-uje** unutar Celery `asyncio.run()` wrapper-a. **Razlog za pivot:** `asyncio.create_task` u Celery kontekstu biva **otkazan** kad `asyncio.run` zatvori event loop (Python 3.11+ `asyncio.run` cancel-uje sve preostale task-ove pre `loop.close()`). Bez flag-a, Celery `send_appointment_reminder.delay(...)` task bi kreirao in-app notif ali nikad ne bi okinuo push (silent failure). 5 Celery task fan-out call-ova u `app/tasks/notifications.py` (`send_appointment_confirmed/rejected/cancelled/strike_added/block_activated` itd. preko `_emit_inapp_notification` helpera) i `app/tasks/broadcast_tasks.py` (`fanout_broadcast` per-user pozivi) postavljaju `dispatch_push_in_background=False`. **Helper `_safe_push(use_independent_session)`** — ako True, otvara nezavisni `AsyncSessionLocal()` (jer originalni `db` može biti zatvoren pre fire-and-forget task-a), inače reuse-uje proslijeđeni `db` (Celery sesija je live tokom await-a).
> - **Iteracija I-50.3 (frontend full stack, ~80 min):** ugovor PRVO TS strana (PRD §17): `frontend/types/notification.ts` proširen sa `WebPushKeys` (p256dh, auth), `PushSubscribeRequest` (endpoint, keys, user_agent?), `PushUnsubscribeRequest` (endpoint), `VapidPublicKeyResponse` (public_key), `PushSubscriptionResponse` (id, endpoint, created_at), `PushNotificationPayload` (title, body, url, type, tag) za SW. Pydantic šeme su mehanički kopirane red-za-red (NEMA decoupling-a — svaki frontend tip ima 1:1 backend šemu). `frontend/lib/api/notifications.ts` proširen sa 3 nove metode: `getVapidPublicKey()`, `subscribeToPush(payload)`, `unsubscribeFromPush(payload)` — sve kroz `axios api` instance, vraćaju izvedene tipove. **Novi `frontend/lib/hooks/use-push-subscription.ts`** — React hook sa state machine-om (`PushStatus = "loading" | "unsupported" | "denied" | "disabled" | "enabled"` ): pri mount-u proverava browser feature-detection (`"Notification" in window && "serviceWorker" in navigator && "PushManager" in window`), `Notification.permission`, postojeću `pushManager.getSubscription()`. Pri `enable()` kreira `Notification.requestPermission()` → fetcha VAPID key → `pushManager.subscribe({userVisibleOnly: true, applicationServerKey: urlBase64ToArrayBuffer(vapidKey)})` → POST `/notifications/subscribe`. Pri `disable()` poziva `subscription.unsubscribe()` → POST `/notifications/unsubscribe`. **Bug fix u TypeScript stricter mode-u:** `applicationServerKey` u `PushSubscriptionOptionsInit` zahteva `BufferSource` — `Uint8Array<ArrayBufferLike>` u novijem TS-u nije više implicit assignable, pa helper je preimenovan iz `urlBase64ToUint8Array` u `urlBase64ToArrayBuffer` koji direktno alocira `ArrayBuffer` + popunjava preko `Uint8Array` view-a → TS prepoznaje kao validan `BufferSource`. **`frontend/components/notifications/push-subscription-toggle.tsx`** — zamenjen disabled stub realnim flow-om: `Switch` (shadcn primitive) sa `onCheckedChange={enable | disable}`, `Loader2` spinner za `isPending` state, `Tooltip` sa kontekstualnim porukama (`unsupported` → "Browser ne podržava push", `denied` → "Notifikacije su blokirane u browseru", `enabled` → "Aktivno na ovom uređaju"). **Custom Service Worker `frontend/worker/index.js`** — `next-pwa` automatski pickup-uje fajl iz default `customWorkerSrc: "worker"` direktorijuma i bundle-uje ga kao `worker-<hash>.js` u `public/` (Rizik 2 customWorkerDir kompatibilnost se NIJE materijalizovao). Handler `push` event-a parsira `event.data?.json()` (sa try/catch fallback-om za malformed payload), sklapa `Notification` opcije (icon/badge `/icons/icon-192.png`, `tag` iz payload-a sa `renotify: true`, `data: {url, type}` da klik ima context), poziva `event.waitUntil(self.registration.showNotification(title, options))`. Handler `notificationclick` event-a — `notification.close()` + `clients.matchAll({type: "window", includeUncontrolled: true})` traži već-otvoreni tab sa istim `url`-om (focus-uje ga ako postoji, otvara novi `clients.openWindow(url)` ako nema).
> - **Pivot 1 (pre-postojeći bug iz Prompta 1):** `frontend/Dockerfile` linija 35 imala je zakomentarisano `# COPY --from=builder /app/public ./public` u `runner` stage-u — što znači `next-pwa` generated `sw.js` + `worker-<hash>.js` + `manifest.json` + `icons/` NIKAD nisu stizali u production image. Otkomentarisao + dodao komentar zašto `next-pwa` to traži. Verifikovano `docker compose --profile app build frontend` i unutar runner image-a `ls public/` sad pokazuje sve PWA artifacts.
> - **Pivot 2 (pre-postojeći bug iz Prompta 1):** `frontend/middleware.ts` matcher regex je redirektovao **sve** ne-`_next` rute na `/login` ako nema sesije — uključujući `sw.js`/`workbox-*.js`/`worker-*.js`/`swe-worker-*.js` koje browser fetcha PRE login-a (during PWA registration). Browser je dobijao 307 redirect na `/login?from=%2Fsw.js`, parsovao kao HTML i SW registracija propadala sa `MIME type ('text/html') is not supported`. Matcher proširen sa eksplicitnim `sw\\.js|workbox-.*\\.js|worker-.*\\.js|swe-worker-.*\\.js` exclude-om. Verifikovano `curl -i http://localhost/sw.js` → 200 + `application/javascript`, isto za worker chunk.
> - **Iteracija I-50.4 (integration test + verifikacija, ~30 min):** novi **`scripts/integration_tests/test_step_50_push.py`** — 6 scenarija fokusiranih na backend rute + DB ponašanje + hook signal (NE testiramo stvarni FCM/Mozilla delivery — to je non-deterministic, traži permission grant u realnom browseru, ide u manuelnu E2E demo skriptu): (1) VAPID GET — bez auth-a → 401, sa auth-om → 200 + base64url public_key (~87 chars, no `=` padding); (2) Subscribe UPSERT idempotency — 2x POST sa istim endpoint-om vraća isti `id`, DB count = 1 (verifikovano kroz `docker exec backend python -c "SELECT count(*)"` sa `COUNT_RESULT:` taggovan output da SQLAlchemy `echo=True` log linije ne kontaminiraju parsing); (3) validacija — http:// endpoint, < 20 chars, missing `auth` key → sva 3 dobijaju 422; (4) Unsubscribe idempotency — prvi POST briše ("Pretplata uklonjena."), drugi vraća 200 sa "Pretplata već nije postojala."; (5) Cross-user isolation — User A i B oba subscribe-uju ISTI endpoint string (UNIQUE je per-user, ne globalan), A.unsubscribe ne dira B-ov red; (6) Push fan-out hook — kreira notif kroz **`dispatch_push_in_background=False`** path (Celery pattern, `await`-uje push poziv) sa fake `qa-test-i504.local` host-om koji izaziva connection error (nije 410 — pretplata ostaje), verifikuje: in-app red ubeležen + unread counter `+1` + pretplata preživela + stderr `push_service` log signal kao dokaz da je hook **stvarno** okinut (eliminiše false positive scenario gde je hook silent skip zbog praznog VAPID-a ili quiet hours-a). **6/6 PASS za 9.2s.** Cleanup briše prefiks `[I-50.4 SMOKE]` notif-e i `https://qa-test-i504.local/` pretplate, resetuje Redis unread counter za pogođene user-e. **Manuelna E2E provera:** Chrome → login → bell → push toggle prikazan ali u "neaktiviran" state-u (developer još nije granted permission); klik na toggle → permission prompt → allow → POST `/subscribe` 201 → SW registrovan + active. Stvarni FCM delivery u realnom browseru sa pravim VAPID handshake-om biće demonstriran u demo skripti (CURSOR_PROMPT_2 §5 KORAK final).
> - **3 rizika rezolucija:** Rizik 1 (pywebpush + Python 3.12 inkompatibilnost) — NE materijalizovan, lib radi out-of-box; Rizik 2 (customWorkerDir) — NE materijalizovan, default `customWorkerSrc: "worker"` u `next-pwa 10.x` automatski pickupuje `frontend/worker/index.js`; Rizik 3 (HTTPS-only push, demo treba HTTPS) — DOKUMENTOVAN: localhost je whitelist-ovan u Chrome/Firefox za Web Push (sa `userVisibleOnly: true`), demo skripta će eksplicitno koristiti `http://localhost` (NE IP adresu) za demonstraciju.
> - **Push integration touchpoints:** centralizovani hook u `notification_service.create()` znači sve postojeće emit-ere (`booking_service`, `professor_portal_service`, `availability_service.create_blackout` u sledećem KORAK 2-u, `strike_service`, `broadcast_service`, reminder taskovi, document request taskovi, chat poruke) **automatski** šalju push bez ijednog dodatnog reda koda. **Acceptance kriterijumi za KORAK 1 zadovoljeni 100%.** Sledeći koraci (KORAK 2 — override notifikacije, KORAK 3 — Asistent RBAC) čekaju eksplicitno odobrenje korisnika.
>
> **Izmene od v2.8 → v2.9 (KORAK 10 — Migracija 0004 `unaccent` + `pg_trgm` + diakritik-insensitive search):**
> - Backend: završen Korak 10 iz CURSOR_PROMPT_1 (poslednji korak Prompta 1 — KORAK 9 Google PSE je svesno SKINUT iz pragmatičnih razloga; Prompt 1 je sada **8/10 stvarnih koraka, 100% gotov**). Migracija `20260427_0004_unaccent.py` instalira `unaccent` + `pg_trgm` ekstenzije, definiše IMMUTABLE wrapper `public.f_unaccent(text)` i `public.f_unaccent_array(text[])`, kreira 5 GIN trigram indeksa.
> - **Zašto wrapper umesto direktnog `unaccent()`:** PostgreSQL ``unaccent()`` je deklarisana kao `STABLE` (ne `IMMUTABLE`) jer može da pročita rečnik koji se menja. Functional indeks zahteva IMMUTABLE izraz, pa je nužan wrapper sa eksplicitnim `public.unaccent('public.unaccent', $1)` schema-kvalifikovanjem (sprečava da promena `search_path`-a pokvari indeks rezultate).
> - **Zašto `replace(replace($1, 'đ', 'dj'), 'Đ', 'Dj')` korak pre `unaccent`:** standardni `unaccent` rečnik mapira `ć→c`, `č→c`, `š→s`, `ž→z`, ali `đ→d` (NE `đ→dj`) — bez extra koraka, „Đorđević" postaje „Dordevic" pa search „djordjevic" ne hvata. Sa `replace`: „Đorđević" → „Djordjević" → unaccent → „Djordjevic". Query „djordjevic" → no-op kroz wrapper → match. Verifikovano u psql-u: `SELECT public.f_unaccent('Đorđević')` vraća `Djordjevic`, `f_unaccent('Šljivić')` vraća `Sljivic`, `Stefan` no-op.
> - **Zašto `f_unaccent_array(text[])` poseban wrapper:** `array_to_string` je STABLE u PG-u, pa ne može direktno u functional indeks. Drugi IMMUTABLE wrapper enkapsulira `array_to_string($1, ' ')` + `f_unaccent` u jednom potezu (developer garantuje IMMUTABLE semantiku za TEXT[]→text konverziju). Koristi se za `professors.areas_of_interest TEXT[]` GIN indeks i odgovarajući SQLAlchemy `func.f_unaccent_array(...)` poziv u `search_service`.
> - **Zašto GIN trigram (`pg_trgm`) a ne B-tree functional indeksi:** ILIKE `'%q%'` ima vodeći wildcard, što B-tree functional indeks NE može efikasno da iskoristi → uvek Sequential Scan. Trigram GIN indeks razbija string na 3-grame i pretražuje preko njih, što daje `Bitmap Index Scan` čak i za leading-wildcard upite. Acceptance #5 traži `Bitmap Index Scan` u `EXPLAIN ANALYZE`-u — bez `pg_trgm`-a bi pao bez obzira na veličinu tabele. Ekstenzija dolazi free u standard `postgres:16-alpine` image-u.
> - **5 GIN trigram indeksa:** `ix_users_first_name_unaccent_trgm`, `ix_users_last_name_unaccent_trgm`, `ix_professors_department_unaccent_trgm`, `ix_professors_areas_unaccent_trgm` (preko `f_unaccent_array`), `ix_subjects_name_unaccent_trgm`. NE indeksiramo `users.email` ni `subjects.code` (oba su ASCII-only po dizajnu).
> - **Refactor `backend/app/services/search_service.py`:** `if q:` blok prebačen sa plain `User.first_name.ilike(...)` na `func.f_unaccent(User.first_name).ilike(func.f_unaccent(needle))`; obe strane idu kroz isti wrapper za simetričan rezultat. Dodato pretraživanje preko `Professor.areas_of_interest` (kroz `func.f_unaccent_array`) — bilo je gap u prethodnoj implementaciji, sada je `vestacka` query matchuje `Veštačka inteligencija` u oblastima profesora. `Subject.code` ostaje plain ILIKE (ASCII).
> - **Refactor `backend/app/services/admin_user_service.py`:** `list_users` `if q:` blok prebačen na `func.f_unaccent(User.first_name/last_name).ilike(func.f_unaccent(needle))`; `User.email` ostaje plain ILIKE jer su email-ovi ASCII-only po whitelist domenima (`*@fon.bg.ac.rs`, `*@student.fon.bg.ac.rs` itd.). Verifikovano: admin search "petrovic" matchuje i ASCII "Petar Petrovic" i dijakrit "Milovan Petrović".
> - **Edge case bezbednost:** wrapper je `STRICT` — NULL ulaz vraća NULL bez egzekucije (sigurniji semantik za nullable kolone). Needle ide kao parametrizovan bind kroz SQLAlchemy `func.f_unaccent(needle)`, nema SQL injection rizika.
> - **Migracija je idempotentna:** `CREATE EXTENSION IF NOT EXISTS unaccent` (radi i ako je ekstenzija pre-instalirana van migracija — što je bilo stanje u dev kontejneru). Downgrade simetričan: drop indeksi → drop funkcije → `DROP EXTENSION IF EXISTS pg_trgm` + `DROP EXTENSION IF EXISTS unaccent`. Verifikovano `alembic upgrade head → alembic downgrade -1 → alembic upgrade head` ciklus čisto.
> - QA: novi **`scripts/integration_tests/test_step_47_unaccent.py`** — 7 scenarija: (1) psql sanity `f_unaccent('Đorđević')='Djordjevic'`, `f_unaccent('Šljivić')='Sljivic'`, no-op „Stefan"; (2) student search „Petrovic" → matchuje seed `profesor1@fon.bg.ac.rs` (Milovan Petrović); (3) student search „djordjevic" → matchuje test prof „Đorđe Đorđević" (verifikuje `replace + unaccent` kompoziciju); (4) ASCII no-op „Stefan" → matchuje „Stefan Mladenović"; (5) search „vestacka" → match preko `areas_of_interest='Veštačka inteligencija'`; (6) admin `/admin/users` search „petrovic" → matchuje „Petrović"; (7) `EXPLAIN ANALYZE` pokazuje `Bitmap Index Scan on ix_users_first_name_unaccent_trgm` + `ix_users_last_name_unaccent_trgm` (NE `Seq Scan`); **7/7 PASS** za 4.7s. Setup koristi prefiks `qa_a47_`/`prof_a47_` za idempotent cleanup, kreira test profesore kroz `POST /admin/users` + nadgrađuje `professors.department/areas_of_interest` direktnim SQL-om (admin endpoint ne pokriva ta polja, dopune se posle preko `PUT /professors/profile`).
> - **Bug iz §3.1 punkt 2 (`ilike ne hvata Petrović za Petrovic`) prebačen u §3.2 (rešeno).**
> - **Prompt 1 status:** 8/10 stvarnih koraka 100% gotov; KORAK 9 (Google PSE proxy) svesno skinut iz Prompta 1 (premešten u Prompt 2 ako bude potreban). Sledeći prompt (`CURSOR_PROMPT_2_FEATURE_EXPANSION.md`) pokriva production infra, testovi, push notifikacije, group consultations.
>
> **Izmene od v2.7 → v2.8 (KORAK 4.6 — Reminder Celery beat + send_appointment_cancelled task fix):**
> - Backend: završen Korak 4.6 (24h + 1h reminder beat dispatcher-i sa Redis idempotency-jem; lead student + profesor + svi CONFIRMED participants dobijaju email + in-app `APPOINTMENT_REMINDER_24H` ili `_1H`). Postojeći `notifications.send_appointment_reminder` task je proširen sa fan-out logikom umesto razdvajanja na 2 task poziva — atomičnost + jedinstveni Redis idempotency ključ + lead se dedupliše ako figuriše i u `participants` listi.
> - **Latentni bug iz PRD §5.2 popravljen:** `booking_service.cancel_appointment` (student cancel flow) NIKADA nije dispečovao Celery task — profesor nije saznavao da je student otkazao. `professor_portal_service.cancel_request` je reuse-ovao `send_appointment_rejected` što je bilo semantički pogrešno (reject ≠ cancel poruka u email body-ju). Oba flow-a sada dispečuju **novi** `notifications.send_appointment_cancelled` task sa `cancelled_by_role: str` argumentom (`"STUDENT"` ili `"PROFESOR"` — string, ne enum, jer je task internal API). Onaj ko otkazuje je excluded iz fan-out-a (student koji je otkazao ne dobija notif samog sebe).
> - Novi task modul **`backend/app/tasks/reminder_tasks.py`** sa 2 sync Celery wrapper-a (`dispatch_reminders_24h`, `dispatch_reminders_1h`) i jednim async helper-om `_dispatch_reminders_async` koji: (1) skenira `appointments JOIN availability_slots` za `status=APPROVED` u prozoru `[now+lower, now+upper]`, (2) za svaki red pokušava Redis `SET NX EX` na ključu `reminder:{hours}:{appointment_id}` — ako vrati `None` (ključ već postoji), skip; ako uspe, dispečuje `send_appointment_reminder.delay(...)`, (3) loguje strukturisan summary `scanned=N dispatched=M skipped=K`. Cross-loop fix: koristi `_fresh_db_session` (NullPool, KORAK 7 helper) i `_new_redis` (fresh per-call client) iz `notifications.py`.
> - **Vremenski prozori i TTL-ovi:** 24h dispatcher prozor `[now+23h30m, now+24h30m]` (60 min širok, beat tick svakih 30 min → svaki termin pokriven bar jednim tick-om), TTL idempotency ključa 25h. 1h dispatcher prozor `[now+45m, now+1h15m]` (30 min širok, beat tick svakih 15 min), TTL 2h. Edge case verifikovan: termin `now+24h05m` ne ulazi u prozor sad, ali ulazi 30 min kasnije kada je `now+23h35m` (u prozoru); idempotency ključ TTL 25h sprečava treći beat tick (60 min kasnije).
> - **Beat schedule** u `celery_app.py::beat_schedule` proširen sa 2 nova ulaza: `dispatch-reminders-24h-every-30-minutes` (`crontab(minute="*/30")`) i `dispatch-reminders-1h-every-15-minutes` (`crontab(minute="*/15")`). Postojeća 2 ulaza (`detect-no-show-every-30-minutes`, `process-waitlist-offers-every-5-minutes`) ostaju netaknuta. `celery_app.include` proširen sa `"app.tasks.reminder_tasks"` (autodiscover novog modula pri startup-u).
> - **Defense-in-depth status guard:** dispatcher SQL filter (`Appointment.status == APPROVED`) je primarni guard, ali i sam `send_appointment_reminder` task ima drugi check (`if appointment.status != APPROVED: return False`) za race scenario kada profesor otkaže termin između dispatcher SELECT-a i task pickup-a (par stotina ms). Redis ključ ostaje set-ovan (race protected), ali fan-out se ne dešava → admin u worker logu vidi `skip` debug poruku.
> - **Per-recipient try/except u oba task-a** (`send_appointment_reminder` + `send_appointment_cancelled`): SMTP ili Redis ispad za jednog primaoca ne sme da pokvari fan-out ostalim primaocima (isti pattern kao `broadcast_tasks.fanout_broadcast` iz Faze 4.5). Worker log nosi `appointment_id`+`recipient_id`+`hours_before`/`cancelled_by_role`+`error` kroz Python logging `extra={...}` argument za structured logging dashboard-e.
> - **Pattern konzistentnost — service commit + dispatch:** `booking_service.cancel_appointment` i `professor_portal_service.cancel_request` su prebačeni sa "samo flush()" pattern-a (oslanjao se na `get_db()` auto-commit) na "explicit `await db.commit()` + `send_appointment_cancelled.delay(...)` pre povratka" — isti pattern kao `broadcast_service.dispatch` iz Faze 4.5. Bez ovoga, Celery worker bi mogao da pokupi task pre nego što DB commit završi i SELECT bi promašio appointment red. Route handler-i u `students.py` / `professors.py` ostaju netaknuti (samo pozivaju service).
> - **`_collect_recipients` helper** u `notifications.py` — vraća `list[(user_id, email, full_name)]` u redosledu lead/professor/non-lead-CONFIRMED-participants sa dedupom po `user_id` (lead se ne dispečuje 2x ako je u `participants` sa is_lead=True — što je default flow iz `booking_service.create_appointment`). `exclude_user_ids` argument koristi `send_appointment_cancelled` da preskoči onog ko je otkazao. `_get_appointment` je proširen `selectinload(Appointment.participants).selectinload(AppointmentParticipant.student)` da fan-out može da dobije `student.email` bez dodatnog DB hop-a.
> - QA: novi **`scripts/integration_tests/test_step_46_reminders.py`** — 7 scenarija (termin u 24h prozoru → 2 REMINDER_24H notif sa lead+prof; termin van prozora → 0 notif; PENDING termin u prozoru → 0 notif (status guard); idempotency: drugi dispatch → 0 dodatnih notif (Redis NX skip); termin u 1h prozoru → 2 REMINDER_1H notif sa `data.hours_before=1`; student cancel: HTTP 200 + profesor 1 CANCELLED notif (`cancelled_by_role=STUDENT`) + lead 0 (excluded) + DB status=CANCELLED; profesor cancel: HTTP 200 + student 1 CANCELLED notif (`cancelled_by_role=PROFESOR`) + profesor 0 (excluded) + `rejection_reason` zapisan); **7/7 PASS** za 32s. Setup koristi `online_link='S46_E2E_TEST_SLOT'` marker za cleanup test slot-ova (slot nema FK na user-a), 6 fresh appointmenata sa eksplicitnim UUID-evima, dispatcher trigger preko `docker exec studentska_backend python -c "...delay()"`, Redis idempotency ključevi se brišu eksplicitno za test ID-eve pre i posle run-a.
> - E2E manualno verifikovano: dispatcher 24h kroz `delay()` nad APPROVED termin sa `slot_datetime=now+24h` → worker log `dispatch_reminders_24h: window=[now+23h30m, now+24h30m] scanned=1 dispatched=1 skipped=0` → `send_appointment_reminder` sub-task `targeted=2 sent=2` (lead + profesor) → 2 reda u `notifications` sa `type=APPOINTMENT_REMINDER_24H` i `data.hours_before=24`; drugi dispatch_24h trigger → `scanned=1 dispatched=0 skipped=1` (Redis SET NX vraća None) → 0 dodatnih notif redova; 1h dispatcher (`slot_datetime=now+1h`) → `targeted=2 sent=2` sa REMINDER_1H tipom; HTTP DELETE `/students/appointments/{id}` (preko admin impersonation studenta) → service commit + dispatch → `cancelled_by=STUDENT targeted=1 sent=1` (samo profesor); HTTP POST `/professors/requests/{id}/cancel` (preko admin impersonation profesora) → `cancelled_by=PROFESOR targeted=1 sent=1` (samo lead student). **Acceptance kriterijumi za KORAK 8 (Faza 4.6) zadovoljeni 100%.**
>
> **Izmene od v2.6 → v2.7 (KORAK 4.5 — Admin strikes + broadcast fan-out):**
> - Backend: završen Korak 4.5 (admin može da pregleda studente sa strike poenima i override-uje aktivnu blokadu uz audit + BLOCK_LIFTED notif; admin može da pošalje globalno obaveštenje ciljano po roli/fakultetu sa per-user IN_APP+EMAIL fan-out-om kroz Celery task). Frontend tipovi i UI komponente (`StrikeRow`, `UnblockRequest`, `BroadcastTarget`, `BroadcastChannel`, `BroadcastRequest`, `BroadcastResponse`) zaključani su pre ovog koraka — backend je 1:1 ispoštovao `frontend/types/admin.ts`.
> - **Frontend ugovor je ispravio prompt:** target enum NEMA `YEAR` (samo `ALL`/`STUDENTS`/`STAFF`/`BY_FACULTY`); polje je `student_full_name` (ne `full_name`), `blocked_until` (ne `active_block_until`), `removal_reason` (ne `reason`/`admin_note`); channels su isključivo `IN_APP`/`EMAIL` (NEMA `PUSH` u V1). Pitanje "YEAR=NotImplemented" iz initial prompta je otpalo.
> - Migracija **`20260427_0003_broadcasts.py`** — nova tabela `broadcasts` (id UUID PK, admin_id FK users RESTRICT, title VARCHAR(120), body TEXT, target VARCHAR(20), faculty VARCHAR(10) NULL, channels VARCHAR(50)[], recipient_count INTEGER, sent_at TIMESTAMPTZ DEFAULT now()) sa indeksima `ix_broadcasts_admin_id` i `ix_broadcasts_sent_at` (DESC). `VARCHAR(50)[]` umesto `TEXT[]` zbog eksplicitnog limita + čistijeg `\d broadcasts` u psql-u. NEMA CHECK constraint-a na target/faculty — Pydantic V2 `BroadcastRequest` već striktno validira na entry point-u, DB-level constraint bi udvostručio logiku.
> - **`AuditAction` enum proširen** sa 2 nove vrednosti: `STRIKE_UNBLOCKED` i `BROADCAST_SENT` (ukupno 4 vrednosti). Migracija NIJE potrebna — `audit_log.action` je `Text` kolona (isti pattern kao `NotificationType`). `NotificationType.BLOCK_LIFTED` i `BROADCAST` su VEĆ postojali u enum-u od Faze 4.2 — nije bilo potrebe za novim članovima.
> - **3 nove Pydantic V2 šeme** u `backend/app/schemas/admin.py`: `StrikeRow` (student_id/student_full_name/email/faculty/total_points>=1/blocked_until|None/last_strike_at|None), `UnblockRequest` (removal_reason min_length=10 max_length=2000 — mirror frontend zod schema), `BroadcastRequest` (title max=120, body min=10, target Literal, faculty Faculty|None, channels list[Literal] min_length=1) sa **`model_validator`** koji garantuje `target=BY_FACULTY ↔ faculty not None` i tiho nuluje `faculty` za ne-`BY_FACULTY` target (defense u backend-u protiv lažnog "FON" u history-u na ALL broadcast-u). `BroadcastResponse` mapira ORM `Broadcast` na frontend ugovor sa **denormalizacijom `admin_id` → `sent_by`**.
> - Novi ORM model **`backend/app/models/broadcast.py`** (mapiran na `broadcasts` tabelu, relationship `admin: User` sa `foreign_keys=[admin_id]`). Bez `TimestampMixin` — broadcast je immutable nakon dispatch-a, nema `updated_at`.
> - Novi servis **`backend/app/services/strike_admin_service.py`** — `list_strike_rows(db)` agregira `strike_records` po studentu (`SUM(points)` + `MAX(created_at)`) HAVING SUM>=1, LEFT JOIN-uje sa `student_blocks` za `blocked_until`, sortira blokirane prve (CASE on `blocked_until > now()`), pa total_points DESC, pa last_strike_at DESC NULLS LAST. **Filter `total_points >= 1` (ne samo aktivno blokirani)** zato što frontend `strikes-table.tsx` disabled-uje "Odblokiraj" dugme kad je `!blocked_until && total_points === 0` — admin mora da vidi i 1-2 poena (preventivno praćenje pre blokade na 3). UI semantika: vraćamo `blocked_until` kao None ako je u prošlosti (istorijske/admin-override blokade ostaju u tabeli sa `blocked_until <= now()`, ali UI badge se pokazuje samo za aktivne).
> - **Strike unblock reuse:** postojeći `strike_service.unblock_student` (Faza 3.1) se zove 1:1 — UPDATE `student_blocks` setuje `blocked_until=now()` + upiše `removed_by`/`removal_reason`. **NIŠTA se ne briše** (StrikeRecord-i ostaju, total_points ostaje — admin override znači "odblokiran", ne "očišćen sa 0 poena"). Idempotent za studenta koji nikad nije bio blokiran (vraća None → ruta vraća 200 "nije bio blokiran" bez audit-a/notif-a).
> - Novi servis **`backend/app/services/broadcast_service.py`** — `_resolve_user_ids(db, target, faculty)` mapira target enum vrednost na `WHERE` klauzu (ALL → svi aktivni ne-ADMIN; STUDENTS → role=STUDENT; STAFF → role IN (PROFESOR, ASISTENT); BY_FACULTY → faculty=$f + ne-ADMIN). `dispatch(db, admin_id, payload, ip)` → resolve_user_ids → INSERT broadcast row → `audit_log_service.log_action(BROADCAST_SENT)` → commit → `fanout_broadcast.delay(...)` posle commit-a (sprečava da Celery worker pokupi task pre nego što DB završi commit i čita `recipient_count=0` iz tek-nekompletiranog reda). `list_history(db, limit=50)` koristi `ix_broadcasts_sent_at` indeks.
> - Novi Celery task **`backend/app/tasks/broadcast_tasks.py::fanout_broadcast`** — JEDAN task za ceo broadcast (NE per-user sub-task) zbog argumenta da je 1 task vs 200 sub-task-ova bolji za broker latenciju + retry granularnost + per-user error izolaciju. **Per-user IN_APP create i EMAIL send su SVAKI u svom `try/except` sa per-user `_log.warning`-om** — ako 5 od 200 user-a padne, ostalih 195 dobija notif/email, log nosi 5 grešaka sa `broadcast_id`+`user_id`, task vraća `{"sent": int, "failed": int}` ali NE re-raises. **`recipient_count` u `broadcasts` tabeli OSTAJE INSERT-ovan kao "ciljani" broj** (resolve-ovan PRE Celery task-a) — NE smanjuje se na "delivered" broj (overengineering za V1, dodaje se u Prompt 2 ako bude potrebno).
> - **Celery `app.celery_app::celery_app.conf.include`** proširen sa `"app.tasks.broadcast_tasks"` (broadcast task se autodiscover-uje pri startupu).
> - **Bonus fix u `tasks/notifications.py`:** dodat helper `_fresh_db_session()` (`@asynccontextmanager`) koji kreira **per-task fresh `AsyncEngine` sa `NullPool`** + `async_sessionmaker` + dispose-uje engine na izlasku. **`_create_inapp` je migriran sa `AsyncSessionLocal` na `_fresh_db_session`** (fix-uje cross-loop bug iz deljenog QueuePool-a — asyncpg konekcije su VEZANE za event loop u kome su otvorene, pa drugi `asyncio.run()` u Celery worker procesu pucao sa `RuntimeError: Future attached to a different loop`). NullPool kreira fresh konekciju per-checkout u **trenutnom** event loop-u i discard-uje na release. `worker_prefetch_multiplier=1` garantuje da nema paralelnih taskova u istom procesu pa NullPool overhead je zanemarljiv. Svi postojeći taskovi (send_appointment_*, send_strike_added, send_block_activated, send_waitlist_offer, send_document_request_*) automatski profitiraju kroz shared `_create_inapp`. Moj novi `send_block_lifted` task takođe koristi `_fresh_db_session` za User SELECT.
> - Novi Celery task **`notifications.send_block_lifted`** — email + in-app `BLOCK_LIFTED` notif (subject "Blokada naloga je skinuta", body sa `removal_reason`); zove se iz `POST /admin/strikes/{id}/unblock` posle commit-a.
> - **Novih 4 ruta u `backend/app/api/v1/admin.py`** — sekcija `# ── Strikes + Broadcast (Faza 4.5) ──`:
>   - `GET /admin/strikes` (CurrentAdmin) → `list[StrikeRow]` (bare array, no paginate; sortirano DB-side)
>   - `POST /admin/strikes/{student_id}/unblock` (CurrentAdmin, body=`UnblockRequest`) → `MessageResponse`; flow: load student (404 ako ne postoji), call `strike_service.unblock_student`, ako `block is None` → 200 "nije bio blokiran" (no-op, no audit/notif); inače `audit_log_service.log_action(STRIKE_UNBLOCKED, impersonated_user_id=student_id)` + commit + `send_block_lifted.delay(...)` posle commit-a
>   - `POST /admin/broadcast` (CurrentAdmin, body=`BroadcastRequest`) → `BroadcastResponse` (status_code=201); poziva `broadcast_service.dispatch` koji unutra commituje + delay-uje Celery task
>   - `GET /admin/broadcast` (CurrentAdmin) → `list[BroadcastResponse]` (poslednjih 50, DESC po sent_at)
>   - Helper `_broadcast_to_response(b)` denormalizuje ORM `admin_id` → frontend `sent_by` polje
> - QA: novi **`scripts/integration_tests/test_step_45_strikes_broadcast.py`** — 7 scenarija (RBAC student → 403 na sve 4 nove rute; GET /strikes vraća A blokiran + B preventivno + C odsutan, sortirano blokirani prvi, shape STRIKE_KEYS, A.blocked_until!=None, B.blocked_until==None; POST unblock happy path = 200 + DB blocked_until<=now + 1 audit STRIKE_UNBLOCKED + BLOCK_LIFTED notif; POST unblock idempotent na ne-blokiranog studenta = 200 "nije bio blokiran" + 0 audit + 0 notif; POST broadcast STAFF = 201 + recipient_count=N PROFESOR+ASISTENT + 1 audit BROADCAST_SENT + per-user notif samo za STAFF (0 student/admin); POST broadcast BY_FACULTY=FON = 201 + recipient_count=FON_only + svi notif FON, 0 ETF; POST broadcast 422 za BY_FACULTY bez faculty + prazan channels + invalid target "YEAR"); **7/7 PASS** za 17s. Setup TRUNCATE-uje `audit_log` + `broadcasts`, cleanup briše prefiks `s45_e2e_`.
> - E2E manualno verifikovano (clean DB run): admin → seed StrikeRecord+StudentBlock za studenta → GET /strikes vraća tačan StrikeRow → POST /unblock sa reason 50+ chars → DB block.blocked_until UPDATE-ovan + 1 audit STRIKE_UNBLOCKED row + BLOCK_LIFTED notif u DB-u (Celery task `succeeded in 0.12s`); admin → POST /broadcast target=STAFF channels=[IN_APP] → 4 PROFESOR/ASISTENT useri primljeni notif u Celery `targeted=4 sent=4 failed=0`, 1 audit BROADCAST_SENT row, GET /broadcast pokazuje history red sa recipient_count=4. **Acceptance kriterijumi za KORAK 7 zadovoljeni 100%.**
>
> **Izmene od v2.5 → v2.6 (KORAK 4.4 — Impersonation + audit log):**
> - Backend: završen Korak 4.4 (admin može da impersonira drugog ne-admin korisnika sa 30-min JWT bez refresh-a + auditom svih start/end događaja sa IP-om). Frontend tipovi i UI komponente (`ImpersonationBanner`, `useImpersonationStore`) zaključani su pre ovog koraka — backend je 1:1 ispoštovao `frontend/types/admin.ts::ImpersonationStartResponse|ImpersonationEndResponse|AuditLogRow`.
> - Migracije NEMA — `audit_log` tabela već postoji u `alembic/versions/20260423_0001_initial_schema.py` (kolone `admin_id`/`impersonated_user_id`/`action TEXT`/`ip_address INET`/`created_at TIMESTAMPTZ`), savršen 1:1 sa frontend `AuditLogRow`. Štedi se nepotrebna migracija 0003.
> - Novi `class AuditAction(str, Enum)` u `backend/app/models/enums.py` — vrednosti `IMPERSONATION_START`, `IMPERSONATION_END`. Isti pattern kao `NotificationType` (Text kolona u DB, Python enum strikt validacija na servisnom sloju, dodavanje novih akcija ne traži migraciju).
> - Nova konfiguracija `IMPERSONATION_TOKEN_TTL_MINUTES: int = 30` u `core/config.py`. `core/security.py::create_access_token(data, expires_minutes=None)` proširen opcionim TTL override-om — back-compat sa svim postojećim pozivima.
> - `core/dependencies.py::get_current_user` proširen `request: Request` parametrom; čita `imp`/`imp_email`/`imp_name` claim-ove iz payload-a, smešta ih na `request.state` (`is_impersonation`, `original_admin_email`, `original_admin_name`) **i** kao in-memory atribute na User objekat (`_is_impersonated`, `_impersonated_by_email`, `_impersonated_by_name`) — za sve servise koji već primaju `current_user: User` bez novog dependency hop-a. **Dakle za imp token, `current_user` JE TARGET, ne admin** (per `docs/websocket-schema.md §6`).
> - Novi `core/dependencies.py::get_current_admin_actor` + `CurrentAdminActor` annotated alias — vraća **pravog admina** i kad je token regularan (rola=ADMIN) i kad je imp token (resolve preko `imp_email` claim-a). Postoji **odvojeno** od `require_role(ADMIN)` da bi ~30 postojećih admin ruta ostalo netaknuto. Koristi se samo za 2 impersonation-related rute.
> - **Pitanje 5 odgovor:** ako admin tokom impersonation klikne `/admin/*`, `CurrentAdmin` (preko `require_role(ADMIN)`) striktno proverava `current_user.role == ADMIN` i daje 403. **NE pravimo backdoor kroz `imp` claim** — to bi pretvorilo imp token u full admin token za 30 min, što bi pokvarilo celu logiku ograničenog radius-a. Sidebar prirodno štiti UX (tokom imp se renderuje target-ova navigacija, admin sidebar se ne vidi).
> - Nova Pydantic V2 šema u `backend/app/schemas/admin.py` (dodato 4 klase): `ImpersonatorSummary` (id/email/first_name/last_name), `ImpersonationStartResponse` (access_token/token_type=bearer/expires_in=1800/user/impersonator/imp_expires_at), `ImpersonationEndResponse` (access_token/token_type/expires_in/user), `AuditLogRow` (id/admin_id/admin_full_name/impersonated_user_id/impersonated_user_full_name/action/ip_address/created_at). Sve poklopljene reč-za-reč sa `frontend/types/admin.ts`.
> - Novi servisi: `backend/app/services/impersonation_service.py` (`start_impersonation` sa validacijama: admin role, target postoji + active, no self-imp, no admin-on-admin; `end_impersonation` idempotentno; `_issue_impersonation_token` ubacuje 3 imp claim-a + 30-min TTL); `backend/app/services/audit_log_service.py` (`log_action` flush bez commit-a, `list_entries` sa eager-loadom admin/impersonated_user relationship-a + datum range + exact action match + default limit 200, `get_active_impersonation_target` helper za re-impersonate flow).
> - Novih 3 ruta u `backend/app/api/v1/admin.py` — `POST /admin/impersonate/end` (deklarisana **PRE** parametrizovane `/{user_id}` jer FastAPI matche-uje rute po declaration order; koristi `CurrentAdminActor` da radi sa oba tipa tokena), `POST /admin/impersonate/{user_id}` (koristi `CurrentAdmin` — admin sa aktivnim imp tokenom dobija 403, mora prvo "Izađi"), `GET /admin/audit-log` (filteri: `admin_id`/`action`/`from_date`/`to_date`, exact match na action). Helper `_client_ip(request)` čita `X-Forwarded-For` → `X-Real-IP` → `request.client.host` (nginx prosleđuje sva 3 header-a per `infra/nginx/nginx.conf`).
> - **Re-impersonate flow (admin u imp na A → klikne na B):** backend `start_impersonation` automatski upiše `IMPERSONATION_END(A)` pa `IMPERSONATION_START(B)` u istoj transakciji (jedan rollback briše oboje). Detekcija kroz `audit_log_service.get_active_impersonation_target(admin)` koji čita poslednji audit red za admina i proverava da li je START bez END-a. Frontend je ovo orchestrate-uje slanjem **regularnog admin tokena** (sačuvanog u `useImpersonationStore.originalUser` snapshot-u) na `/impersonate/{B}`.
> - Frontend WS hot-swap: **NULL touch potreban** — i `frontend/components/notifications/notification-stream.tsx` i `frontend/lib/hooks/use-chat.ts` već imaju `accessToken` u `useEffect` dep array-u (linije 157 i 181 respektivno), pa pri token swap-u (admin → imp → admin) automatski close + reconnect sa novim tokenom kroz `createNotificationSocket`/`createChatSocket` (oba imaju eksplicitni `.reconnect(nextToken)` API koji nismo morali ni da pozovemo — sam re-mount efekta to radi). `docs/websocket-schema.md §6.4` je tačan: WS handler na backendu uvek koristi `sub` claim, što za imp token znači target-a, što je tačno ponašanje za notif/chat stream tokom impersonation-a.
> - QA: novi `scripts/integration_tests/test_step_44_impersonation.py` — 8 scenarija (RBAC student→403 na sve 3 rute, happy start sa shape + JWT claims + 1 audit row, end vraća admin token bez imp claim-a + audit END row, re-impersonate A→B sa auto END+START u istoj transakciji, validation 400/404 — self/admin-on-admin/inactive/non-existent, IP capture iz X-Real-IP, audit log filteri exact-match action + admin_id + future from_date, expired imp token vraća 401 na svim rutama bez auto-refresh-a); **8/8 PASS**.
> - E2E manualno verifikovano (clean DB run): login admin → impersonate → imp token decode pokazuje sve 3 imp claim-a + TTL=30min + sub=target → audit log 1 START sa IP=172.18.0.1 (nginx gateway) → impersonate/end → end token decode pokazuje sub=admin + bez imp claim-a → final audit log 2 reda. **Acceptance kriterijumi za KORAK 6 zadovoljeni 100%.**
>
> **Izmene od v2.4 → v2.5 (KORAK 4.3 — Admin users CRUD + bulk CSV import):**
> - Backend: završen Korak 4.3 (admin user CRUD + bulk CSV import samo za studente)
> - Nova Pydantic V2 šema `backend/app/schemas/admin.py` — `AdminUserCreate` (password required, frontend ugovor), `AdminUserUpdate` (Partial sa `is_active?`), `AdminUserResponse` (mirror `frontend/types/admin.ts` = `UserResponse` alias, BEZ `student_index_number`/`study_program`/`enrollment_year`), `BulkImportRow`, `BulkImportPreview`, `BulkImportResult`. Sve šeme reč-za-reč usklađene sa `frontend/types/admin.ts`.
> - Novi servis `backend/app/services/admin_user_service.py` — `list_users()` (ILIKE pretraga + role/faculty filteri, BEZ unaccent-a — to ostaje za migraciju 0003 u Korak 10), `get_user/create_user/update_user/deactivate_user` (soft delete), `bulk_import_preview/confirm` (UTF-8 BOM tolerant CSV, header `ime,prezime,email,indeks,smer,godina_upisa` per PRD §4.1, samo studentski domeni `*@student.fon.bg.ac.rs|*@student.etf.bg.ac.rs`).
> - Hibridni welcome flow: `auth_service._create_reset_token(db, user, ttl_seconds)` faktorisan iz `forgot_password()` da se reuse-uje sa TTL=7d za welcome link; novi helper `core/email.send_welcome_email_with_reset_link()` šalje Celery task sa `{FRONTEND_URL}/reset-password?token=...` linkom (bez novog reset frontend ekrana — postojeći se reuse-uje). Nova konfiguracija `WELCOME_RESET_TOKEN_TTL_DAYS: int = 7` u `core/config.py`.
> - Novih 7 ruta u `backend/app/api/v1/admin.py` — `GET /users` (ILIKE q+role+faculty), `GET /users/{id}`, `POST /users` (single, šalje welcome email), `PATCH /users/{id}` (email+password locked, frontend ugovor), `POST /users/{id}/deactivate` (soft delete preko POST jer je u frontend ugovoru, ne DELETE), `POST /users/bulk-import/preview` (multipart `file`), `POST /users/bulk-import/confirm` (re-validira CSV iz frontend re-upload-a — frontend ne pamti `preview_id`, vidi user prompt I-5 odgovor C).
> - Bulk import transakcija: confirm radi kroz jedan `AsyncSession` flush — ako bilo koji insert padne, `get_db()` rollback grana ponǐsti sve i nema raspolovljenog stanja. ``failed=0`` u happy path-u (re-validacija odbacuje invalid/duplicates pre INSERT-a). Svaki kreirani student dobija welcome email kroz Celery task posle uspešnog flush-a.
> - Frontend touch (1 linija): `frontend/components/admin/bulk-import-dialog.tsx` — stale tekst `email, first_name, last_name, role, faculty, password` zamenjen sa PRD §4.1 formatom `ime, prezime, email, indeks, smer, godina_upisa` (admin više neće biti zbunjen pri uploadu).
> - QA: novi `scripts/integration_tests/test_step_43_admin_users.py` — 7 scenarija (RBAC 403, single create + welcome email task verifikacija u Celery worker logu, PATCH partial, deactivate + 403 na login, validation 422/409/404, bulk preview kategorisanje 5/2/1, bulk confirm + 5 welcome email task-ova); 7/7 PASS. Fixture `scripts/fixtures/test_bulk_users.csv` (5 valid + 1 in-file dup + 1 invalid domain — test runtime dodaje 1 in-DB dup za 8-redni 5/2/1 raspored).
> - Pattern potvrđen i dokumentovan: kad prompt iz CURSOR_PROMPT-a kontradiktora frontend ugovoru, **frontend pobeđuje** (ovde je primenjeno na: PATCH umesto PUT za update; POST `/deactivate` umesto DELETE; frontend re-upload-uje CSV na confirm umesto preview_id u Redis-u; `AdminUserResponse` ne sadrži student-specific polja).
>
> **Izmene od v2.3 → v2.4 (KORAK 4.2 — Notifications REST + WS stream):**
> - Backend: završen Korak 4.2 (in-app notifikacije: 4 REST ruta + per-user WS stream + Celery proširenje)
> - Novi `class NotificationType(str, Enum)` u `backend/app/models/enums.py` — 16 vrednosti uparenih red-za-red sa `frontend/types/notification.ts` (kolona `notifications.type` ostaje VARCHAR(50), nema migracije)
> - Nova Pydantic V2 šema `backend/app/schemas/notification.py` — `NotificationResponse`, `UnreadCountResponse` (frontend list endpoint vraća goli array, ne paginated wrapper)
> - Novi servis `backend/app/services/notification_service.py` — `create()`, `list_recent()`, `mark_read()`, `mark_all_read()`, `get_unread_count()` (Redis-first sa DB fallback i lazy backfill); envelope helperi za `notification.created`, `notification.unread_count`, `system.ping`, `system.error` (schema §4 + §3)
> - Novi router `backend/app/api/v1/notifications.py` sa 4 REST endpoint-a (`GET /`, `GET /unread-count`, `POST /{id}/read`, `POST /read-all`) + native FastAPI `WS /stream` (per-user kanal `notif:pub:{user_id}`, kanal iz JWT `sub` claim-a, implicitna RBAC; 25s heartbeat / 60s timeout, identičan pattern kao chat WS iz 4.1)
> - `backend/app/main.py` — `notifications.router` registrovan pod `/api/v1/notifications`
> - `backend/app/tasks/notifications.py` — svih 8 Celery email taskova prošireno: pored email-a sad kreiraju in-app notif preko `notification_service.create()` (helper `_create_inapp` otvara fresh `aioredis.Redis` per `asyncio.run()` da izbegne cross-loop greške, isti pattern kao `waitlist_tasks.py`); mapiranje 8→9 (reminder se grana na `APPOINTMENT_REMINDER_24H` / `_1H`)
> - Frontend cleanup: `lib/ws/notification-socket.ts` reconnect schedule prebačen sa defanzivnog [1s/5s/30s × 3] na schema §7.2 standard `[1, 2, 4, 8, 30]s ±20% jitter × 5` (uparen sa chat-socket.ts); `lib/hooks/use-notifications.ts` skinut defanzivni 5-min polling fallback (uveo se dok je 4.2 endpoint vraćao 404) — sad clean conditional `refetchInterval = wsConnected ? false : 30s`
> - QA: novi `scripts/integration_tests/test_step_42_notifications.py` — 7 scenarija (auth 4401, RBAC izolacija, real-time delivery <2s, REST endpointi, heartbeat 25s, validation no-close, reconnect terminal vs normal); 7/7 PASS
> - E2E verifikovano: profesor approve PENDING zahtev → student-ov otvoreni WS prima `notification.created` + `notification.unread_count` envelope za **828ms** (acceptance < 2s ✓)
>
> **Izmene od v2.2 → v2.3 (KORAK 4.1 — Chat WebSocket):**
> - Backend: završen Korak 4.1 (chat WS + Redis Pub/Sub `chat:pub:{appointment_id}` kanal)
> - Novi `backend/app/core/ws_deps.py::decode_ws_token` — vraća User|None bez raise-a, caller bira close kod (4401)
> - `backend/app/api/v1/appointments.py` proširen sa `WS /{id}/chat` handler-om (3 concurrent task-a: recv_loop / fanout_loop / heartbeat_loop; close kodovi 4401/4403/4404/4409/4430/4500; per-sender rate limit Redis SET NX PX 500ms)
> - `backend/app/services/chat_service.py` — `send_message` sa `redis=` parametrom radi DB INSERT + commit + publish u jednom prolazu (single source of truth za fan-out)
> - QA: `scripts/integration_tests/test_step_41_chat_ws.py` — 8 scenarija PASS

---

## 0. TL;DR — gde se NALAZIMO

- **Faza 0 (Infrastruktura):** ✅ kompletno
- **Faza 1 (Auth + email):** ✅ kompletno
- **Faza 2 (Stabilizacija + Shared frontend foundation):** ✅ kompletno
  - Korak 2.1 (bugovi): ✅ `waitlist_tasks.timedelta` import dodat, `celery-beat` koristi `celery.beat.PersistentScheduler`
  - Korak 2.2 + 2.3: frontend ima sav shell, sve API klijente, sve TanStack Query hookove i sve TS tipove
- **Faza 3 — Backend (HANDOFF2 zadatak):**
  - Korak 3.1 (Professor portal endpoints): ✅ kompletno (`/api/v1/professors/*`)
  - Korak 3.2 (Document requests, oba toka): ✅ kompletno
  - Korak 3.3 (Appointment detail + files + chat REST polling): ✅ kompletno
  - Korak 3.8 (Recurring slots ekspanzija — `recurring_group_id` + RRULE → N zapisa + grupno brisanje): ✅ kompletno
- **Faza 3 — Frontend:** ✅ sve stranice imaju kompletan UI; `/appointments/[id]` koristi WS chat (4.1) sa polling fallback-om
- **Faza 4 (Backend WS + admin + reminderi):**
  - **Korak 4.1 (Chat WebSocket + Redis Pub/Sub `chat:pub:{appointment_id}`): ✅ kompletno**
  - **Korak 4.2 (Notifications REST + per-user WS stream `notif:pub:{user_id}` + Celery in-app proširenje): ✅ kompletno**
  - **Korak 4.3 (Admin users CRUD + bulk CSV import sa welcome email reset link flow-om): ✅ kompletno**
  - **Korak 4.4 (Impersonation + audit log): ✅ kompletno**
  - **Korak 4.5 (Admin strikes + broadcast fan-out): ✅ kompletno**
  - **Korak 4.6 (Reminder Celery beat 24h + 1h, idempotency u Redis-u + multi-recipient fan-out + send_appointment_cancelled task fix): ✅ kompletno**
  - **Korak 10 (Migracija 0004 `unaccent` + `pg_trgm` + diakritik-insensitive search): ✅ kompletno**
- **Faza 4 — Frontend (4.7 admin UI, 4.8 documents+notif center):** ✅ kompletno
- **Faza 5:** Korak 5.2 (PWA) ✅; 5.3 (prod infra), 5.4 (testovi) ❌; 5.1 (Google PSE) ❌ (svesno skinut iz Prompta 1, prebačen u Prompt 2 ako bude potreban)
- **Faza 6 (Frontend finalni polish):** ✅ kompletno + Tailwind v3→v4 migracija (april 2026)
- **Prompt 2 (`CURSOR_PROMPT_2_DEMO_READY.md` — DEMO READY):**
  - **KORAK 1 (Web Push notifikacije — VAPID + push_subscriptions tabela + 3 REST rute + custom Service Worker + frontend toggle + fan-out hook u `notification_service.create`): ✅ kompletno** ← završeno u poslednjoj sesiji
  - KORAK 2 (Override notifikacije — profesorska blackout proširena sa appointment cancel + priority waitlist 14d + custom email body): ⏳ čeka
  - KORAK 3 (Asistent RBAC ojačan — `require_subject_assistant(subject_id)` + CRM rute provera): ⏳ čeka

**Prompt 1 KOMPLETNO završen (8/10 koraka stvarno urađeno, KORAK 9 PSE skinut).** Migracija 0004 pokriva diakritik-insensitive search — student koji kuca „Petrovic" sada nalazi „Milovan Petrović", „djordjevic" nalazi „Đorđević" (preko `replace(đ→dj) + unaccent` kompozicije), „vestacka" nalazi profesora sa `areas_of_interest=['Veštačka inteligencija']`. EXPLAIN ANALYZE pokazuje `Bitmap Index Scan on ix_users_first_name_unaccent_trgm` (NE Seq Scan).

**Prompt 2 KORAK 1 KOMPLETNO završen.** Web Push notifikacije rade end-to-end: VAPID javni/privatni par generiše `scripts/generate_vapid_keys.py`, migracija 0005 kreira `push_subscriptions` tabelu (UNIQUE per-user-endpoint, ON DELETE CASCADE), 3 REST rute (`GET /vapid-public-key` + `POST /subscribe` UPSERT + `POST /unsubscribe` idempotent), `notification_service.create()` ima fire-and-forget hook ka `push_service.send_push` (`asyncio.create_task` u FastAPI request handler-u, eksplicitan `await` u Celery task-u kroz flag `dispatch_push_in_background=False`), `push_service` šalje trimovan payload (title≤80, body≤140, deep link, type, tag) kroz `pywebpush + asyncio.to_thread`, 410 Gone čisti dead pretplate, quiet hours 22:00-07:00 CET filtruje non-urgent tipove. Frontend `usePushSubscription` hook + `<PushSubscriptionToggle />` UI + custom `frontend/worker/index.js` SW handle-uju push i notificationclick events sa deep link-om. **Integration test 6/6 PASS.** Acceptance kriterijumi 100%.

**Sledeći logični korak:** **KORAK 2 Prompta 2 (Override notifikacije)** — kad profesor kreira blackout u rangu sa već postojećim APPROVED appointment-ima: bulk CANCELLED + `send_appointment_cancelled.delay()` sa custom razlogom + dodavanje na prioritetnu waitlist (Redis Sorted Set, score=`-now_timestamp`, 14d expiry). Procena: ~1 dan, 2-3 iteracije.

---

## 1. STRUKTURA REPOZITORIJUMA (snimak 26. apr 2026)

```
Student_Platform_App/
├── CLAUDE.md                       ← jedini source of truth, čitati pre koda
├── HANDOFF2.md                     ← druga primopredaja Filip → Stefan (zaključno sa Fazom 2.1)
├── HANDOFF.md                      ← prva primopredaja (Faza 0 → 1)
├── CURRENT_STATE.md                ← stari snimak (pre Faze 2)
├── CURRENT_STATE2.md               ← OVAJ dokument (sledbenik)
├── CURSOR_FRONTEND_PROMPT.md       ← prompt koji je vodio Cursor kroz frontend
│
├── backend/
│   ├── Dockerfile                  ← python:3.12-slim + uvicorn --reload
│   ├── requirements.txt            ← FastAPI 0.111+, SQLAlchemy 2 async, Celery 5.4, Redis 5
│   ├── alembic.ini                 ← timezone=Europe/Belgrade
│   ├── celerybeat-schedule         ← runtime fajl (PersistentScheduler), gitignore-ovati
│   ├── alembic/
│   │   ├── env.py                  ← async setup
│   │   └── versions/
│   │       └── 20260423_0001_initial_schema.py   ← JEDINA migracija (sve 20 tabela + 9 enum tipova)
│   └── app/
│       ├── main.py                 ← registruje auth, students, professors, admin, **appointments**
│       ├── celery_app.py
│       ├── core/
│       │   ├── config.py
│       │   ├── database.py         ← async engine + AsyncSessionLocal + get_db()
│       │   ├── security.py         ← JWT, bcrypt 12 rounds, Redis Lua slot lock
│       │   ├── dependencies.py     ← CurrentUser/CurrentAdmin/CurrentProfesor/CurrentStudent
│       │   └── email.py
│       ├── models/                 ← 20 tabela u 16 fajlova (svi gotovi)
│       │   ├── enums.py            ← 9 PG ENUM-ova
│       │   ├── user.py / professor.py / subject.py
│       │   ├── availability_slot.py / appointment.py / file.py
│       │   ├── chat.py / crm_note.py / strike.py
│       │   ├── faq.py / notification.py / audit_log.py
│       │   ├── canned_response.py / document_request.py
│       │   └── password_reset_token.py
│       ├── schemas/
│       │   ├── auth.py                ← ✅
│       │   ├── student.py             ← ✅ (search, profile, booking, slots)
│       │   ├── professor.py           ← ✅ (slot+blackout+profile+requests+canned+faq+crm+assistants+RequestCancelRequest)
│       │   ├── document_request.py    ← ✅ (Create, ApproveRequest, RejectRequest, Response)
│       │   ├── appointment.py         ← ✅ (Faza 3.3: AppointmentDetailResponse, ChatMessage{Create,Response}, FileResponse, ParticipantResponse, ParticipantConfirmRequest)
│       │   ├── notification.py        ← ✅ (Faza 4.2)
│       │   ├── chat.py                ← ✅ (Faza 4.1)
│       │   └── admin.py               ← ✅ NOVO (Faza 4.3: AdminUser{Create,Update,Response}, BulkImport{Row,Preview,Result})
│       ├── services/
│       │   ├── auth_service.py                ← ✅
│       │   ├── search_service.py              ← ✅ (ilike, BEZ unaccent-a — vidi §6)
│       │   ├── booking_service.py             ← ✅ (Redis Lua lock, create/cancel/list)
│       │   ├── availability_service.py        ← ⚠️ create_slot pravi 1 zapis (recurring nije ekspandiran — Faza 3.8)
│       │   ├── waitlist_service.py            ← ✅ (Redis Sorted Set, issue_offer)
│       │   ├── strike_service.py              ← ✅ (LATE_CANCEL/NO_SHOW, blokade 14/21/+7d)
│       │   ├── professor_portal_service.py    ← ✅ (profile, requests, approve/reject/delegate, assistants, **cancel_request**)
│       │   ├── canned_response_service.py     ← ✅
│       │   ├── faq_service.py                 ← ✅
│       │   ├── crm_service.py                 ← ✅ (RBAC: PROFESOR + ASISTENT preko delegacije/predmeta)
│       │   ├── document_request_service.py    ← ✅ (student create/list, admin approve/reject/complete)
│       │   ├── appointment_detail_service.py  ← ✅ (Faza 3.3 — load_appointment_for_user RBAC, get_detail s countovima, participant confirm/decline)
│       │   ├── chat_service.py                ← ✅ (Faza 3.3 + 4.1 — list_messages limit≤20, create_message validacija "≤20 ukupno + ne-prazna" + can_chat_until provera; WS publish u istom prolazu sa DB INSERT)
│       │   ├── file_service.py                ← ✅ (Faza 3.3 — MinIO presigned upload/get/delete, MIME whitelist + 5MB limit)
│       │   ├── notification_service.py        ← ✅ (Faza 4.2 — Redis-first counter + DB fallback)
│       │   ├── admin_user_service.py          ← ✅ (Faza 4.3 — list_users ILIKE+role+faculty, get/create/update/deactivate, bulk_import_preview/confirm)
│       │   ├── impersonation_service.py       ← ✅ NOVO (Faza 4.4 — start/end + auto END+START re-impersonate u istoj transakciji + 30-min imp JWT)
│       │   └── audit_log_service.py           ← ✅ NOVO (Faza 4.4 — log_action flush bez commit-a, list_entries sa eager-loadom + filteri, get_active_impersonation_target)
│       ├── tasks/
│       │   ├── broadcast_tasks.py          ← ✅ Faza 4.5 — fanout_broadcast (JEDAN task za ceo broadcast, per-user try/except)
│       │   ├── email_tasks.py              ← ✅ smtplib + STARTTLS, retry 3x
│       │   ├── notifications.py            ← ✅ confirmed/rejected/**cancelled (Faza 4.6)**/reminder (multi-recipient fan-out, Faza 4.6)/strike/block_*/waitlist/document_* + `_fresh_db_session` + `_new_redis` + `_collect_recipients` + `_get_appointment`
│       │   ├── reminder_tasks.py           ← ✅ NOVO Faza 4.6 — dispatch_24h (prozor [now+23h30m, now+24h30m], TTL 25h) + dispatch_1h (prozor [now+45m, now+1h15m], TTL 2h) + async helper `_dispatch_reminders_async` sa Redis SET NX EX idempotency-jem
│       │   ├── strike_tasks.py             ← ✅ no-show detekcija (beat: */30 min)
│       │   └── waitlist_tasks.py           ← ✅ (timedelta import OK, beat-driven)
│       └── api/v1/
│           ├── auth.py             ← ✅ register, login, refresh, logout, forgot, reset, me
│           ├── students.py         ← ✅ search, prof profile, slots, appointments (DELETE → service commit + send_appointment_cancelled.delay, Faza 4.6), waitlist, document-requests
│           ├── professors.py       ← ✅ slots, blackout, profile, requests, canned, faq, crm, assistants, **cancel** (POST /requests/{id}/cancel → service commit + send_appointment_cancelled.delay, Faza 4.6)
│           ├── admin.py            ← ✅ document-requests + **users CRUD + bulk-import** (Faza 4.3) + **impersonation + audit-log** (Faza 4.4) + **strikes + broadcast** (Faza 4.5)
│           └── appointments.py     ← ✅ Faza 3.3: detail, chat REST, files multipart, participants confirm/decline; Faza 4.1: WS /chat
│
├── frontend/
│   ├── Dockerfile                  ← 3-stage build (deps → builder → runner), standalone
│   ├── package.json                ← Next 14.2.5, **Tailwind v4 + @tailwindcss/postcss**, shadcn/ui, TanStack Query, FullCalendar
│   ├── postcss.config.mjs          ← samo `@tailwindcss/postcss` (autoprefixer uklonjen u v4 migraciji)
│   ├── next.config.mjs             ← next-pwa konfigurisan, runtime caching
│   ├── middleware.ts               ← refresh_token cookie → protected routes
│   ├── playwright.config.ts        ← chromium + mobile-chrome
│   ├── components.json             ← shadcn/ui config (`tailwind.config.ts` brisan u v4 migraciji)
│   ├── public/
│   │   ├── manifest.json           ← PWA, start_url=/dashboard, sr-Latn
│   │   └── icons/                  ← 192/512/maskable + apple-touch + favicons (generated)
│   ├── e2e/                        ← smoke + auth + student-search + professor-view (rade); 4 spec-a deferovana
│   ├── app/                        ← (auth)/(student)/(professor)/(admin)/**(appointment)** route groupe
│   │   ├── globals.css             ← Tailwind v4 syntax (`@import "tailwindcss"` + `@theme inline` + `@custom-variant dark`)
│   │   ├── (auth)/                 ← /login /register /forgot-password /reset-password
│   │   ├── (student)/              ← /dashboard /search /professor/[id] /my-appointments /document-requests
│   │   ├── (professor)/            ← /professor/dashboard /professor/settings
│   │   ├── (admin)/                ← /admin /admin/users /admin/document-requests /admin/strikes /admin/broadcast /admin/audit-log
│   │   └── (appointment)/          ← NOVO: shared layout (ProtectedPage + dinamičan AppShell role) + appointments/[id]/page.tsx (radi i za STUDENT i za PROFESOR/ASISTENT)
│   ├── components/
│   │   ├── ui/                     ← svi shadcn primitivi (button **forwardRef**, card, dialog, sheet, table, dropdown-menu, …) — Tailwind v4 syntax
│   │   ├── shared/                 ← AppShell, Sidebar, TopBar, UserMenu, ImpersonationBanner, OfflineIndicator, StrikeDisplay, WaitlistButton, ProtectedPage, RoleGate, FacultyBadge, EmptyState, PageHeader
│   │   ├── auth/                   ← login/register/forgot-password forme
│   │   ├── calendar/               ← BookingCalendar, AvailabilityCalendar, RecurringRuleModal, SlotPopover, CalendarLegend
│   │   ├── appointments/           ← Card (interactive uvek), StatusBadge, RequestForm, CancelDialog, DetailHeader, ParticipantList, FileList, FileUploadZone
│   │   ├── chat/                   ← TicketChat (REST polling fallback radi protiv 3.3 endpointa), ChatMessage, ChatInput, ChatMessageCounter, ChatClosedNotice
│   │   ├── professor/              ← RequestsInbox (status-aware dropdown), RequestRejectDialog (reused i za cancel), FaqList, CannedResponseList, BlackoutManager, ProfileForm, AreasOfInterestInput
│   │   ├── student/                ← ProfessorSearchCard, ProfileHeader, FaqAccordion, SubjectsList
│   │   ├── document-requests/      ← Form, Card, AdminRow, ApproveDialog, RejectDialog
│   │   ├── admin/                  ← UsersTable, UserFormModal, BulkImportDialog, StrikesTable, AuditLogTable, BroadcastForm, DashboardMetrics
│   │   └── notifications/          ← NotificationCenter, NotificationItem, NotificationStream (WS spreman), PushSubscriptionToggle (disabled stub)
│   ├── lib/
│   │   ├── api.ts                  ← axios + JWT auto-refresh queue + 401 logout
│   │   ├── api/                    ← auth, students, professors (sa cancelRequest), appointments (live!), admin, document-requests, notifications
│   │   ├── stores/                 ← auth, impersonation, notification-ws-status
│   │   ├── hooks/                  ← 22 TanStack Query hook-ova (dodat `useCancelRequest` u `use-requests-inbox.ts`)
│   │   ├── ws/                     ← notification-socket.ts + chat-socket.ts (čeka Faza 4.1/4.2 backend)
│   │   └── utils/                  ← cn(), jwt decode (za WS query param)
│   └── types/                      ← auth, professor, appointment, admin, document-request, notification, chat, ws, common, index (barrel)
│
├── infra/
│   ├── docker-compose.yml          ← postgres + redis + minio + minio-init + nginx + backend + celery-worker + celery-beat + frontend (svi servisi pod profile=app)
│   ├── nginx/nginx.conf            ← reverse proxy + WS upgrade za /api/v1/notifications/stream i /api/v1/appointments/{id}/chat
│   └── minio/init-buckets.sh       ← 4 bucketa: appointment-files, professor-avatars (public), bulk-imports, document-requests
│
├── scripts/
│   ├── migrate.sh                          ← alembic wrapper
│   ├── seed_db.py                          ← idempotentno seedovanje 6 staff+admin korisnika
│   ├── verify-step-3-1.py                  ← manual smoke za Faza 3.1 endpointe
│   ├── test_step_32_document_requests.py   ← manual smoke za Faza 3.2 endpointe
│   ├── _step_33_integration_test.py        ← 9-scenarijski end-to-end test za Faza 3.3
│   ├── fixtures/
│   │   └── test_bulk_users.csv             ← NOVO (Faza 4.3): 5 valid + 1 in-file dup + 1 invalid domain za bulk import test
│   └── integration_tests/
│       ├── test_step_38_recurring.py            ← Faza 3.8 (5/5 PASS)
│       ├── test_step_41_chat_ws.py              ← Faza 4.1 (8/8 PASS)
│       ├── test_step_42_notifications.py        ← Faza 4.2 (7/7 PASS)
│       ├── test_step_43_admin_users.py          ← Faza 4.3 (7/7 PASS — RBAC, single create+welcome email, PATCH, deactivate+403, validation 422/409/404, bulk preview, bulk confirm+5 emails)
│       ├── test_step_44_impersonation.py        ← Faza 4.4 (8/8 PASS — RBAC, happy start, end, re-impersonate, validation 400/404, IP capture, audit filteri, expired imp 401)
│       ├── test_step_45_strikes_broadcast.py    ← Faza 4.5 (7/7 PASS — RBAC, GET /strikes shape+sort, unblock happy+idempotent, broadcast STAFF/BY_FACULTY/422)
│       └── test_step_46_reminders.py            ← NOVO: Faza 4.6 (7/7 PASS — 24h prozor → 2 REMINDER_24H, van prozora → 0, PENDING status guard → 0, idempotency drugi dispatch → 0 dodatnih, 1h prozor → 2 REMINDER_1H, student cancel → profesor 1 CANCELLED, profesor cancel → student 1 CANCELLED)
│
└── docs/
    ├── PRD_Studentska_Platforma.md
    ├── Arhitektura_i_Tehnoloski_Stek.md
    ├── ROADMAP.md                  ← merodavni plan i acceptance kriterijumi
    ├── FRONTEND_STRUKTURA.md
    ├── websocket-schema.md         ← AUTORITATIVAN ugovor za Fazu 4 (chat+notif WS)
    └── copilot_plan_prompt.md      ← stari plan (reference, ne merodavan za stanje)
```

---

## 2. ŠTA TAČNO RADI U LIVE BROWSER-U (E2E provereno)

### 2.1 Infrastruktura
- `docker compose --profile app up -d --build` diže 9 kontejnera bez greške:
  postgres, redis, minio, minio-init, nginx, **backend**, **celery-worker**, **celery-beat**, **frontend**
- `alembic upgrade head` primenjuje **jedinu** migraciju `0001_initial_schema` (sve 20 tabela + 9 enum tipova)
- `python ../scripts/seed_db.py` kreira 6 nalozima (Seed lozinka: `Seed@2024!`)
- Nginx reverse proxy:
  - `http://localhost/` → Next.js frontend
  - `http://localhost/api/*` → FastAPI backend
  - WS upgrade headeri postavljeni za buduće chat + notifications endpointe

### 2.2 Auth (Faza 1)
- ✅ Register (samo studentski domeni: `student.fon.bg.ac.rs`, `student.etf.bg.ac.rs`)
- ✅ Login → access JWT u Zustand memoriji + refresh JWT u httpOnly cookie (path=`/api/v1/auth`)
- ✅ Refresh (Redis whitelist provera)
- ✅ Logout (Redis invalidate + cookie clear)
- ✅ Forgot/Reset password (SHA-256 token hash, 1h TTL, email kroz Celery task)
- ✅ `/auth/me` (Bearer)

### 2.3 Backend endpointi koji RADE u Swaggeru (`http://localhost/api/v1/docs`)

#### `/api/v1/auth/*` — kompletno
`register`, `login`, `refresh`, `logout`, `forgot-password`, `reset-password`, `me`

#### `/api/v1/students/*` — kompletno (Faza 3.1 student strana)
| Metod | Putanja | Opis |
|-------|---------|------|
| GET   | `/professors/search` | q, faculty, subject, type filteri |
| GET   | `/professors/{id}` | profil + FAQ + slobodni slotovi |
| GET   | `/professors/{id}/slots` | slobodni slotovi (start_date, end_date filter) |
| POST  | `/appointments` | zakazivanje (Redis Lua lock) |
| DELETE| `/appointments/{id}` | otkaz (LATE_CANCEL strike < 12h) |
| GET   | `/appointments?view=upcoming\|history` | moji termini |
| POST  | `/waitlist/{slot_id}` | Redis Sorted Set join |
| DELETE| `/waitlist/{slot_id}` | leave |
| POST  | `/document-requests` | kreiranje zahteva (3.2) |
| GET   | `/document-requests` | moji zahtevi (3.2) |

#### `/api/v1/professors/*` — kompletno (Faza 3.1)
| Metod | Putanja | Opis |
|-------|---------|------|
| GET/POST/PUT/DELETE | `/slots`, `/slots/{id}` | availability slot CRUD |
| GET/POST/DELETE | `/blackout`, `/blackout/{id}` | blackout periodi |
| GET   | `/profile` | sopstveni profil + FAQ |
| PUT/PATCH | `/profile` | izmena |
| GET   | `/requests?status=PENDING\|ALL` | inbox (PROFESOR ili ASISTENT) |
| POST  | `/requests/{id}/approve` | šalje `send_appointment_confirmed` |
| POST  | `/requests/{id}/reject` | obavezno `reason` (samo PENDING) |
| POST  | `/requests/{id}/cancel` | NOVO: profesor/asistent otkazuje **APPROVED** termin (`reason` obavezan, šalje `send_appointment_rejected`) |
| POST  | `/requests/{id}/delegate` | samo PROFESOR; provera `subject_assistants` M2M |
| GET   | `/assistants` | asistenti dodeljeni mojim predmetima |
| GET/POST/PUT/PATCH/DELETE | `/canned-responses[/id]` | CRUD šablona |
| GET/POST/PUT/PATCH/DELETE | `/faq[/id]` | CRUD FAQ |
| GET/POST/PUT/DELETE | `/crm/{student_id}`, `/crm/{note_id}` | CRM beleške (path-based) |
| GET/POST/PATCH/DELETE | `/crm-notes`, `/crm-notes/{note_id}` | dupliran query-based set radi frontend kompatibilnosti |

#### `/api/v1/appointments/*` — kompletno (Faza 3.3) ← NOVO
| Metod | Putanja | Opis |
|-------|---------|------|
| GET   | `/{id}` | flat `AppointmentDetailResponse` (slot+professor+lead+countovi+`chat_open`+`can_chat_until`); RBAC u `appointment_detail_service.load_appointment_for_user` |
| GET   | `/{id}/messages` | paginated `list[ChatMessageResponse]` (limit≤20) |
| POST  | `/{id}/messages` | kreiranje poruke; **422** ako prazno, **409** ako limit 20 prekoračen, **410** ako `chat_open=false` |
| GET   | `/{id}/files` | lista fajlova s presigned GET URL-ovima (TTL 1h) |
| POST  | `/{id}/files` (multipart `file`) | upload u MinIO bucket `appointment-files`; **422** za bad MIME, **413** za >5MB |
| DELETE| `/{id}/files/{file_id}` | samo uploader (i ADMIN/profesor učesnik termina) |
| GET   | `/{id}/participants` | `list[ParticipantResponse]` |
| POST  | `/{id}/participants/{pid}/confirm` | učesnik prihvata termin |
| POST  | `/{id}/participants/{pid}/decline` | učesnik odbija termin |

> RBAC pravilo (jedinstveno za REST i budući WS): `lead_student`, prihvaćeni `participants`, profesor termina, delegirani asistent. Ostali → 403.

#### `/api/v1/admin/*` — DELIMIČNO (3.2 ✅ + 4.3 ✅; 4.4–4.5 čeka)
| Metod | Putanja | Status |
|-------|---------|--------|
| GET   | `/document-requests?status=...` | ✅ |
| POST  | `/document-requests/{id}/approve` | ✅ + Celery email |
| POST  | `/document-requests/{id}/reject` | ✅ + Celery email |
| POST  | `/document-requests/{id}/complete` | ✅ |
| GET   | `/users?q=&role=&faculty=` | ✅ Faza 4.3 — ILIKE pretraga (first/last/email), exact match po enum-ima, sortirano `created_at DESC` |
| GET   | `/users/{id}` | ✅ Faza 4.3 |
| POST  | `/users` | ✅ Faza 4.3 — single create, hibridni welcome flow (admin password + Celery welcome email sa reset link TTL=7d) |
| PATCH | `/users/{id}` | ✅ Faza 4.3 — partial update (first_name/last_name/role/faculty/is_active); email + password locked u edit mode-u (frontend ugovor) |
| POST  | `/users/{id}/deactivate` | ✅ Faza 4.3 — soft delete (`is_active=false`); login deaktiviranog → 403 |
| POST  | `/users/bulk-import/preview` (multipart `file`) | ✅ Faza 4.3 — UTF-8 BOM tolerant CSV, header `ime,prezime,email,indeks,smer,godina_upisa`, kategorisanje valid/invalid/duplicates |
| POST  | `/users/bulk-import/confirm` (multipart `file`) | ✅ Faza 4.3 — re-validira CSV (frontend re-upload-uje, ne pamti preview_id), kreira valid_rows kao STUDENT, dispatch-uje N welcome email task-ova |
| POST  | `/impersonate/{user_id}` | ✅ Faza 4.4 — `CurrentAdmin`, izdaje imp JWT (TTL=30min, BEZ refresh-a, claim-ovi `imp:true` + `imp_email` + `imp_name`); blokira self-imp (400), admin-on-admin (400), inactive (400), 404 za non-existent; auto END+START u istoj transakciji za re-impersonate flow |
| POST  | `/impersonate/end` | ✅ Faza 4.4 — deklarisana **PRE** parametrizovane `/{user_id}` rute; `CurrentAdminActor` resolve-uje pravog admina iz `imp_email` claim-a; vraća svež admin access JWT (bez imp claim-a); idempotentno (END bez aktivnog START se prihvata) |
| GET   | `/audit-log` | ✅ Faza 4.4 — filteri `admin_id`/`action` (exact match na `IMPERSONATION_START`/`IMPERSONATION_END`/`STRIKE_UNBLOCKED`/`BROADCAST_SENT`)/`from_date`/`to_date`; eager-load admin + impersonated_user; 200 redova default; sort `created_at DESC` |
| GET   | `/strikes` | ✅ Faza 4.5 — `list[StrikeRow]` (no paginate); studenti sa `total_points >= 1` (ne samo aktivno blokirani — frontend prikazuje i 1-2 poena za preventivno admin praćenje pre blokade na 3); sortirano: aktivno blokirani prvi, pa total_points DESC, pa last_strike_at DESC NULLS LAST; `blocked_until=None` ako je u prošlosti |
| POST  | `/strikes/{student_id}/unblock` | ✅ Faza 4.5 — body `UnblockRequest{removal_reason: 10..2000 chars}`; reuse `strike_service.unblock_student` (UPDATE blocked_until=now() + upiše removed_by/removal_reason; NIŠTA se ne briše); ako student nije bio blokiran → 200 "nije bio blokiran" (no-op, no audit/notif); inače audit `STRIKE_UNBLOCKED` + commit + `send_block_lifted.delay(student_id, removal_reason)` |
| POST  | `/broadcast` | ✅ Faza 4.5 — body `BroadcastRequest{title<=120, body>=10, target: ALL\|STUDENTS\|STAFF\|BY_FACULTY, faculty: FON\|ETF\|null, channels: [IN_APP\|EMAIL] min_length=1}`; `model_validator` validira `target=BY_FACULTY ↔ faculty not None` + tiho nuluje faculty za ne-BY_FACULTY target; flow: resolve_user_ids (ALL=svi aktivni ne-ADMIN, STUDENTS=role=STUDENT, STAFF=role IN [PROFESOR,ASISTENT], BY_FACULTY=faculty=$f + ne-ADMIN) → INSERT broadcast row → audit `BROADCAST_SENT` → commit → `fanout_broadcast.delay(broadcast_id, user_ids, channels)`; vraća 201 sa `BroadcastResponse` |
| GET   | `/broadcast` | ✅ Faza 4.5 — `list[BroadcastResponse]` poslednjih 50, sortirano `sent_at DESC`; koristi `ix_broadcasts_sent_at` indeks |

#### Routeri koji su zakomentarisani u `main.py` (čekaju implementaciju)
```python
# from app.api.v1 import search, notifications
# app.include_router(search.router,         prefix="/api/v1/search",        tags=["Search"])
# app.include_router(notifications.router,  prefix="/api/v1/notifications", tags=["Notifications"])
```
→ Faze 4.2 (notifications REST+WS) i 5.1 (Google PSE proxy). `appointments` je odkomentarisan u Korak 3.3.

#### `/api/v1/health` — ✅
Vraća `{ "status": "ok", "service": "studentska-platforma-api", "version": "1.0.0", "environment": "..." }`

> ⚠️ **HANDOFF2 napomena bila je da `http://localhost/api/v1/docs` vraća 404.** Stvarni put je **`http://localhost/docs`** (FastAPI default; nginx ne prefixuje). Swagger se otvara tu. `openapi.json` je na `http://localhost/openapi.json`.

### 2.4 Celery
- **Worker:** `studentska_celery_worker` — sluša `app.tasks.broadcast_tasks`, `app.tasks.email_tasks`, `app.tasks.notifications`, `app.tasks.reminder_tasks`, `app.tasks.strike_tasks`, `app.tasks.waitlist_tasks` (sve uvezeno u `celery_app.py::celery_app.conf.include` autodiscover)
- **Beat:** `studentska_celery_beat` — `--scheduler celery.beat.PersistentScheduler` (FIX iz Korak 2.1, više ne pada). Trenutno scheduluje 4 ulaza:
  - `detect-no-show-every-30-minutes` → `strike_tasks.detect_no_show` (`crontab(minute="*/30")`)
  - `process-waitlist-offers-every-5-minutes` → `waitlist_tasks.process_waitlist_offers` (`crontab(minute="*/5")`)
  - **`dispatch-reminders-24h-every-30-minutes`** → `reminder_tasks.dispatch_24h` (`crontab(minute="*/30")`) — Faza 4.6
  - **`dispatch-reminders-1h-every-15-minutes`** → `reminder_tasks.dispatch_1h` (`crontab(minute="*/15")`) — Faza 4.6
- **Implementirani taskovi:**
  - `email_tasks.send_email` (smtplib STARTTLS, retry 3x)
  - `notifications.send_appointment_confirmed`
  - `notifications.send_appointment_rejected`
  - `notifications.send_appointment_cancelled` ← **NOVO Faza 4.6** (zaseban email + in-app `APPOINTMENT_CANCELLED`; argumenti `appointment_id`, `cancelled_by_role: str ("STUDENT"|"PROFESOR")`, `reason: str|None`; fan-out na lead+profesor+CONFIRMED participants sa exclude-om onoga ko je otkazao; per-recipient try/except sa structured logging-om; popravlja latentni bug iz PRD §5.2 gde `booking_service.cancel_appointment` NIKADA nije dispečovao Celery task)
  - `notifications.send_appointment_reminder` ← **PROŠIREN Faza 4.6** (multi-recipient fan-out: lead student + profesor + svi CONFIRMED participants; `_collect_recipients` helper sa dedupom po user_id; `if appointment.status != APPROVED: return False` defense-in-depth status guard; per-recipient try/except sa `_log.warning` i `extra={appointment_id, recipient_id, hours_before, error}`; argument `hours_before>=24` mapira na `APPOINTMENT_REMINDER_24H`, ispod na `_1H`)
  - `notifications.send_strike_added`
  - `notifications.send_block_activated`
  - `notifications.send_block_lifted` (Faza 4.5 — admin override; email "Blokada naloga je skinuta" + in-app `BLOCK_LIFTED` notif sa `removal_reason` u body-ju)
  - `notifications.send_waitlist_offer`
  - `notifications.send_document_request_approved` (Faza 3.2)
  - `notifications.send_document_request_rejected` (Faza 3.2)
  - `strike_tasks.detect_no_show`
  - `waitlist_tasks.process_waitlist_offers`
  - `broadcast_tasks.fanout_broadcast` (Faza 4.5 — JEDAN task za ceo broadcast, NE per-user; per-user IN_APP create i EMAIL send svaki u svom `try/except` sa per-user warning log-om; partial failure ne ruši ceo task; `recipient_count` u DB ostaje "ciljani" broj resolve-ovan pre task-a)
  - **`reminder_tasks.dispatch_24h`** ← **NOVO Faza 4.6** (sync Celery wrapper koji `asyncio.run(_dispatch_reminders_async(hours_before=24, lower_offset=23h30m, upper_offset=24h30m, redis_ttl_seconds=25h*3600))`; SELECT `appointments JOIN availability_slots WHERE status=APPROVED AND slot_datetime BETWEEN ...`; per-row Redis `SET NX EX` na ključu `reminder:24:{id}` → `delay(send_appointment_reminder)` ako lock acquire uspe, skip ako ne; vraća `{scanned, dispatched, skipped}` summary)
  - **`reminder_tasks.dispatch_1h`** ← **NOVO Faza 4.6** (isti pattern kao gornji; prozor `[now+45m, now+1h15m]`, ključ `reminder:1:{id}`, TTL=2h)
- **`send_appointment_cancelled` wiring (Faza 4.6 commit pattern):** `booking_service.cancel_appointment` (student cancel) i `professor_portal_service.cancel_request` (profesor cancel APPROVED) sada eksplicitno rade `await db.commit()` + `send_appointment_cancelled.delay(appointment_id, cancelled_by_role, reason)` pre povratka. Service-level commit + dispatch je isti pattern kao `broadcast_service.dispatch` iz Faze 4.5; route handler-i u `students.py`/`professors.py` ostaju netaknuti (samo pozivaju service). Profesor flow više **ne** reuse-uje `send_appointment_rejected` (semantički pogrešno per PRD §5.2).
- **`_fresh_db_session` helper (Faza 4.5, reused u Faza 4.6):** u `backend/app/tasks/notifications.py` — fix-uje cross-loop bug iz deljenog `AsyncSessionLocal` QueuePool-a (asyncpg konekcije su VEZANE za event loop u kome su otvorene, drugi `asyncio.run()` u istom Celery worker procesu pucao je sa `RuntimeError: Future attached to a different loop`). Helper je `@asynccontextmanager` koji kreira fresh `AsyncEngine(NullPool)` per task invocation, async_sessionmaker, dispose-uje engine na izlasku. **Reminder dispatcher koristi isti pattern** preko shared importa `from app.tasks.notifications import _fresh_db_session, _new_redis`. NullPool overhead je zanemarljiv jer `worker_prefetch_multiplier=1`.
- **`_collect_recipients` helper (Faza 4.6):** u `backend/app/tasks/notifications.py` — vraća `list[(user_id, email, full_name)]` u redosledu lead/professor/non-lead-CONFIRMED-participants sa dedupom po `user_id`. Coupled sa `_get_appointment` koji je proširen `selectinload(Appointment.participants).selectinload(AppointmentParticipant.student)` da fan-out može da dobije `student.email` bez dodatnog DB hop-a. `exclude_user_ids` argument koristi `send_appointment_cancelled` da preskoči onog ko je inicirao otkazivanje. Future-proof za grupne konsultacije iz Prompt 2 (kad booking flow počne da kreira non-lead participants sa CONFIRMED status-om, automatski će dobijati reminder/cancel notif bez ikakvih izmena u task kodu).
- **Nedostaju:** *(ništa što čeka iz Faze 4. Sve reminder + cancel funkcionalnosti su završene u Korak 4.6.)*

### 2.5 Frontend (svih 19 ruta — UI gotov)

| URL | Status | Backend kačenje |
|-----|--------|----------------|
| `/login`, `/register`, `/forgot-password`, `/reset-password` | 🟢 live | `/auth/*` ✅ |
| `/dashboard` | 🟢 live | `/students/appointments` ✅, strikes ✅ Faza 4.5 |
| `/search` | 🟢 live | `/students/professors/search` ✅ |
| `/professor/[id]` | 🟢 live | `/students/professors/{id}`, slots ✅ |
| `/my-appointments` | 🟢 live (cancel + strike warning, Card uvek interactive — chevron + actions zajedno) | `/students/appointments` ✅ |
| `/document-requests` | 🟢 live (Faza 3.2) | `/students/document-requests` ✅ |
| `/appointments/[id]` | 🟢 live (Faza 3.3 — detail+files+chat REST polling, dostupna i STUDENT-u i PROFESOR-u/ASISTENT-u kroz `(appointment)` route group); chat WS dolazi u 4.1 | `/appointments/{id}/*` ✅ |
| `/professor/dashboard` | 🟢 live (Faza 3.1 + status-aware inbox dropdown — PENDING: Approve/Reject/Delegate; APPROVED: Cancel; ostalo: read-only Otvori) | `/professors/requests` + `/professors/requests/{id}/cancel` ✅ |
| `/professor/settings` | 🟢 live (Faza 3.1) | `/professors/profile/faq/canned/blackout/assistants` ✅ |
| `/admin` | 🟡 placeholder kartice | čeka 4.7 metrics agregat |
| `/admin/users` | 🟢 live (Faza 4.3 — tabela sa ILIKE pretragom + role/faculty filterima, create modal, edit modal, deactivate, bulk import dialog sa PRD §4.1 CSV format-om) | `/admin/users` + `/admin/users/bulk-import/{preview,confirm}` ✅ |
| `/admin/document-requests` | 🟢 live (Faza 3.2) | `/admin/document-requests` ✅ |
| `/admin/strikes` | 🟢 live (Faza 4.5 — tabela sa total_points >= 1, blokirani prvi, "Odblokiraj" dialog sa removal_reason 10-2000 chars; vidi i preventivno 1-2 poena) | `/admin/strikes` + `/admin/strikes/{id}/unblock` ✅ |
| `/admin/broadcast` | 🟢 live (Faza 4.5 — forma sa target ALL/STUDENTS/STAFF/BY_FACULTY + channels IN_APP/EMAIL + history poslednjih 50 broadcast-ova) | `/admin/broadcast` (POST + GET) ✅ |
| `/admin/audit-log` | 🟢 live (Faza 4.4 — tabela sa filterima admin/action/from_date/to_date, exact match na action enum) | `/admin/audit-log` ✅ |

**Frontend foundation (Faze 2.2 + 2.3):** `lib/api/*` (8 fajlova), `lib/hooks/*` (21 hook-ova), `types/*` (10 fajlova + barrel index.ts), `lib/ws/*` (notification-socket.ts + chat-socket.ts spremni prema `docs/websocket-schema.md`), `lib/stores/*` (auth, impersonation, notification-ws-status).

---

## 3. POZNATI BUGOVI / PITFALL-OVI

### 3.1 Aktivni problemi
1. **HANDOFF2 napomena `/api/v1/docs not found`** — taj URL je pogrešan. Swagger je na `http://localhost/docs`. Treba samo ažurirati dokumentaciju (HANDOFF2 §"Provera da sve radi" tabela).
2. **`backend/.env` se ne nalazi u repo-u** (gitignored), ali postoji `backend/.env.example`. Pre prvog pokretanja `cp backend/.env.example backend/.env` i postaviti `SECRET_KEY` (generiši `openssl rand -hex 32`) + `REDIS_PASSWORD`.
3. **`recurring_group_id` REŠENO u Koraku 3.8 (apr 2026).** Migracija `20260427_0002_recurring_group_id.py` dodala je kolonu + parcijalni indeks `WHERE recurring_group_id IS NOT NULL`. `availability_service.create_slot` ekspandira `recurring_rule` u N zapisa preko `dateutil.rrule` (JS weekday → dateutil mapiranje), hard cap 100 → 422 "Prevelik raspon", `_check_recurring_conflicts` blokira preklapanje sa APPROVED terminima → 422 sa `detail.conflicts`. Novi `DELETE /api/v1/professors/slots/recurring/{group_id}` briše samo buduće slotove (prošli ostaju za audit); 409 + `conflicts` lista ako iko od njih ima APPROVED termin. Acceptance: `scripts/integration_tests/test_step_38_recurring.py` 5/5 PASS.
4. **Untracked fajlovi u repo-u** (vidi `git status`): `CURRENT_STATE2.md` (ovaj dokument), `CURSOR_PROMPT_1_BACKEND_COMPLETION.md`, `backend/celerybeat-schedule` (runtime, treba `.gitignore`), `infra/nginx/nginx.conf` (treba commit-ovati ili `.gitignore`).

### 3.2 Bugovi koji su POPRAVLJENI (NE diraj ih ponovo)
1. ✅ `backend/app/tasks/waitlist_tasks.py:2` — `from datetime import datetime, timedelta, timezone` (ranije je `timedelta` bio izostavljen)
2. ✅ `infra/docker-compose.yml:155` — `--scheduler celery.beat.PersistentScheduler` (ranije je bio `django_celery_beat.schedulers:DatabaseScheduler` koji nije instaliran)
3. ✅ `backend/app/main.py` — admin **i** appointments router su uvezeni i registrovani; samo `search`, `notifications` su zakomentarisani
4. ✅ **Tailwind v3 → v4 migracija (apr 2026):** `shadcn/ui` je generisao komponente sa v4 sintaksom (`w-(--var)`, `data-state:`, `outline-hidden`, `data-open:animate-in`) ali projekat je vrteo v3 — što je dovelo do toga da je dropdown content imao `position: static` umesto `absolute`, i zato je bio nevidljiv. Fix: instaliran `tailwindcss@^4.2.4` + `@tailwindcss/postcss@^4.2.4`, izbrisan `tailwind.config.ts`, `globals.css` rewrite-ovan na v4 sintaksu (`@import "tailwindcss"` + `@theme inline { ... }` + `@custom-variant dark`), `postcss.config.mjs` koristi samo `@tailwindcss/postcss` (autoprefixer izbačen), `tw-animate-css` zamenio `tailwindcss-animate`.
5. ✅ **`Button` ref-forwarding bug:** Radix UI primitivi sa `asChild` (npr. `DialogTrigger asChild`) nisu mogli da forward-uju ref na `Button`, što je lomilo Floating UI pozicioniranje (`transform: translate(0px, -200%)`). Fix: `frontend/components/ui/button.tsx` umotan u `React.forwardRef<HTMLButtonElement, ButtonProps>`.
6. ✅ **Profesor inbox dropdown — "Konflikt: samo PENDING zahtevi mogu biti odbijeni":** `RequestInboxRow` sada pokazuje status-aware akcije (PENDING → Odobri/Odbij/Delegiraj; APPROVED → Otkaži termin; REJECTED/CANCELLED/COMPLETED → samo Otvori). Backend dobija novi `POST /professors/requests/{id}/cancel` endpoint za otkazivanje već odobrenog termina.
7. ✅ **`/appointments/[id]` nedostupan profesoru:** stranica je bila u `(student)` route group → middleware je redirektovao profesora. Premešteno u novi `(appointment)` route group sa `ProtectedPage allowedRoles={["STUDENT","PROFESOR","ASISTENT"]}` i dinamičnim `AppShell` rolom (STUDENT vidi student sidebar, PROFESOR/ASISTENT profesor sidebar).
8. ✅ **`AppointmentCard` nije bio interactive kad ima Cancel button:** `my-appointments` sada uvek prosleđuje `interactive={true}` i `Cancel` button eksplicitno radi `e.stopPropagation()`. Card render-uje chevron + actions zajedno.
9. ✅ **`booking_service.cancel_appointment` NIJE dispečovao Celery task (Faza 4.6 fix):** student koji otkaže termin nikad nije generisao notifikaciju → profesor nije saznavao za otkazivanje. PRD §5.2 zahteva da i student-cancel i profesor-cancel pošalju notifikaciju drugoj strani. Fix: novi `notifications.send_appointment_cancelled(appointment_id, cancelled_by_role, reason)` task; service eksplicitno `await db.commit()` + `.delay(...)` pre povratka. Profesor flow (`professor_portal_service.cancel_request`) je takođe migriran sa pogrešnog `send_appointment_rejected` na ovaj novi task.
10. ✅ **`send_appointment_reminder` slao je notifikaciju samo studentu (Faza 4.6):** generic task iz Faze 4.2 nije imao fan-out logiku → profesor nikad nije dobijao reminder iako PRD §5.2 to traži. Fix: task proširen sa `_collect_recipients` koji vraća lead+profesor+CONFIRMED participants sa dedupom; per-recipient `try/except` da SMTP/Redis ispad za jednog ne pokvari ostale.
11. ✅ **Diakritik-insensitive search REŠENO u Koraku 10 (apr 2026, migracija 0004).** Pre ove sesije, `search_service.search_professors` i `admin_user_service.list_users` su koristili plain `ILIKE` što je značilo da student koji kuca „Petrovic" NIJE nalazio „Milovan Petrović" (dijakritički ć ne matchuje plain c). ROADMAP §1.3 i §1.7 su pominjali „sa unaccent od migracije 0002" — to je bilo aspiraciono, nije postojalo. Fix: migracija `20260427_0004_unaccent.py` instalira `unaccent` + `pg_trgm` ekstenzije, definiše IMMUTABLE wrapper `public.f_unaccent(text)` (sa eksplicitnim `replace(replace($1, 'đ', 'dj'), 'Đ', 'Dj')` korakom pre `unaccent` poziva — standardni rečnik mapira `đ→d`, ne `dj`, pa „djordjevic" search ne bi hvatao „Đorđević" bez ovog koraka) i `public.f_unaccent_array(text[])` wrapper (jer `array_to_string` je STABLE pa ne može direktno u functional indeks), pravi 5 GIN trigram indeksa (`ix_users_first_name_unaccent_trgm`, `ix_users_last_name_unaccent_trgm`, `ix_professors_department_unaccent_trgm`, `ix_professors_areas_unaccent_trgm`, `ix_subjects_name_unaccent_trgm`). Servisi prebačeni sa `User.first_name.ilike(...)` na `func.f_unaccent(User.first_name).ilike(func.f_unaccent(needle))` (obe strane idu kroz isti wrapper za simetričan rezultat). Bonus: search_service sada matchuje i preko `professors.areas_of_interest TEXT[]` što je bio gap — query „vestacka" pronalazi profesora sa `areas_of_interest=['Veštačka inteligencija']`. `EXPLAIN ANALYZE` pokazuje `Bitmap Index Scan on ix_users_first_name_unaccent_trgm` (NE Seq Scan) zahvaljujući `pg_trgm` GIN indeksima — bez `pg_trgm`-a, leading-wildcard `ILIKE '%q%'` UVEK ide kroz Seq Scan jer B-tree ne može efikasno da iskoristi vodeći wildcard. Acceptance: `scripts/integration_tests/test_step_47_unaccent.py` 7/7 PASS.

---

## 4. SLEDEĆI KORAK — KORAK 2 Prompta 2 (Override notifikacije)

**Status Prompta 1:** ✅ **100% gotov** (8/10 stvarnih koraka završeno; KORAK 9 Google PSE svesno skinut).

**Status Prompta 2 (`CURSOR_PROMPT_2_DEMO_READY.md`):**
- ✅ **KORAK 1 (Web Push notifikacije):** kompletno (poslednja sesija, ova v2.10)
- ⏳ **KORAK 2 (Override notifikacije):** čeka — kad profesor kreira blackout u rangu sa već postojećim APPROVED appointment-ima, sistem treba da ih bulk CANCELLED-uje + dispečuje `send_appointment_cancelled.delay` sa custom razlogom + dodaje na prioritetnu waitlist 14 dana (Redis Sorted Set sa score=`-now_timestamp`)
- ⏳ **KORAK 3 (Asistent RBAC):** čeka — `require_subject_assistant(subject_id)` dependency + CRM rute provera da je asistent dodeljen istom predmetu kao termin koji vezuje studenta

**Šta KORAK 2 zahteva (skica iz CURSOR_PROMPT_2 §3.2):**

| # | Iteracija | Procena |
|---|-----------|---------|
| 1 | `availability_service.create_blackout` proširen — pre INSERT-a, query APPROVED appointments u tom rasponu, bulk update na CANCELLED, dispatch `send_appointment_cancelled` task za svaki, dodaj ih na prioritetnu waitlist | 2-3h |
| 2 | `waitlist_service.add_to_priority_waitlist` (Redis Sorted Set, key `waitlist:priority:{slot_id}`, score=`-now_timestamp` za prioritet, 14d expiry) | 1-2h |
| 3 | Custom email body za override cancel ("profesor je rezervisao to vreme za drugu obavezu, na prioritetnoj ste listi") + push (od KORAK 1, automatski) | 1h |
| 4 | Idempotency: 2x kreiranje istog blackout-a ne dispečuje 2x notif (verifikacija kroz UNIQUE ili IF NOT EXISTS check) | 1h |
| 5 | `scripts/integration_tests/test_step_51_blackout_override.py` 3+ scenarija PASS | 1.5h |

**Ukupan napor za KORAK 2:** ~1 dan fokusa.

**Pre otvaranja sledeće sesije** treba ovaj dokument (CURRENT_STATE2 v2.10) pročitati radi onboarding-a + skenirati `CURSOR_PROMPT_2_DEMO_READY.md §3.2` za precizan acceptance kriterijume KORAKA 2.

---

## 5. PUN BACKLOG (Prompt 2 i dalje)

Prompt 1 je 100% gotov. KORAK 1 Prompta 2 (Web Push) je gotov u poslednjoj sesiji. Stavke ispod su preostale iz Prompta 2 (`CURSOR_PROMPT_2_DEMO_READY.md`) plus dugoročne izvan-DEMO stavke.

| # | Korak | Opis | Procena | Zavisi |
|---|-------|------|---------|--------|
| 1 | **KORAK 2 (Prompt 2)** | Override notifikacije — blackout kanceluje APPROVED appointments + priority waitlist 14d | 1d | — |
| 2 | **KORAK 3 (Prompt 2)** | Asistent RBAC — `require_subject_assistant` + CRM rute provera | 0.5d | — |
| 3 | **5.3** | Production infra (compose.prod, Let's Encrypt, rate limiting, CI) | 1.5d | — |
| 4 | **5.4** | Backend pytest-asyncio + Locust load test | 1d | — |
| 5 | **Group consultations** | Multi-student booking flow (PRD §6) | 2d | — |
| 6 | **5.1 (opciono)** | Google PSE proxy (`/api/v1/search/university`) sa Redis 1h cache-om | 0.5d | — |

**Ukupan preostali napor:** ~6.5 dana fokusa (DEMO READY zahteva samo prvih 2 stavke).

### Završeno u v2.10 (poslednja sesija, neće više biti deo backlog-a)
- ✅ **KORAK 1 Prompta 2 — Web Push notifikacije end-to-end.** Backend: novi model `PushSubscription` sa UNIQUE per-user-endpoint + migracija `20260427_0005_push_subscriptions.py`; novi servis `push_service` sa UPSERT subscribe / idempotent unsubscribe / fan-out send_push (pywebpush kroz `asyncio.to_thread`, 410+404 cleanup, quiet hours 22:00-07:00 CET sa 4 urgent type exception, trimovan payload title≤80/body≤140, deep link mapping per notif type, tag deduplication); 3 nove Pydantic V2 šeme + 3 REST rute (`GET /vapid-public-key` 503 ako nije konfigurisan, `POST /subscribe` UPSERT idempotent 201, `POST /unsubscribe` idempotent 200 — push akcije NIJE u audit logu, isti pattern kao mark_read); kritičan hook u `notification_service.create()` sa `dispatch_push_in_background: bool = True` flag-om (FastAPI request handler ide fire-and-forget kroz `asyncio.create_task`, Celery taskovi await-uju eksplicitno jer `asyncio.run` cancel-uje pending task-ove pri zatvaranju event loop-a — Python 3.11+ behavior); 5 Celery taskova u `tasks/notifications.py` + `tasks/broadcast_tasks.py` postavljaju flag=False; `core/config.py` proširen sa 3 VAPID polja sa defenzivnim defaultom `""`; novi `scripts/generate_vapid_keys.py` (cryptography ec.SECP256R1, base64url enkodiranje); `requirements.txt` + `pywebpush>=1.14.0` + `cryptography>=43.0.0` (Rizik 1 NE materijalizovan, Python 3.12 inkompatibilnost nije postojala). Frontend: TS tipovi PRVI u `frontend/types/notification.ts` (Pydantic šeme su slijed), API client `notificationsApi.{getVapidPublicKey, subscribeToPush, unsubscribeFromPush}`, novi `use-push-subscription` hook sa state machine-om (loading/unsupported/denied/disabled/enabled) + `urlBase64ToArrayBuffer` helper (TS stricter mode bug fix sa `Uint8Array` → `ArrayBuffer`), `<PushSubscriptionToggle />` zamenjuje stari disabled stub realnim flow-om sa Switch + Loader + Tooltip, custom `frontend/worker/index.js` SW (next-pwa default `customWorkerSrc: "worker"` automatski pickup — Rizik 2 NE materijalizovan) sa `push` event handler-om i `notificationclick` deep linking-om. **2 pre-postojeća buga popravljena:** `frontend/Dockerfile` `COPY public ./public` otkomentarisan (PWA artifacts nisu stizali u runner image), `frontend/middleware.ts` matcher proširen sa exclude-om za `sw.js|workbox-*.js|worker-*.js|swe-worker-*.js` (browser je dobijao 307 redirect na `/login` pre SW registracije). `scripts/integration_tests/test_step_50_push.py` 6/6 PASS u 9.2s (VAPID GET auth + non-empty key, Subscribe UPSERT idempotency 1 red u DB, validacija 422 za http://+ short + missing keys, Unsubscribe idempotent sa različitim porukama, cross-user isolation per-user UNIQUE, push fan-out hook signal kroz stderr `push_service` log linije sa fake hostom). Acceptance kriterijumi 100% zadovoljeni.

### Završeno u v2.9 (predprošla sesija, neće više biti deo backlog-a)
- ✅ Korak 10 — Migracija 0004 `unaccent` + `pg_trgm` + diakritik-insensitive search. Migracija `20260427_0004_unaccent.py` instalira `unaccent` + `pg_trgm` ekstenzije, definiše IMMUTABLE wrapper `public.f_unaccent(text)` (sa `replace(replace($1, 'đ', 'dj'), 'Đ', 'Dj')` korakom pre `unaccent` poziva za srpsko `đ→dj` mapiranje koje standardni rečnik ne radi) i `public.f_unaccent_array(text[])` wrapper (jer `array_to_string` je STABLE pa ne može direktno u functional indeks), pravi 5 GIN trigram indeksa: `ix_users_first_name_unaccent_trgm`, `ix_users_last_name_unaccent_trgm`, `ix_professors_department_unaccent_trgm`, `ix_professors_areas_unaccent_trgm`, `ix_subjects_name_unaccent_trgm`. `search_service.search_professors` prebačen na `func.f_unaccent(User.first_name).ilike(func.f_unaccent(needle))` pattern (obe strane idu kroz isti wrapper za simetričan rezultat); dodato pretraživanje preko `Professor.areas_of_interest TEXT[]` kroz `func.f_unaccent_array(...)`. `admin_user_service.list_users` isto refaktorisan (`first_name`/`last_name` kroz wrapper, `email` ostaje plain ILIKE jer je ASCII-only). `subjects.code` ostaje plain ILIKE. Migracija je idempotentna sa simetričnim downgrade-om (drop indeksi → drop funkcije → drop ekstenzije). `scripts/integration_tests/test_step_47_unaccent.py` 7/7 PASS u 4.7s (psql sanity, student search "Petrovic"→"Milovan Petrović", "djordjevic"→"Đorđe Đorđević" sa replace+unaccent kompozicijom, ASCII no-op "Stefan", search po areas_of_interest "vestacka"→"Veštačka inteligencija", admin /users search, EXPLAIN ANALYZE pokazuje `Bitmap Index Scan on ix_users_first_name_unaccent_trgm` NE Seq Scan). Bug iz §3.1 punkt 2 prebačen u §3.2 punkt 11.

### Završeno u v2.8 (sesija pre toga, neće više biti deo backlog-a)
- ✅ Korak 4.6 — Reminder Celery beat taskovi (24h + 1h sa idempotency-jem u Redis-u) + multi-recipient fan-out u `send_appointment_reminder` (lead+profesor+CONFIRMED participants) + novi `send_appointment_cancelled` task koji popravlja latentni bug iz PRD §5.2 (`booking_service.cancel_appointment` NIKADA nije dispečovao Celery task; `professor_portal_service.cancel_request` je reuse-ovao `send_appointment_rejected` što je bilo semantički pogrešno). Novi modul `backend/app/tasks/reminder_tasks.py` sa `dispatch_24h` (prozor `[now+23h30m, now+24h30m]`, beat svakih 30 min, TTL ključa 25h) i `dispatch_1h` (prozor `[now+45m, now+1h15m]`, beat svakih 15 min, TTL 2h). `_collect_recipients` helper sa dedupom po user_id i `exclude_user_ids` argumentom; `_get_appointment` proširen `selectinload(participants.student)`. Defense-in-depth status guard u oba sloja (dispatcher SQL filter + task `if status != APPROVED: return False`). Per-recipient `try/except` sa structured logging-om (`extra={appointment_id, recipient_id, hours_before, error}`) — partial failure ne ruši fan-out. Service commit + dispatch pattern u `booking_service.cancel_appointment` i `professor_portal_service.cancel_request` (eksplicitan `await db.commit()` + `send_appointment_cancelled.delay(...)` pre povratka). `celery_app.include` proširen sa `"app.tasks.reminder_tasks"`; `beat_schedule` proširen sa 2 nova ulaza. `scripts/integration_tests/test_step_46_reminders.py` 7/7 PASS u 32s (24h prozor → 2 REMINDER_24H notif; van prozora → 0; PENDING status guard → 0; idempotency drugi dispatch → 0 dodatnih; 1h prozor → 2 REMINDER_1H sa `data.hours_before=1`; student cancel HTTP DELETE → profesor 1 CANCELLED + lead 0 + status=CANCELLED; profesor cancel HTTP POST → student 1 CANCELLED + profesor 0 + rejection_reason zapisan). E2E manualno: dispatcher 24h → fan-out lead+prof 2/2 sent; drugi dispatch → 0 dodatnih (Redis NX); HTTP cancel flow oba pravca verifikovan kroz admin impersonation.

### Završeno u v2.7 (sesija pre toga)
- ✅ Korak 4.5 — Admin strikes + broadcast fan-out. Migracija `20260427_0003_broadcasts.py` (nova tabela `broadcasts` sa `VARCHAR(50)[]` channels kolonom + indeksi). `AuditAction` enum proširen sa `STRIKE_UNBLOCKED` + `BROADCAST_SENT` (Text kolona, bez migracije). 4 nove Pydantic V2 šeme (`StrikeRow`, `UnblockRequest`, `BroadcastRequest` sa `model_validator` za BY_FACULTY consistency, `BroadcastResponse`). Novi servisi `strike_admin_service` (list_strike_rows sa total_points >= 1 filterom) i `broadcast_service` (resolve_user_ids za ALL/STUDENTS/STAFF/BY_FACULTY, dispatch sa post-commit Celery delay). Postojeći `strike_service.unblock_student` reuse-ovan 1:1. Novi Celery taskovi: `notifications.send_block_lifted` (email + in-app BLOCK_LIFTED) i `broadcast_tasks.fanout_broadcast` (JEDAN task za ceo broadcast, per-user try/except oko IN_APP create i EMAIL send, partial failure ne ruši task). 4 nove rute u `admin.py` (GET /strikes, POST /strikes/{id}/unblock, POST /broadcast, GET /broadcast). **Bonus fix:** `_fresh_db_session` helper u `notifications.py` sa `NullPool` fix-uje cross-loop bug iz `AsyncSessionLocal` QueuePool-a koji je rušio sve Celery in-app taskove sa `RuntimeError: Future attached to a different loop` — automatski popravlja sve postojeće in-app taskove. `scripts/integration_tests/test_step_45_strikes_broadcast.py` 7/7 PASS. E2E manualno verifikovano: GET /strikes vraća tačan StrikeRow → POST /unblock → BLOCK_LIFTED notif u DB-u + 1 audit STRIKE_UNBLOCKED row; POST /broadcast STAFF → 4 notif za PROFESOR/ASISTENT, recipient_count=4 u history, 1 audit BROADCAST_SENT.

### Završeno u v2.6 (sesija pre toga)
- ✅ Korak 4.4 — Impersonation + audit log. `AuditAction` enum (Text kolona, bez migracije). `IMPERSONATION_TOKEN_TTL_MINUTES=30` config + `create_access_token(expires_minutes=)` proširenje. `get_current_user(request)` propagira imp claim-ove na `request.state` + User in-memory atribute. Novi `get_current_admin_actor` / `CurrentAdminActor` dependency (resolve pravog admina iz oba tipa tokena, izolovano od `require_role(ADMIN)`). 4 nove Pydantic V2 šeme (`ImpersonatorSummary`, `ImpersonationStartResponse`, `ImpersonationEndResponse`, `AuditLogRow` — sve 1:1 sa `frontend/types/admin.ts`). Servisi `impersonation_service` (start sa validacijama + auto END+START re-impersonate u istoj transakciji, end idempotentno) i `audit_log_service` (log_action flush bez commit-a, list_entries sa eager-loadom, get_active_impersonation_target helper). 3 rute u `admin.py` (`/impersonate/end` PRE `/impersonate/{user_id}` zbog FastAPI declaration-order match-a; `/audit-log` sa filterima admin_id/action/from_date/to_date, exact match). `_client_ip` helper (X-Forwarded-For → X-Real-IP → request.client.host). Pitanje 5 odluka: admin tokom imp-a koji klikne `/admin/*` dobija 403 (NE pravimo backdoor kroz imp claim, sidebar prirodno štiti UX). Frontend WS hot-swap: NULL touch (oba hook-a već imaju `accessToken` u `useEffect` dep-u). `scripts/integration_tests/test_step_44_impersonation.py` 8/8 PASS. E2E manualno verifikovano (clean DB run): admin login → impersonate → 30-min imp token → audit START sa IP=172.18.0.1 → impersonate/end → admin token → audit END.

### Završeno u v2.5 (sesija pre toga)
- ✅ Korak 4.3 — Admin users CRUD + bulk CSV import. Pydantic V2 šeme `AdminUserCreate/Update/Response`, `BulkImportRow/Preview/Result` (1:1 sa `frontend/types/admin.ts`). `admin_user_service` sa CRUD + ILIKE pretragom + bulk preview/confirm (UTF-8 BOM tolerant CSV, header `ime,prezime,email,indeks,smer,godina_upisa` per PRD §4.1, samo studentski domeni). Hibridni welcome flow: `_create_reset_token` faktorisan iz `forgot_password`, novi `send_welcome_email_with_reset_link` Celery task, `WELCOME_RESET_TOKEN_TTL_DAYS=7`. 7 ruta u `admin.py` (PATCH umesto PUT, POST `/deactivate` umesto DELETE, frontend re-upload-uje CSV na confirm umesto preview_id u Redis-u — sve direktno iz frontend ugovora). `scripts/integration_tests/test_step_43_admin_users.py` 7/7 PASS sa Celery worker email task verifikacijom. Fixture `scripts/fixtures/test_bulk_users.csv`. Frontend touch (1 linija): `bulk-import-dialog.tsx` helper text usklađen sa PRD §4.1 formatom.

### Završeno u v2.4 (sesije pre toga)
- ✅ Korak 4.2 — Notifications REST + per-user WS stream + Celery in-app proširenje. `NotificationType` enum (16 vrednosti, VARCHAR(50) u DB-u, bez migracije). Pydantic V2 šeme (`NotificationResponse`, `UnreadCountResponse`). `notification_service` (Redis-first counter + DB fallback + lazy backfill, envelope helperi). `notifications.router` (4 REST + native WS `/stream` sa 25s heartbeat / 60s timeout, kanal `notif:pub:{user_id}` iz JWT sub claim-a → implicitna RBAC). 8 Celery email taskova prošireno (mapiranje 8→9: reminder se grana 24h/1h). Frontend cleanup: defanzivni 5-min polling skinut, reconnect schedule prebačen na schema §7.2 standard. `scripts/integration_tests/test_step_42_notifications.py` 7/7 PASS. E2E verifikovano: profesor approve → student WS bell badge update za 828ms (< 2s acceptance ✓).

### Završeno u v2.3 (sesije pre toga)
- ✅ Korak 4.1 — Chat WebSocket + Redis Pub/Sub. `core/ws_deps.py::decode_ws_token` (vraća User|None bez raise-a). `appointments.py` proširen sa `WS /{id}/chat` handler-om (3 concurrent task-a, close kodovi 4401/4403/4404/4409/4430/4500, per-sender rate limit Redis SET NX PX 500ms). `chat_service.send_message(redis=)` radi DB INSERT + commit + publish u jednom prolazu. `scripts/integration_tests/test_step_41_chat_ws.py` 8/8 PASS.

### Završeno u v2.2 (sesije pre toga, neće više biti deo backlog-a)
- ✅ Korak 3.8 — Recurring slots ekspanzija. Migracija 0002 (`recurring_group_id` UUID + parcijalni indeks). Pydantic V2 `RecurringRule` šema (frontend ugovor 1:1). `availability_service`: `_expand_recurring_rule` (dateutil.rrule), `_check_recurring_conflicts`, `delete_recurring_group`. `POST /api/v1/professors/slots` vraća `list[SlotResponse]`. Novi `DELETE /api/v1/professors/slots/recurring/{group_id}` (samo budući slotovi, 409 + conflicts ako ima APPROVED termina). Acceptance test `scripts/integration_tests/test_step_38_recurring.py` 5/5 PASS na live stack-u.

### Završeno u v2.1 (sesije pre poslednje)
- ✅ Korak 3.3 — Appointment detail + chat REST polling + files (MinIO presigned URL) + participants confirm/decline. Endpoint inventory 1:1 sa `frontend/lib/api/appointments.ts`. End-to-end test (`scripts/_step_33_integration_test.py`) verifikovan na live stack-u.
- ✅ Profesor `cancel_request` (POST `/professors/requests/{id}/cancel`) — simetrično paru sa student `DELETE /appointments/{id}`.
- ✅ Frontend Tailwind v3 → v4 migracija (uključuje `Button` forwardRef fix, novi `(appointment)` route group, status-aware inbox dropdown).

---

## 6. KRITIČNA PRAVILA (PROŠIRENA)

Iz `CLAUDE.md` (samo bitno za Claude AI na webu):

1. **Sve rute su `async def`** — bez izuzetaka.
2. **ORM only** — zabranjen raw SQL. Samo SQLAlchemy 2.x `select()` ili ORM.
3. **UUID PK** sa `gen_random_uuid()` server default-om.
4. **Pydantic V2** — `model_config = {"from_attributes": True}` na svim Response šemama.
5. **JWT u memoriji (Zustand)** za access token. **NIKADA `localStorage`**.
6. **Refresh JWT u httpOnly cookie** sa `path=/api/v1/auth`.
7. **Nema Keycloak-a** u V1 (planiran V2).
8. **Email kroz Celery task**, nikad direktno iz endpoint-a (`smtplib` u workeru, ne u API procesu).
9. **Staff naloge (PROFESOR/ASISTENT/ADMIN) kreira samo ADMIN**, nema javne registracije.
10. **CRM beleške nisu vidljive STUDENT-u** (RBAC u `crm_service`).
11. **Redis Lua skript za slot lock** — atomičan, ne `SET NX + EXPIRE` kao 2 komande.
12. **Validacija WS tokena samo pri handshake-u**, ne pri svakoj poruci (`docs/websocket-schema.md §2.2`).
13. **WebSocket close kodovi (4401/4403/4404/4409/4429/4430/4500)** moraju se striktno poštovati — frontend reconnect logika zavisi od njih.
14. **Impersonation JWT TTL = 30 min, BEZ refresh-a.** Posle 401 → admin re-impersonira.
15. **Audit log obavezan** za svaki impersonate start/end + IP adresu.
16. **Email whitelist u `backend/.env`:**
    - `ALLOWED_STUDENT_DOMAINS=student.fon.bg.ac.rs,student.etf.bg.ac.rs`
    - `ALLOWED_STAFF_DOMAINS=fon.bg.ac.rs,etf.bg.ac.rs`
17. **Pri svakom novom Pydantic schema fajlu ili izmeni postojeće** — uporedi sa `frontend/types/*.ts` fajlom (red za red). Frontend je zaključan na te tipove; ako backend odstupi, sve mora da se refaktoriše.

---

## 7. UGOVORI KOJI SU ZAKUCANI U FRONTEND-U (ne menjati bez sinhronizacije)

| Backend artefakt | Frontend ugovor (lokacija) | Implementiran |
|------------------|---------------------------|---------------|
| `AppointmentResponse` | `frontend/types/appointment.ts::AppointmentResponse` | ✅ |
| `AppointmentDetailResponse` (+ `ChatMessage{Create,Response}`, `FileResponse`, `Participant{Response,ConfirmRequest}`) | `frontend/types/appointment.ts` | ✅ Faza 3.3 — `backend/app/schemas/appointment.py` |
| `RequestCancelRequest` (`reason: str 1..2000`) | `frontend/lib/api/professors.ts::cancelRequest` | ✅ |
| `ProfessorProfileResponse` (student view) | `frontend/types/professor.ts::ProfessorProfileResponse` | ✅ |
| `ProfessorMeResponse` (own view) | `frontend/types/professor.ts::ProfessorMeResponse` | ✅ |
| `RequestInboxRow` | `frontend/types/professor.ts::RequestInboxRow` | ✅ |
| `DocumentRequestResponse` | `frontend/types/document-request.ts` | ✅ |
| `AdminUserResponse` (= alias na `UserResponse`, BEZ student-specific polja), `AdminUserCreate` (sa `password` required), `AdminUserUpdate` (Partial + `is_active?`), `BulkImportPreview`, `BulkImportResult`, `BulkImportRow` | `frontend/types/admin.ts` | ✅ Faza 4.3 — `backend/app/schemas/admin.py` |
| `AuditLogRow`, `ImpersonatorSummary`, `ImpersonationStartResponse`, `ImpersonationEndResponse` | `frontend/types/admin.ts` | ✅ Faza 4.4 — `backend/app/schemas/admin.py` |
| `StrikeRow`, `UnblockRequest`, `BroadcastTarget`, `BroadcastChannel`, `BroadcastRequest`, `BroadcastResponse` | `frontend/types/admin.ts` | ✅ Faza 4.5 — `backend/app/schemas/admin.py` (target enum: `ALL\|STUDENTS\|STAFF\|BY_FACULTY` — NEMA `YEAR`; channels: `IN_APP\|EMAIL` — NEMA `PUSH`) |
| `NotificationResponse`, `NotificationType` (16 vrednosti) | `frontend/types/notification.ts` | ✅ Faza 4.2 — `backend/app/schemas/notification.py` |
| `WsEnvelope`, `WS_CLOSE_CODES`, svi WS event tipovi | `frontend/types/ws.ts` + `docs/websocket-schema.md` | ✅ Faza 4.1+4.2 |
| Impersonation JWT (`imp`, `imp_email`, `imp_name`, 30 min, bez refresh-a) | `docs/websocket-schema.md §6` + `frontend/lib/stores/impersonation.ts` | ✅ Faza 4.4 |

**Pravilo:** Pre nego što napišeš novu Pydantic šemu, otvori odgovarajući `frontend/types/*.ts` fajl. Polja moraju da se poklope (snake_case na backend-u, snake_case ostaje i na TS strani jer je i tamo `snake_case` konvencija za API tipove).

---

## 8. SEED NALOZI (svi sa lozinkom `Seed@2024!`)

| Email | Uloga | Fakultet | Profesor profil |
|-------|-------|----------|----------------|
| `sluzba@fon.bg.ac.rs` | ADMIN | FON | — |
| `sluzba@etf.bg.ac.rs` | ADMIN | ETF | — |
| `profesor1@fon.bg.ac.rs` | PROFESOR | FON | dr Milovan Petrović, Katedra za IS, kanc. 216 |
| `profesor2@fon.bg.ac.rs` | PROFESOR | FON | dr Dragana Nikolić, Katedra za menadžment, kanc. 305 |
| `profesor1@etf.bg.ac.rs` | PROFESOR | ETF | prof. dr Aleksandar Jovanović, RTI katedra, kanc. 54 |
| `asistent1@fon.bg.ac.rs` | ASISTENT | FON | — |

Studenti se sami registruju na `/register` koristeći `*@student.fon.bg.ac.rs` ili `*@student.etf.bg.ac.rs`.

---

## 9. KAKO POKRENUTI (Quick start)

```bash
# Prvi put
cd Student_Platform_App
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# u backend/.env postaviti SECRET_KEY i REDIS_PASSWORD

cd infra
docker compose --profile app up -d --build
docker exec studentska_backend alembic upgrade head
docker exec studentska_backend python /scripts/seed_db.py

# Test:
curl http://localhost/api/v1/health
# → {"status":"ok",...}

# Swagger:
open http://localhost/docs

# Login (Swagger ili UI):
POST /api/v1/auth/login
{ "email": "profesor1@fon.bg.ac.rs", "password": "Seed@2024!" }
```

Nakon izmena u `frontend/.env` (NEXT_PUBLIC_*):
```bash
docker compose --profile app build --no-cache frontend
docker compose --profile app up -d frontend
```

End-to-end test za Korak 3.3 (mora biti pokrenut sa živim `--profile app` stack-om):
```bash
# stack mora biti up; alembic upgrade head + seed odrađeni
python scripts/_step_33_integration_test.py
# → 9 scenarija: docs exposure, RBAC, file upload (PDF / .exe / >5MB), DELETE permissions,
#   chat limit (20), prazna poruka, otkazan termin → 410.
```

---

## 10. ZAKLJUČAK

**Stanje:** Faza 0 + 1 + 2 + 3 (cela) + **4.1 + 4.2 + 4.3 + 4.4 + 4.5 + 4.6** (cela backend Faza 4) + Korak 10 (unaccent + pg_trgm) + cela frontend strana kroz Fazu 6 + Tailwind v4 + **KORAK 1 Prompta 2 (Web Push notifikacije end-to-end)** — gotovo.
**Sledeći korak:** **KORAK 2 Prompta 2 (Override notifikacije)** — `availability_service.create_blackout` proširen sa appointment cancel + priority waitlist 14d + custom email body; → KORAK 3 (Asistent RBAC ojačan) → posle DEMO READY ide ostatak Prompta 2 (5.3 prod infra, 5.4 testovi, group consultations, opciono 5.1 PSE).

**Šta je važno za nastavak:**
- Frontend je *zaključan* na ugovore u `frontend/types/*.ts` i `docs/websocket-schema.md`. Pridržavaj se reda za red. **Push tipovi (`WebPushKeys`/`PushSubscribeRequest`/`PushUnsubscribeRequest`/`VapidPublicKeyResponse`/`PushSubscriptionResponse`/`PushNotificationPayload`) su definisani PRVI u `frontend/types/notification.ts` u v2.10** — Pydantic šeme su kopirane red-za-red.
- Pre svakog novog endpoint-a: otvori odgovarajući `frontend/lib/api/*.ts` da vidiš tačan URL + metod + query parametre koje frontend zove.
- Cilj svakog koraka: kad backend isporuči endpoint, odgovarajući 🟡 placeholder na frontendu automatski postaje 🟢 (axios wrapper i hook već postoje).
- `/appointments/[id]` je odblokiran — chat radi preko REST polling-a (`GET /{id}/messages` na ~5s), upload fajlova prolazi kroz MinIO presigned URL-ove, RBAC je centralizovan u `appointment_detail_service.load_appointment_for_user`.
- Frontend gradi Tailwind v4 — **NE** dodavaj nazad `tailwind.config.ts`. Sve theme varijable idu u `app/globals.css` unutar `@theme inline { ... }`.
- **Push hook obrazac za nove Celery taskove:** kad pišeš novi Celery task koji poziva `notification_service.create(...)`, OBAVEZNO postavi `dispatch_push_in_background=False` da push se await-uje. `asyncio.create_task` se silently otkazuje kad `asyncio.run` zatvori event loop (Python 3.11+). FastAPI request handler-i ostavljaju default `True` (fire-and-forget za <100ms response).
- **VAPID keys:** generišu se preko `python scripts/generate_vapid_keys.py` (output kopiraj u `backend/.env`); restart backend kontejnera kroz `docker compose --profile app up -d --force-recreate backend` (samo `restart` ne reload-uje `.env`).

---

*Ovaj dokument (v2.10) generisan je 26. apr 2026. kasno veče direktnim skeniranjem codebase-a (`backend/app/models/push_subscription.py`, `backend/app/services/push_service.py`, `backend/app/services/notification_service.py` sa novim `dispatch_push_in_background` flag-om, `backend/alembic/versions/20260427_0005_push_subscriptions.py`, `frontend/types/notification.ts`, `frontend/lib/api/notifications.ts`, `frontend/lib/hooks/use-push-subscription.ts`, `frontend/components/notifications/push-subscription-toggle.tsx`, `frontend/worker/index.js`, `scripts/integration_tests/test_step_50_push.py`, plus sve iz v2.9 osnovne). Ako posle ovog datuma vidiš novi commit, prekontroliši §0 TL;DR (status Prompta 2), §4 (sledeći korak — KORAK 2 Override) i §5 backlog tabelu pre nego što ažuriraš plan. **Prompt 1 je 100% gotov** (8/10 stvarnih koraka). **Prompt 2 KORAK 1 je 100% gotov** (Web Push). **KORAK 2 + KORAK 3 čekaju eksplicitno odobrenje za nastavak.***
