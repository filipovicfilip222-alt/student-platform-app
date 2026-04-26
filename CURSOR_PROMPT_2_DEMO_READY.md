# CURSOR PROMPT 2 — Feature Expansion (DEMO-READY VERSION)

> **Status:** Skraćena verzija fokusirana na **demo prezentaciju**. Originalni plan iz `CURSOR_PROMPT_2_FEATURE_EXPANSION.md` (sa 10 koraka — testovi, prod infra, CI/CD, push, group consultations, monitoring) je odložen. Plan onoga što je odloženo i u kom redosledu se vraća posle demo-a je u `POST_DEMO_TODO.md`.
>
> **Šta ovaj prompt pokriva (3 koraka):**
> 1. Web Push notifikacije (PRD §5.3) — VAPID + service worker + frontend toggle
> 2. Override notifikacije (PRD §3.1) — kad profesor blokira datum, studenti sa zakazanim terminima dobijaju notif
> 3. Asistent RBAC ojačan — pojačati postojeću proveru da asistent može CRM samo za svoje predmete
>
> **Veličina:** ~3.5–4 dana fokusiranog rada (KORAK 1 ~2d, KORAK 2 ~1d, KORAK 3 ~0.5d).
>
> **Preduslov:** PROMPT 1 je 100% završen i verifikovan. Sve frontend 🟡 stranice su prešle u 🟢 (osim Google PSE koji je svesno odložen).

---

## 0. PRE-FLIGHT

Pre prvog reda koda:

1. `CURRENT_STATE2.md v2.9` — autoritativno trenutno stanje posle Prompta 1
2. `CLAUDE.md` — pravila stack-a (posebno §11 zabrane)
3. `docs/PRD_Studentska_Platforma.md` — §3.1 (Override datumi), §5.3 (PWA Web Push), §1.3 (RBAC asistent)
4. `docs/ROADMAP.md` — referenca

### Pravila ostaju ista kao u Promptu 1

- Async, ORM only, Pydantic V2, UUID PK
- Pre svake izmene tipa: pogledaj `frontend/types/*.ts` (frontend je istina)
- Pre svakog endpoint-a: pogledaj `frontend/lib/api/*.ts`
- Direktno menjaš fajlove na disku — bez Git terminologije, bez „commit-ova", „PR-ova", „branch-eva"
- Posle svake iteracije: kratak status update sa verifikacijom
- Integration test scenariji idu u `scripts/integration_tests/` folder

---

## KORAK 1 — Web Push notifikacije (PRD §5.3)

**Cilj:** PWA push notifikacije rade kad user nema otvoren browser tab. Frontend već ima `<PushSubscriptionToggle />` kao disabled stub (iz Faze 5.2).

### 1.1 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/requirements.txt` | EDIT | Dodaj `pywebpush==1.14+`, `cryptography` |
| 2 | `backend/app/models/push_subscription.py` | NEW | `PushSubscription`: id (UUID), user_id (FK), endpoint, p256dh_key, auth_key, user_agent, created_at, last_used_at |
| 3 | `backend/alembic/versions/20260427_0005_push_subscriptions.py` | NEW | Kreiraj tabelu + indekse (revision="0005", down_revision="0004") |
| 4 | `backend/app/schemas/notification.py` | EDIT (postojeći iz KORAKA 4 Prompta 1) | Dodaj `PushSubscribeRequest` (endpoint, keys), `VapidPublicKeyResponse` (public_key) |
| 5 | `backend/app/services/push_service.py` | NEW | `subscribe(user, data)`, `unsubscribe(user, endpoint)`, `send_push(user_id, title, body, url)` (poziva `pywebpush` per sub, čisti expired/410 sub-ove) |
| 6 | `backend/app/api/v1/notifications.py` | EDIT (postojeći) | `POST /subscribe` (body: PushSubscribeRequest), `POST /unsubscribe` (body: endpoint), `GET /vapid-public-key` |
| 7 | `backend/app/services/notification_service.py` | EDIT (postojeći iz KORAKA 4) | U `create(...)`, posle Redis publish, takođe pozovi `push_service.send_push(user_id, ...)` ako user ima aktivne sub-ove |
| 8 | `backend/.env.example` | EDIT | `VAPID_PUBLIC_KEY=`, `VAPID_PRIVATE_KEY=`, `VAPID_SUBJECT=mailto:admin@fon.bg.ac.rs` |
| 9 | `scripts/generate_vapid_keys.py` | NEW | Helper script: generiše VAPID par, ispiše base64 verziju za `.env` |
| 10 | `frontend/lib/api/notifications.ts` | EDIT (postojeći) | `subscribeToPush(subscription)`, `unsubscribeFromPush(endpoint)`, `getVapidPublicKey()` |
| 11 | `frontend/components/notifications/push-subscription-toggle.tsx` | EDIT | Skini disabled stub: `Notification.requestPermission()`, `serviceWorker.pushManager.subscribe(...)` sa VAPID public key, pošalji backend-u |
| 12 | `frontend/public/sw-push.js` | NEW (ili u next-pwa config) | Service worker push event handler — prikazuje native notif i otvara `data.url` na klik |
| 13 | `frontend/next.config.mjs` | EDIT | Dodaj custom service worker `pwa: { swSrc: 'public/sw-push.js' }` ili kroz workbox `customWorker` |

### 1.2 Kritični detalji

- **VAPID key generation:** Kreiraj jednom, čuvaj u `.env`, **ne menjaj** (ako se promeni, sve postojeće sub-ove postaju nevažeće). Pokreni `python scripts/generate_vapid_keys.py` jednom, kopiraj output u `.env`.
- **Cleanup:** kad `pywebpush` vrati 410 Gone → obriši subscription iz baze (već postojeći user više nije validan endpoint).
- **Frontend service worker:** `next-pwa` generiše svoj SW. Treba ga proširiti — koristi `customWorkerDir` config ili manualno integriši `sw-push.js` posle build-a (videti next-pwa docs za workbox custom routes).
- **Permission flow:** klik na toggle → browser prompt-uje za permission → ako user dozvoli, registruje se push subscription → POST endpoint-u → server upiše u DB.
- **Idempotency:** ako user pozove `subscribe` 2x sa istim endpoint-om, drugi poziv samo ažurira `last_used_at`, ne kreira duplikat.

### 1.3 Quiet hours (opciono za demo)

Ako vreme dozvoli: ne šalji push za reminder između 22:00–07:00 (Europe/Belgrade). Dodaj u `notification_service.create` proveru pre poziva `push_service.send_push`. Za demo nije kritično — push može da stigne i u 23h, demo neće biti u to vreme.

### 1.4 Acceptance

- [ ] Pokreni `python scripts/generate_vapid_keys.py` — vidi VAPID public + private key u output-u
- [ ] Dodaj keys u `backend/.env`, restart backend
- [ ] Login student u Chrome-u → klik na push toggle → permission prompt → klik „Dozvoli"
- [ ] Endpoint zapisan u bazi (`SELECT * FROM push_subscriptions;`)
- [ ] Profesor odobri zahtev → student dobija **OS-level** push notif čak i ako tab nije otvoren (zatvori tab, push i dalje stiže)
- [ ] Klik na push notif otvara `/appointments/{id}`
- [ ] Klik na unsubscribe → endpoint obrisan iz baze, push više ne stiže
- [ ] Test u različitim browser-ima: Chrome ✓, Firefox ✓, Safari (verovatno ne radi na desktopu — to je poznat limit, dokumentuj)
- [ ] Integration test: `scripts/integration_tests/test_step_50_push.py` sa scenarijima:
  * Subscribe happy path
  * Unsubscribe
  * 410 Gone cleanup (mock)
  * Push se ne šalje za quiet hours (ako implementirano)

### 1.5 Demo skripta

Tokom prezentacije:
1. Otvori platformu na laptopu, login kao student, dozvoli push notifikacije
2. **Zatvori tab** (ne minimuj — pravo zatvori)
3. Na drugom uređaju (telefon ili drugi laptop) login kao profesor, odobri zahtev
4. Studentov laptop dobija push notifikaciju u system tray-u (Windows) ili notification center-u (Mac)
5. Klik na notif → otvara browser direktno na `/appointments/{id}`

**Wow effect:** „aplikacija šalje notifikacije čak i kad nije otvorena, kao prava mobilna aplikacija."

**Procena KORAK 1:** ~2 dana.

---

## KORAK 2 — Override notifikacije (PRD §3.1)

**Cilj:** Kad profesor postavi blackout datum koji **gazi postojeće APPROVED appointments**:
1. Kancelovati te appointment-e (`status=CANCELLED_BY_PROFESSOR`)
2. Notifikovati pogođene studente (in-app + email + push ako je iz KORAKA 1 isporučen)
3. Staviti ih na **prioritetnu waitlist** za sledeći slot u sledećih 14 dana

### 2.1 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/services/availability_service.py` | EDIT (postojeći) | `create_blackout(...)`: pre INSERT-a, query svih APPROVED appointments u tom datumskom rasponu → bulk update `status=CANCELLED_BY_PROFESSOR` + `cancellation_reason="Profesor je rezervisao termin za drugu obavezu"` → za svaki: `send_appointment_cancelled.delay(id, "PROFESSOR", reason)` (postojeći task iz KORAKA 8 Prompta 1) + `waitlist_service.add_to_priority_waitlist(student_id, professor_id, ttl=14*24*3600)` |
| 2 | `backend/app/services/waitlist_service.py` | EDIT (postojeći) | Dodaj `add_to_priority_waitlist(...)` — Redis Sorted Set sa zaokruženim score-om koji garantuje da prioritetni budu prvi na listi (npr. `score = -now_timestamp` da prioritetni imaju najmanji score, sortirani po vremenu blackout-a) |
| 3 | `backend/app/models/enums.py` | EDIT (postojeći) | Provera da `AppointmentStatus.CANCELLED_BY_PROFESSOR` postoji ili `CANCELLED` je dovoljan (Cursor odlučuje na osnovu trenutnog modela). Ako fali, dodaje se kao Python enum vrednost (kolona je VARCHAR ili PG enum — proveri) |
| 4 | `frontend/types/appointment.ts` | EDIT (samo ako fali) | Sinhronizuj enum vrednost ako je dodavana nova vrednost na backend-u |
| 5 | `scripts/integration_tests/test_step_51_blackout_override.py` | NEW | Scenariji: (a) profesor kreira blackout sutra 10–14h, postoji APPROVED termin u 11h → status menja se u CANCELLED_BY_PROFESSOR, student dobija email + notif; (b) student vidi termin označen kao otkazan u `/my-appointments`; (c) profesor doda novi slot sledeće nedelje → student je prvi na waitlist offer-u |

### 2.2 Kritični detalji

- **Prioritetna waitlist:** Postojeći `waitlist_service` (iz Faze 4.6 ili ranije) ima Redis Sorted Set. Prioritetni score je negativan (manji = bolji prioritet) sa `-now_timestamp` da osigura FIFO unutar prioriteta. Regular waitlist users imaju score `+now_timestamp`.
- **TTL:** 14 dana — posle toga student ispada sa prioritetne waitlist (vraća se u regular ako se ručno ponovo prijavi).
- **Email body** za override otkazivanje treba da bude drugačiji od regularnog cancel-a — pominje da je termin profesor rezervisao za drugu obavezu i da je student automatski na prioritetnoj listi.
- **Idempotency:** ako profesor kreira blackout 2x za isti period (slučajno klikne 2x), drugi put nema dodatnih kanceliranja (prvi put su već svi APPROVED prebačeni u CANCELLED).
- **Edge case:** šta ako student ima 5 termina u blackout periodu (nemoguće u praksi, ali tehnički)? Svih 5 se kanceliraju, šalje se 5 zasebnih notifikacija (svaki termin svoj kontekst). Ne agregiramo u 1 notif jer student treba da vidi koji tačno termini su otkazani.

### 2.3 Acceptance

- [ ] Profesor kreira blackout sutra od 10h do 14h
- [ ] Pre toga: student je imao APPROVED termin u 11h
- [ ] Posle blackout-a: termin status = CANCELLED_BY_PROFESSOR (ili CANCELLED sa razlogom)
- [ ] Student dobija email „Vaš termin je otkazan jer je profesor rezervisao to vreme za drugu obavezu"
- [ ] Student dobija in-app notif sa istim sadržajem
- [ ] Student vidi u `/my-appointments` da je termin u history sekciji sa statusom otkazan
- [ ] Kad profesor sledeće nedelje doda novi slot → student je prvi na waitlist (proveri kroz `redis-cli ZRANGE waitlist:{slot_id} 0 -1 WITHSCORES`)
- [ ] Ako je iz KORAKA 1 push isporučen, student dobija i push notif

**Procena KORAK 2:** ~1 dan.

---

## KORAK 3 — Asistent RBAC ojačan (PRD §1.3, CLAUDE.md §5)

**Cilj:** Eksplicitno provera + test da asistent može CRM samo za svoje predmete. Trenutno (iz Faze 3.1) postoji `crm_service` sa nekim RBAC-om, ali nije eksplicitno verifikovan kroz integration test.

### 3.1 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `backend/app/core/dependencies.py` | EDIT (postojeći) | Dodaj `require_subject_assistant(subject_id)` dependency koja proverava `subject_assistants` M2M za current user. Ako asistent nije dodeljen tom predmetu → 403 |
| 2 | `backend/app/api/v1/professors.py` | EDIT (postojeći) | Sve CRM rute za asistenta (GET/POST/PUT/DELETE `/crm/{student_id}` i `/crm-notes`) moraju proveriti da je asistent dodeljen istom predmetu kao termin koji vezuje studenta. Ako nije → 403. Profesori uvek prolaze (oni vide sve svoje predmete). |
| 3 | `backend/app/services/crm_service.py` | EDIT (postojeći) | Dodaj helper `_assert_assistant_can_access_student(db, asistent_user, student_id)` koji query-uje da li postoji bilo koji APPROVED appointment između tog asistenta (kao delegated_to) i tog studenta na predmetu kome je dodeljen. Ako ne, raise HTTPException 403. |
| 4 | `scripts/integration_tests/test_step_52_assistant_rbac.py` | NEW | Scenariji: (a) asistent A dodeljen predmetu X, postoji student S koji je išao na termin sa profesorom za predmet X (sa delegacijom asistentu A) → A može CRM za S; (b) student T je išao na termin za predmet Y (gde A nije asistent) → A NE može CRM za T (403); (c) profesor uvek može CRM za bilo kog studenta svog predmeta |

### 3.2 Kritični detalji

- **„Dodeljen predmetu"** = postoji red u `subject_assistants` M2M tabeli sa `(subject_id, assistant_user_id)`.
- **„Studentov termin za taj predmet"** = postoji bilo koji `Appointment` sa `lead_student_id=student_id` i `subject_id=subject_id` (bez obzira na status — i COMPLETED ili CANCELLED termini ostaju validna istorija).
- **Delegacija nije potrebna** za RBAC — asistent može CRM za studenta koji je bio na profesorovom (ne asistentovom) terminu, ali predmet mora biti zajednički. Logika: asistent koji predaje vežbe iz X može da pravi beleške o studentu koji je išao kod profesora za X.
- **Profesor ima bezuslovni pristup** za svoje predmete — ne pravi se RBAC zid između profesora i njegovih studenata.
- **Admin nije slučaj** — admin koristi impersonation za debugging, ne CRM endpoint direktno (CLAUDE.md §14).

### 3.3 Acceptance

- [ ] Asistent `asistent1@fon.bg.ac.rs` (seed) dodeljen predmetu „Programiranje 1" (proveri u bazi `subject_assistants` ili kreiraj ako fali)
- [ ] Student je bio na terminu za „Programiranje 1" → asistent može POST `/professors/crm/{student_id}` sa beleškom → 200
- [ ] Drugi student je bio na terminu za „Matematika 1" (gde asistent NIJE dodeljen) → asistent POST `/professors/crm/{drugi_student_id}` → 403
- [ ] Profesor (vlasnik predmeta) GET `/professors/crm/{bilo_koji_student_id}` → 200 (uvek prolazi)
- [ ] Integration test 6/6 PASS (3 RBAC scenarija + happy path-ovi)

**Procena KORAK 3:** ~0.5 dana.

---

## ZAVRŠNI ČEK-LIST POSLE 3 KORAKA

- [ ] Web Push radi na Chrome i Firefox (Safari je known limit, dokumentovano)
- [ ] Override blackout kanceluje termine + šalje notifikacije + prioritetna waitlist
- [ ] Asistent RBAC ojačan + verifikovan kroz integration test
- [ ] CURRENT_STATE2.md ažuriran na v3.0 (markirajući kraj Prompta 1 + 3 koraka iz Prompta 2)
- [ ] `POST_DEMO_TODO.md` ostaje netaknut — služi kao mapa za posle prezentacije
- [ ] Demo skripta isprobana minimum 1 put end-to-end pre prezentacije (najmanje 1 ceo flow: register → search → book → professor approve → push notif)

---

## DEMO PRIPREMA

Posle završetka 3 koraka, **napravi demo skriptu** od 5–7 minuta koja pokriva:

1. **Login flow** (30s) — registruj novog studenta sa fakultetskim email-om, login profesora postojećim seed nalogom
2. **Search + book** (2 min) — student traži profesora („Petrovic" matchuje „Petrović" — KORAK 10 Prompta 1), klikne profil, vidi FAQ iznad kalendara, klikne slobodan slot, popuni formu
3. **Professor approve** (30s) — profesor vidi zahtev u inbox-u, klikne odobri
4. **Real-time notification** (1 min) — student vidi bell badge ažuriran < 2s (KORAK 4 Prompta 1) + push notif u system tray-u (KORAK 1 ovog prompta)
5. **Chat real-time** (1 min) — oba korisnika otvaraju `/appointments/{id}`, šalju poruke, vide se u realnom vremenu (KORAK 3 Prompta 1)
6. **Document request** (1 min) — student traži uverenje, admin odobrava, student dobija notif sa datumom preuzimanja
7. **Admin features** (1 min) — admin impersonira profesora (KORAK 6), vidi crveni banner, klikne „Izađi", odlazi na `/admin/audit-log` da pokaže audit trail
8. **Završetak** (30s) — ukratko spomeni da postoje strikes, broadcast, recurring slots, ali da to nećete demonstrirati zbog vremena

**Wow factors koji prolaze kroz prezentaciju:**
- Real-time chat između studenta i profesora
- Push notifikacije čak i kad tab nije otvoren
- Srpska latinična pretraga (Petrovic → Petrović)
- Crveni impersonation banner sa audit logom
- Recurring slot-ovi (1 klik = 8 termina za 8 nedelja)

**Šta NE pokazujemo na demo-u** (svesno):
- Bulk CSV import (rizično ako fail-uje uživo, koristi pripremljen video umesto)
- Strike system (zahteva manipulisanje `slot_datetime` u psql-u, suviše tehnički za demo)
- Reminder taskovi (ne mogu se demonstrirati u realnom vremenu, samo objasniti)
- Google PSE search (svesno preskočeno u Promptu 1)
- Group consultations (odložen u POST_DEMO_TODO)

---

**Total procena ovog Prompta:** 3.5–4 dana fokusiranog rada.

Posle završetka, projekat je **demo-ready** + ima 2 ključna PRD feature-a (push, override notifikacije) + ojačan RBAC.

Sve ostalo iz originalnog Prompta 2 (testovi, prod infra, CI/CD, group consultations, monitoring, Postman kolekcija) je u `POST_DEMO_TODO.md` — vraća se u rad **posle prezentacije**.
