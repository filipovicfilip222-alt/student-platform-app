# WebSocket šema — Studentska Platforma (FON/ETF)

**Verzija:** 1.0
**Datum:** April 2026
**Status:** Ugovor (contract) — napisan **pre** implementacije Faze 4/5. Backend i frontend moraju striktno poštovati ovu šemu. Svaki odstupak ide kao PR na ovaj fajl i mora biti dogovoren između Stefana (backend) i Filipa (frontend).
**Referentni dokumenti:** `CLAUDE.md`, `docs/ROADMAP.md` (§ 4.1, § 4.2, § 4.4, § 4.7), `docs/FRONTEND_STRUKTURA.md` (§ 3.5, § 3.6, § 7.2), `docs/copilot_plan_prompt.md` (§ 3.4 Appointments, § 3.7 Notifications), `docs/Arhitektura_i_Tehnoloski_Stek.md` (§ 4 Redis, § 5 Frontend).

---

## 1. Pregled

V1 aplikacija ima **dva WebSocket kanala** — oba native (FastAPI `@router.websocket`), bez socket.io sloja, sa Redis Pub/Sub-om kao relayom između backend instanci.

| # | URL | Scope | Auth | Redis kanal | ROADMAP |
|---|-----|-------|------|-------------|---------|
| 1 | `WS /api/v1/notifications/stream` | per-user | JWT query param | `notif:pub:{user_id}` | 4.2 (❌ nije implementiran) |
| 2 | `WS /api/v1/appointments/{id}/chat` | per-appointment | JWT query param | `chat:pub:{appointment_id}` | 4.1 (❌ nije implementiran) |

**Kritična odluka:** `socket.io-client` se **ne koristi**. CLAUDE.md § 2 i `Arhitektura_i_Tehnoloski_Stek.md` § 5 pominju `socket.io-client` kao biblioteku, ali `copilot_plan_prompt.md` § 3.4 i ROADMAP § 4.1 pokazuju da backend koristi native FastAPI WebSocket. Frontend koristi native `WebSocket` API u oba slučaja (wrapper u `frontend/lib/ws/`). Posledica: `socket.io-client` se može izostaviti iz `package.json`-a ili zadržati za eventualni V2 fallback.

---

## 2. Handshake i autentifikacija

### 2.1 Prenos tokena

Browseri **ne dozvoljavaju** custom `Authorization` header na `new WebSocket(...)` pozivu. Zato se access token prenosi kao **query param**:

```
wss://api.example.com/api/v1/notifications/stream?token=<ACCESS_JWT>
wss://api.example.com/api/v1/appointments/<uuid>/chat?token=<ACCESS_JWT>
```

**Napomena o sigurnosti:** token u URL-u može procuriti u access log-ove reverse proxy-ja. Zato:
- Access token TTL ostaje kratak (`ACCESS_TOKEN_EXPIRE_MINUTES=60`).
- Nginx `access_log` za `/api/v1/**/stream` i `/api/v1/**/chat` treba da maskira `token=...` query param (`$arg_token` se isključuje iz log formata) — INFRA TODO pri deploy-u.
- Klijent refreshuje access token **pre** otvaranja WS konekcije (ili neposredno po receive-u `4401 Unauthorized` close-a).

### 2.2 Validacija na serveru

Pseudo-code (u `backend/app/api/v1/notifications.py` / `appointments.py`):

```python
@router.websocket("/stream")
async def notifications_stream(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_access_token(token)
    except JWTError:
        await websocket.close(code=4401)
        return

    user = await db.get(User, UUID(payload["sub"]))
    if not user or not user.is_active:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    # ... subscribe to Redis pub/sub
```

Validacija se radi **samo pri handshake-u**, ne pri svakoj poruci (CLAUDE.md § 12, „WebSocket konekcija se gubi"). Ako token istekne mid-session — server ne prekida konekciju automatski; klijent će dobiti 401 na sledećem REST pozivu, refreshovati token, i pri reconnect-u poslati novi.

### 2.3 Close code-ovi

| Code | Značenje | Akcija klijenta |
|------|----------|-----------------|
| `1000` | Normal closure (klijent zatvorio) | — |
| `1001` | Going away (server restart / heartbeat timeout) | Reconnect sa backoff-om |
| `4401` | Unauthorized (invalid/expired JWT) | Refresh token → reconnect; ako refresh padne → logout |
| `4403` | Forbidden (nije učesnik / nema RBAC) | Ne reconnect, prikaži toast |
| `4404` | Resurs ne postoji (appointment izbrisan) | Ne reconnect, redirect |
| `4409` | Conflict (limit poruka / duplikat) | Samo informativno |
| `4429` | Rate limited | Backoff, pokušaj kasnije |
| `4430` | Chat window closed (24h posle termina) | Ne reconnect, prikaži `<ChatClosedNotice />` |
| `4500` | Internal server error | Reconnect sa backoff-om |

Custom kodovi u opsegu `4000–4999` su dozvoljeni po RFC 6455.

---

## 3. Envelope (zajednički format poruka)

Svaka poruka (server→client i client→server) je JSON sa ovim envelope-om:

```json
{
  "event": "<namespace>.<action>",
  "ts":    "2026-04-24T17:12:33.123Z",
  "data":  { ... }
}
```

| Polje | Tip | Obavezno | Opis |
|-------|-----|----------|------|
| `event` | string | ✅ | `<namespace>.<action>`. Namespace-ovi: `notification`, `chat`, `system`. |
| `ts` | ISO-8601 UTC | ✅ (server→client) | Vreme generisanja na serveru. Klijent ne šalje — server ga ignoriše. |
| `data` | object | ✅ | Event-specific payload. |

**Pravila:**
- Polja u `data` uvek `snake_case` (matching Pydantic response šeme).
- Datumi: ISO-8601 sa `Z` ili offset-om (`2026-05-10T10:00:00+02:00`).
- UUID-ovi: standardna `8-4-4-4-12` hex forma.
- `null` je dozvoljena vrednost za opciona polja (ne izostavljati ključ).

**Validacija:**
- Server parsira klijent poruku kroz Pydantic model po `event` tipu. Na validacionu grešku → `system.error` + close `4409` ako je kritična, inače bez close-a.
- Klijent preskače (log warn) eventove sa nepoznatim `event` nazivom (forward-compat).

### 3.1 Sistemski eventovi (oba kanala)

| Event | Smer | Data | Svrha |
|-------|------|------|-------|
| `system.ping` | S→C | `{ "seq": 42 }` | Heartbeat (svakih 25s). |
| `system.pong` | C→S | `{ "seq": 42 }` | Heartbeat odgovor. Server zatvara konekciju (1001) ako nema pong-a u 60s. |
| `system.error` | S→C | `{ "code": "...", "message": "..." }` | Ne-fatalna greška (validacija, limit). Nije close. |

**Error code-ovi (u `data.code`):**

| Code | Značenje |
|------|---------|
| `VALIDATION_FAILED` | Poruka ne prolazi Pydantic validaciju. |
| `RATE_LIMITED` | Previše poruka (chat > 1 / 500ms). |
| `CHAT_LIMIT_REACHED` | 20 poruka dostignuto (§ 5.4). |
| `CHAT_CLOSED` | Pokušaj slanja posle 24h prozora. |
| `PERMISSION_DENIED` | Mid-session promena RBAC-a (npr. user deaktiviran). |
| `INTERNAL_ERROR` | Neočekivana server greška. |

---

## 4. Notifications stream

**URL:** `WS /api/v1/notifications/stream?token=<JWT>`
**Scope:** 1 konekcija = 1 korisnik (iz `sub` claim-a JWT-a).
**Svrha:** Push in-app notifikacija kreiranih u `notification_service.create(...)` — zamenjuje polling za „bell" counter u top-bar-u.

### 4.1 Dispatch flow na backendu

```
notification_service.create(user_id, type, title, body, data)
  ├─ INSERT INTO notifications (...)
  ├─ INCR notif:unread:{user_id}
  └─ redis.publish("notif:pub:{user_id}", json.dumps({...}))
         │
         ▼
WS handler (subscribed via redis.pubsub().subscribe("notif:pub:{user_id}"))
  └─ websocket.send_json({ event: "notification.created", ts, data })
```

### 4.2 Server → client eventovi

#### `notification.created`

Šalje se kada `notification_service.create(...)` ubaci novi red.

```json
{
  "event": "notification.created",
  "ts": "2026-04-24T17:12:33.123Z",
  "data": {
    "id": "b3c9f0a8-1d2e-4a5b-9c7e-1f2d3a4b5c6d",
    "type": "APPOINTMENT_APPROVED",
    "title": "Termin je potvrđen",
    "body": "Vaš termin kod profesora Marka Markovića je potvrđen za 10.05.2026 u 10:00.",
    "data": {
      "appointment_id": "aa11bb22-...",
      "slot_datetime": "2026-05-10T10:00:00+02:00"
    },
    "is_read": false,
    "created_at": "2026-04-24T17:12:33.000Z"
  }
}
```

Payload je identičan `NotificationResponse` Pydantic šemi iz `backend/app/schemas/notification.py` (koji tek treba napisati u Koraku 4.2).

#### `notification.unread_count`

Sync counter-a. Server šalje:
1. Odmah posle `accept()` (initial sync) — čita `redis.get("notif:unread:{user_id}")`.
2. Posle svake promene (kreiranje novog, mark-read / mark-all-read iz REST endpointa — service publish-uje).

```json
{
  "event": "notification.unread_count",
  "ts": "2026-04-24T17:12:33.000Z",
  "data": { "count": 7 }
}
```

**Frontend ponašanje:** `<NotificationCenter />` čita ovu vrednost direktno za bell badge. Na `notification.created` dodatno zove `queryClient.invalidateQueries({ queryKey: ['notifications'] })` da osvježi dropdown listu.

### 4.3 Client → server eventovi

**Nijedan.** Sve mutacije idu kroz REST:
- `POST /api/v1/notifications/{id}/read`
- `POST /api/v1/notifications/read-all`

Posle REST poziva frontend radi `invalidateQueries` — ali server takođe publish-uje novi `notification.unread_count` da ostale browser tabove istog korisnika automatski sinhronizuje.

Jedini client→server event je `system.pong` (heartbeat).

### 4.4 Katalog `type` vrednosti

Frontend koristi ovaj enum za:
- Ikonu i boju notifikacije u `<NotificationItem />`.
- Da li prikazati toast (kritični tipovi) vs. samo bell badge update.

| `type` | Okidač (service) | `data` payload | Kritičan (toast) |
|--------|------------------|----------------|:---:|
| `APPOINTMENT_CONFIRMED` | profesor approve | `{ appointment_id, slot_datetime }` | ✅ |
| `APPOINTMENT_REJECTED` | profesor reject | `{ appointment_id, reason }` | ✅ |
| `APPOINTMENT_CANCELLED` | student otkazao | `{ appointment_id, cancelled_by_user_id, cancelled_by_role }` | ✅ |
| `APPOINTMENT_DELEGATED` | profesor delegate | `{ appointment_id, delegated_to_user_id }` | — |
| `APPOINTMENT_REMINDER_24H` | Celery beat 24h pre | `{ appointment_id, slot_datetime }` | — |
| `APPOINTMENT_REMINDER_1H` | Celery beat 1h pre | `{ appointment_id, slot_datetime }` | ✅ |
| `NEW_APPOINTMENT_REQUEST` | student booking (→ prof/asistent) | `{ appointment_id, student_name, slot_datetime }` | — |
| `NEW_CHAT_MESSAGE` | chat_service (šalje se **samo** ako je primalac offline na chat WS-u; da ne duplira toast dok je chat prozor otvoren) | `{ appointment_id, sender_name, preview }` | — |
| `WAITLIST_OFFER` | waitlist_service.issue_offer | `{ slot_id, expires_at, professor_id }` | ✅ |
| `STRIKE_ADDED` | strike_service | `{ points, total, reason, appointment_id }` | ✅ |
| `BLOCK_ACTIVATED` | strike_service | `{ blocked_until, total_points }` | ✅ |
| `BLOCK_LIFTED` | admin unblock | `{ admin_note }` | ✅ |
| `DOCUMENT_REQUEST_APPROVED` | admin approve | `{ document_request_id, document_type, pickup_date, admin_note }` | ✅ |
| `DOCUMENT_REQUEST_REJECTED` | admin reject | `{ document_request_id, document_type, admin_note }` | ✅ |
| `DOCUMENT_REQUEST_COMPLETED` | admin complete | `{ document_request_id }` | — |
| `BROADCAST` | broadcast_service fanout | `{ broadcast_id, channels }` | ✅ |

`type` vrednost je `VARCHAR(50)` u `notifications.type` koloni (vidi `backend/app/models/notification.py`). Backend treba da definiše Python `enum.Enum` u `app/models/enums.py` (npr. `NotificationType`) i koristi ga striktno — frontend `types/notification.ts` mora 1:1 mapirati.

### 4.5 Ponašanje pri impersonaciji

Kada admin impersonira korisnika X, novi access token ima `sub: X, imp: admin_id` (vidi § 6). WS handler se **vezuje za `sub` claim**, dakle stream prikazuje notifikacije korisnika X, ne admina.

Dok je impersonacija aktivna, admin ne dobija svoje notifikacije na otvorenom browser tabu (namerno — admin „vidi sistem kao X"). Kad klikne „Izađi iz ADMIN MODE" → frontend zatvara WS konekciju, swap-uje token, otvara novi WS — sada sa originalnim `admin_id` kao `sub`.

---

## 5. Chat namespace

**URL:** `WS /api/v1/appointments/{id}/chat?token=<JWT>`
**Scope:** 1 konekcija = 1 korisnik na 1 terminu. Više učesnika grupne konsultacije → više nezavisnih konekcija na istom endpoint-u.
**Svrha:** bidirektan per-appointment chat (max 20 poruka, auto-close 24h posle termina).

### 5.1 RBAC provere pri handshake-u

Server odbija (close code) u ovom redosledu:

1. Invalid JWT → `4401`.
2. Korisnik deaktiviran → `4401`.
3. Appointment ne postoji → `4404`.
4. Korisnik **nije**:
   - `appointment.lead_student_id`, ili
   - `AppointmentParticipant` sa `status ∈ {PENDING, CONFIRMED}`, ili
   - `appointment.professor.user_id`, ili
   - `AppointmentSubject.assistants` (za asistenta dodeljenog predmetu), ili
   - `appointment.delegated_to`, ili
   - `UserRole.ADMIN` (samo ako je impersonacija aktivna i impersonirani target je učesnik — admin bez impersonacije NEMA pristup tuđim chat-ovima).
   → `4403`.
5. `appointment.slot.slot_datetime + 24h <= now()` → `4430` (chat prozor zatvoren). Klijent NE pokušava reconnect; prikazuje `<ChatClosedNotice />`.

### 5.2 Dispatch flow na backendu

```
Client → WS "chat.send" { content }
  ├─ chat_service.send_message(appointment_id, sender_id, content)
  │    ├─ validacije (§ 5.4)
  │    ├─ INSERT INTO ticket_chat_messages (...)
  │    ├─ INCR chat:count:{appointment_id}   (za enforcement limita)
  │    └─ redis.publish("chat:pub:{appointment_id}", json.dumps({...}))
  │
  ▼ (svi subscribed WS-ovi, uključujući sender-ov — za echo)
WS handlers → websocket.send_json({ event: "chat.message", ts, data })

(paralelno, za offline učesnike:)
chat_service loops participants → if not connected to chat WS
  → notification_service.create(type="NEW_CHAT_MESSAGE", ...)
    (stiže preko notifications stream-a § 4)
```

### 5.3 Server → client eventovi

#### `chat.history`

Šalje se **jednom**, odmah posle `accept()`. Inicijalni snapshot svih postojećih poruka (ordered ASC po `created_at`, max 20).

```json
{
  "event": "chat.history",
  "ts": "2026-04-24T17:12:33.000Z",
  "data": {
    "messages": [
      {
        "id": "uuid",
        "sender": {
          "id": "uuid",
          "full_name": "Marko Marković",
          "role": "PROFESOR"
        },
        "content": "Zdravo, šaljem materijal.",
        "created_at": "2026-04-24T16:30:00.000Z",
        "message_number": 1
      }
    ],
    "total": 1,
    "remaining": 19,
    "closes_at": "2026-05-11T10:00:00+02:00"
  }
}
```

- `message_number`: redni broj 1..20 (za UI counter „X/20").
- `remaining`: 20 - total.
- `closes_at`: `slot_datetime + 24h` — frontend koristi za countdown.

#### `chat.message`

Broadcast nove poruke svim subscribed WS-ovima (uključujući pošiljaoca — za echo i potvrdu o uspelom persist-u).

```json
{
  "event": "chat.message",
  "ts": "2026-04-24T17:12:33.000Z",
  "data": {
    "id": "uuid",
    "sender": {
      "id": "uuid",
      "full_name": "Marko Marković",
      "role": "PROFESOR"
    },
    "content": "Zdravo, šaljem materijal.",
    "created_at": "2026-04-24T17:12:33.000Z",
    "message_number": 7,
    "remaining": 13
  }
}
```

#### `chat.limit_reached`

Šalje se kad `message_number === 20`. Klijent disable-uje input i prikazuje „Dostignut je limit od 20 poruka".

```json
{
  "event": "chat.limit_reached",
  "ts": "2026-04-24T17:12:33.000Z",
  "data": { "total": 20 }
}
```

#### `chat.closed`

Šalje se ako server zatvori chat mid-session (edge case: termin izbrisan, status promenjen u CANCELLED, admin force-close). Po slanju, server radi `websocket.close(4430)`.

```json
{
  "event": "chat.closed",
  "ts": "2026-04-24T17:12:33.000Z",
  "data": { "reason": "APPOINTMENT_CANCELLED" | "WINDOW_EXPIRED" | "ADMIN_ACTION" }
}
```

### 5.4 Client → server eventovi

#### `chat.send`

Jedini mutacioni event.

```json
{
  "event": "chat.send",
  "data": { "content": "Tekst poruke — max 1000 znakova." }
}
```

**Validacije na serveru:**

| Pravilo | Akcija na neuspeh |
|---------|-------------------|
| `content.strip()` nije prazan | `system.error` + `VALIDATION_FAILED` |
| `len(content) <= 1000` | `system.error` + `VALIDATION_FAILED` |
| `chat:count:{appointment_id}` < 20 | `system.error` + `CHAT_LIMIT_REACHED`, pa `close 4409` |
| Rate limit: < 1 poruka / 500ms po sender-u | `system.error` + `RATE_LIMITED` |
| `slot_datetime + 24h > now` | `system.error` + `CHAT_CLOSED`, pa `close 4430` |

Poruka se persist-uje **tek posle** svih validacija (ne da se upiše pa se odustane).

### 5.5 Ponašanje sa više učesnika (grupna konsultacija)

Grupna konsultacija (`appointment.is_group = true`): svi `AppointmentParticipant` sa `status = CONFIRMED` (+ lead_student) mogu da se konektuju. Limit od 20 poruka je **ukupan za termin**, ne po učesniku. Svi vide iste poruke.

---

## 6. Impersonation — JWT `imp` claim

ROADMAP § 4.4 definiše impersonation endpointe. Ova sekcija specificira **tačan format JWT-a** koji backend vraća, jer ga frontend mora dekodirati da prikaže `<ImpersonationBanner />`.

### 6.1 REST endpoint-i

#### Start

```
POST /api/v1/admin/impersonate/{user_id}
Authorization: Bearer <ADMIN_ACCESS_TOKEN>
```

**201 Created:**

```json
{
  "access_token": "<IMPERSONATION_JWT>",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "<target_user_id>",
    "email": "student@student.fon.bg.ac.rs",
    "first_name": "Ana",
    "last_name": "Anić",
    "role": "STUDENT",
    "faculty": "FON",
    "is_active": true,
    "is_verified": true,
    "profile_image_url": null,
    "created_at": "..."
  },
  "impersonator": {
    "id": "<admin_id>",
    "email": "admin@fon.bg.ac.rs",
    "first_name": "Admin",
    "last_name": "Adminović"
  },
  "imp_expires_at": "2026-04-24T17:42:33Z"
}
```

**Pravila:**
- Admin mora imati `role = ADMIN`. Inače `403`.
- Target user mora biti aktivan. Inače `422`.
- Admin **ne može** impersonirati drugog ADMIN-a (zaštita). `403 IMPERSONATE_ADMIN_FORBIDDEN`.
- Audit log: `AuditLog(admin_id, impersonated_user_id=user_id, action="IMPERSONATE_START", ip_address=client_ip)`.
- **Impersonation TTL je kraći nego regularni access token** — preporuka 30 minuta (`expires_in: 1800`). Ovo ograničava window ako token iscuri.

#### End

```
POST /api/v1/admin/impersonate/end
Authorization: Bearer <IMPERSONATION_JWT>
```

**200 OK:**

```json
{
  "access_token": "<RESTORED_ADMIN_ACCESS_TOKEN>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { /* originalni admin UserResponse */ }
}
```

- Backend čita `imp` claim iz trenutnog JWT-a (taj JWT je impersonation token). Generiše novi admin token sa `sub=imp, role=ADMIN`.
- Audit: `AuditLog(admin_id=imp, impersonated_user_id=sub, action="IMPERSONATE_END", ip_address=client_ip)`.
- Ako je refresh token u cookie-u i dalje valjan za admin sesiju, samo se access token menja; refresh cookie ostaje netaknut.

### 6.2 Format impersonation access tokena

Standardni access token (trenutno stanje):

```json
{
  "sub":   "<user_id>",
  "role":  "STUDENT" | "ASISTENT" | "PROFESOR" | "ADMIN",
  "email": "user@domain.rs",
  "exp":   1716570753,
  "type":  "access"
}
```

Impersonation access token dodaje tri `imp*` polja:

```json
{
  "sub":       "<target_user_id>",
  "role":      "<target_user_role>",
  "email":     "<target_user_email>",
  "imp":       "<admin_id>",
  "imp_email": "admin@fon.bg.ac.rs",
  "imp_name":  "Admin Adminović",
  "exp":       1716572553,
  "type":      "access"
}
```

| Claim | Tip | Opis |
|-------|-----|------|
| `imp` | UUID string | ID admin korisnika koji je pokrenuo impersonaciju. **Prisustvo ovog polja = impersonacija je aktivna.** |
| `imp_email` | string | Email admin korisnika (UX, za banner tekst). |
| `imp_name` | string | Full name admina (UX). |

**Backend `get_current_user` dependency** (CLAUDE.md § 3, ROADMAP § 4.4) čita `payload` i postavlja atribute na `User` objektu:

```python
user._impersonated_by_admin_id = payload.get("imp")  # None ako ne postoji
user._impersonated_by_email    = payload.get("imp_email")
user._impersonated_by_name     = payload.get("imp_name")
```

Ovo je **in-memory flag na ORM objektu**, ne DB kolona. Ne persist-uje se u bazi.

### 6.3 Frontend detekcija (za `<ImpersonationBanner />`)

`frontend/lib/utils/jwt.ts` dekodira payload (bez verifikacije potpisa — to radi backend):

```ts
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split('.');
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function isImpersonationToken(token: string): boolean {
  const p = decodeJwtPayload(token);
  return !!p && typeof p.imp === 'string';
}
```

Flow (vidi `FRONTEND_STRUKTURA.md` § 3.6):

1. Posle `adminApi.impersonateStart(userId)` → `useImpersonationStore.setImpersonating({ adminId: payload.imp, adminEmail: payload.imp_email, adminName: payload.imp_name, originalAdmin: authStore.user })`.
2. `useAuthStore.setAuth({ user: response.user, accessToken: response.access_token })`.
3. `<ImpersonationBanner />` renderuje se **uvek** kad `useImpersonationStore.isImpersonating === true`. Tekst: `"ADMIN MODE — Impersonirate: [target_full_name] • Admin: [imp_name]"` + dugme „Izađi iz ADMIN MODE".
4. `NotificationStream` komponenta (u `app/providers.tsx`) detektuje promenu access tokena → zatvara staru WS konekciju (`ws.close(1000)`) → otvara novu sa novim tokenom. Tako admin vidi notifikacije impersoniranog korisnika.
5. Klik na „Izađi" → `adminApi.impersonateEnd()` → isti flow obrnuto: restore admin token + user, clear impersonation store, WS se ponovo reconnect-uje.

### 6.4 WS handshake pri impersonaciji

WS handler ne radi ništa posebno — `decode_access_token` vraća payload sa `imp` claim-om, ali `sub` je i dalje target user. Scope (Redis kanal, RBAC provere) se računaju po `sub`.

**Opciono (preporuka):** pri svakom WS accept-u sa `imp` claim-om, upisati `AuditLog(action="IMPERSONATE_WS_CONNECT", admin_id=imp, impersonated_user_id=sub, ip_address=client_host)`. Ovo daje granularan trag, ali može generisati puno zapisa za dug-lived konekcije — zato opciono.

---

## 7. Heartbeat, reconnect, resiliency

### 7.1 Heartbeat

- Server šalje `system.ping` svakih **25 sekundi**.
- Klijent u roku od **10s** odgovara `system.pong` sa istim `seq`.
- Ako server ne dobije `pong` u 60s od poslednjeg ping-a → `close(1001)`.
- Klijent detektuje gubitak konekcije preko `onclose` event-a WebSocket-a.

### 7.2 Klijent reconnect strategija

```
Pokušaj 1: 1s
Pokušaj 2: 2s
Pokušaj 3: 4s
Pokušaj 4: 8s
Pokušaj 5+: 30s (cap)
```

Sa jitter-om ±20% da se izbegne thundering herd. Reset backoff-a posle uspešnog `open`-a.

**Ne reconnect-uj** ako je close code ∈ `{ 4403, 4404, 4430 }` — te greške su permanentne za konkretan scope.

Na `4401` (token expired):
1. Pozovi `authApi.refresh()` da dobiješ novi access token.
2. Ako uspe → reconnect sa novim tokenom.
3. Ako ne uspe → `clearAuth()` + redirect na `/login`.

### 7.3 Propušteni eventovi

Per-user notifikacije **se ne buferuju** dok je klijent offline — publish je fire-and-forget. Zato posle svakog reconnect-a:

```ts
queryClient.invalidateQueries({ queryKey: ['notifications'] });
```

Persistence (DB) je source of truth; REST `GET /api/v1/notifications` vraća listu sa `is_read`. WS je samo push-kanal za real-time UX.

Za chat isto važi: posle reconnect-a server šalje `chat.history` sa svim postojećim porukama (do 20), klijent zameni lokalni state.

---

## 8. Kontrakt tipova (Python ↔ TypeScript)

### 8.1 Backend (Pydantic)

Napisati u `backend/app/schemas/notification.py` (ROADMAP § 4.2) i `backend/app/schemas/appointment.py` (ROADMAP § 3.3):

```python
# schemas/notification.py
from enum import Enum
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class NotificationType(str, Enum):
    APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED"
    APPOINTMENT_REJECTED  = "APPOINTMENT_REJECTED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_DELEGATED = "APPOINTMENT_DELEGATED"
    APPOINTMENT_REMINDER_24H = "APPOINTMENT_REMINDER_24H"
    APPOINTMENT_REMINDER_1H  = "APPOINTMENT_REMINDER_1H"
    NEW_APPOINTMENT_REQUEST  = "NEW_APPOINTMENT_REQUEST"
    NEW_CHAT_MESSAGE         = "NEW_CHAT_MESSAGE"
    WAITLIST_OFFER           = "WAITLIST_OFFER"
    STRIKE_ADDED             = "STRIKE_ADDED"
    BLOCK_ACTIVATED          = "BLOCK_ACTIVATED"
    BLOCK_LIFTED             = "BLOCK_LIFTED"
    DOCUMENT_REQUEST_APPROVED  = "DOCUMENT_REQUEST_APPROVED"
    DOCUMENT_REQUEST_REJECTED  = "DOCUMENT_REQUEST_REJECTED"
    DOCUMENT_REQUEST_COMPLETED = "DOCUMENT_REQUEST_COMPLETED"
    BROADCAST                  = "BROADCAST"

class NotificationResponse(BaseModel):
    id: UUID
    type: NotificationType
    title: str
    body: str
    data: dict | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}

# schemas/chat.py (ili u schemas/appointment.py)
class ChatSender(BaseModel):
    id: UUID
    full_name: str
    role: str  # UserRole.value

class ChatMessageResponse(BaseModel):
    id: UUID
    sender: ChatSender
    content: str
    created_at: datetime
    message_number: int
```

### 8.2 Frontend (TypeScript)

U `frontend/types/notification.ts` i `frontend/types/chat.ts`:

```ts
// types/notification.ts
export type NotificationType =
  | 'APPOINTMENT_CONFIRMED'
  | 'APPOINTMENT_REJECTED'
  | 'APPOINTMENT_CANCELLED'
  | 'APPOINTMENT_DELEGATED'
  | 'APPOINTMENT_REMINDER_24H'
  | 'APPOINTMENT_REMINDER_1H'
  | 'NEW_APPOINTMENT_REQUEST'
  | 'NEW_CHAT_MESSAGE'
  | 'WAITLIST_OFFER'
  | 'STRIKE_ADDED'
  | 'BLOCK_ACTIVATED'
  | 'BLOCK_LIFTED'
  | 'DOCUMENT_REQUEST_APPROVED'
  | 'DOCUMENT_REQUEST_REJECTED'
  | 'DOCUMENT_REQUEST_COMPLETED'
  | 'BROADCAST';

export interface NotificationResponse {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  data: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string; // ISO-8601
}

// types/chat.ts
export interface ChatSender {
  id: string;
  full_name: string;
  role: 'STUDENT' | 'ASISTENT' | 'PROFESOR' | 'ADMIN';
}

export interface ChatMessageResponse {
  id: string;
  sender: ChatSender;
  content: string;
  created_at: string;
  message_number: number;
}

// WS envelope
export interface WsEnvelope<TEvent extends string, TData> {
  event: TEvent;
  ts?: string;
  data: TData;
}

export type NotificationWsEvent =
  | WsEnvelope<'notification.created', NotificationResponse>
  | WsEnvelope<'notification.unread_count', { count: number }>
  | WsEnvelope<'system.ping', { seq: number }>
  | WsEnvelope<'system.error', { code: string; message: string }>;

export type ChatWsEvent =
  | WsEnvelope<'chat.history', { messages: ChatMessageResponse[]; total: number; remaining: number; closes_at: string }>
  | WsEnvelope<'chat.message', ChatMessageResponse & { remaining: number }>
  | WsEnvelope<'chat.limit_reached', { total: number }>
  | WsEnvelope<'chat.closed', { reason: 'APPOINTMENT_CANCELLED' | 'WINDOW_EXPIRED' | 'ADMIN_ACTION' }>
  | WsEnvelope<'system.ping', { seq: number }>
  | WsEnvelope<'system.error', { code: string; message: string }>;
```

---

## 9. Test matrica (acceptance)

| # | Scenario | Očekivano |
|---|----------|-----------|
| 1 | Notifications WS bez `token` query param-a | Close `4401` odmah posle connect-a |
| 2 | Notifications WS sa istekao JWT-om | Close `4401` |
| 3 | Notifications WS uspešan handshake | `accept()` + odmah `notification.unread_count` event |
| 4 | Student zakaže termin dok je profesor konektovan | Profesor dobija `notification.created` event < 1s bez refresh-a |
| 5 | Chat WS za ne-učesnika | Close `4403` |
| 6 | Chat WS 25h posle `slot_datetime` | Close `4430` |
| 7 | Chat send 21. poruke | `system.error` + `CHAT_LIMIT_REACHED` + close `4409` |
| 8 | Chat send u isto vreme iz 2 browsera | Obe persist-uju ali počevši od 21. broadcast je odbijen |
| 9 | Admin impersonira studenta sa aktivnim WS | Admin-ov stari WS ostaje povezan na admin-ov `notif:pub:{admin_id}`; novi WS (otvoren po swap-u tokena) je na `notif:pub:{student_id}` |
| 10 | Network drop 10s → reconnect | Klijent uradi backoff, uspe u roku 10s; `invalidateQueries` refetchuje missed notifs |
| 11 | Server heartbeat timeout | Close `1001` od servera, klijent reconnect-uje |
| 12 | Impersonation JWT bez `imp` claim-a (regularni admin login) | `<ImpersonationBanner />` sakriven |
| 13 | Impersonation JWT sa `imp` claim-om | `<ImpersonationBanner />` vidljiv, prikazuje `imp_name` |
| 14 | Admin pokušava da impersonira drugog ADMIN-a | `403 IMPERSONATE_ADMIN_FORBIDDEN` |

Testove izvršiti ručno pre merge-a Faze 4 + pytest integracioni (ROADMAP § 5.4).

---

## 10. Otvorena pitanja (za sync Filip ⇄ Stefan pre implementacije Faze 4)

Ova pitanja **moraju** biti dogovorena pre početka `/api/v1/notifications/stream` i `/api/v1/appointments/{id}/chat` implementacije:

1. **Cross-tab sinhronizacija same korisnika:** Ako isti korisnik ima 2 tab-a otvorena (mobile + desktop), obe WS konekcije subscribe-uju na `notif:pub:{user_id}`. Redis pub/sub bacast-uje na obe — to je OK. Ali `notif:unread:{user_id}` counter se menja po `mark_read` u jednom tabu — da li drugi tab dobija novi `notification.unread_count` event? **Predlog:** `notification_service.mark_read` i `mark_all_read` takođe publish-uju `notification.unread_count` event na isti kanal. **Potvrditi.**

2. **`NEW_CHAT_MESSAGE` de-duplikacija:** Ako je učesnik online na chat WS-u, chat_service **ne** treba da kreira `NEW_CHAT_MESSAGE` notifikaciju (toast bi bio duplikat jer korisnik već vidi poruku u chat-u). Za ovo chat_service mora da zna da li učesnik ima aktivnu chat WS konekciju — upit u `chat:session:{appointment_id}` Redis hash (koji je već u `Arhitektura_i_Tehnoloski_Stek.md` § 4). **Potvrditi da će se taj hash zaista koristiti.**

3. **`socket.io-client` uklanjanje:** ROADMAP i CLAUDE.md pominju `socket.io-client`, ali ova šema kaže native WS. **Odluka:** ukloniti iz `frontend/package.json` u istom PR-u kao implementacija chat-a. Potvrditi.

4. **Impersonation + refresh token:** Da li impersonation token ima svoj refresh token (novi cookie sa scoped path-om), ili je samo access token scope-ovan a refresh ostaje admin-ov? **Predlog:** impersonation **nema** refresh — admin mora da re-impersonira ako access istekne (30 min). Ovo je jednostavnije i sigurnije. Potvrditi.

5. **Broadcast skala:** Ako admin pošalje broadcast na 2000 korisnika, `broadcast_tasks.fanout_broadcast` kreira 2000 notifikacija i 2000 redis publish-eva. Test pod Redis load-om — radi li `notification.unread_count` u realnom vremenu ili kasni? Ovo je load-test tema za § 5.4.

6. **Mobilni PWA + WS lifecycle:** iOS Safari u PWA modu prekida WS konekciju čim se app backgrounduje. Očekujemo česte reconnect-e. Backoff strategija iz § 7.2 mora ovo da hendluje gracefully (bez logout-a). Test ručno na iOS.

---

## 11. Implementacioni pointeri (za Fazu 4)

Kad Stefan krene implementaciju, pointeri za brz start:

### Notifications stream (ROADMAP § 4.2)

```python
# backend/app/api/v1/notifications.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from redis.asyncio import Redis
# ...

router = APIRouter()

@router.websocket("/stream")
async def notifications_stream(
    websocket: WebSocket,
    token: str = Query(...),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    # 1. Auth
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4401)
        return

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # 2. Initial unread count
    count = int(await redis.get(f"notif:unread:{user_id}") or 0)
    await websocket.send_json({
        "event": "notification.unread_count",
        "ts": datetime.now(timezone.utc).isoformat(),
        "data": {"count": count},
    })

    # 3. Subscribe + forward
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"notif:pub:{user_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"])  # already JSON string
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"notif:pub:{user_id}")
        await pubsub.close()
```

### Chat (ROADMAP § 4.1)

Slično, dodatno:
- Pre `accept()`: RBAC check (§ 5.1) + 24h window check.
- Po `accept()`: `chat.history` event sa DB query-jem poslednjih 20 poruka.
- Dva taska u `asyncio.gather(...)`: (a) `websocket.receive_json()` loop za `chat.send`, (b) `pubsub.listen()` loop za relay.

### Frontend WS klijent (Faza 5)

```ts
// frontend/lib/ws/notification-socket.ts
export function createNotificationSocket(token: string, onEvent: (e: NotificationWsEvent) => void) {
  const url = `${WS_BASE_URL}/api/v1/notifications/stream?token=${encodeURIComponent(token)}`;
  const ws = new WebSocket(url);

  ws.onmessage = (ev) => {
    try { onEvent(JSON.parse(ev.data)); } catch { /* ignore */ }
  };
  // ... heartbeat, reconnect backoff
  return ws;
}
```

---

*Ovaj fajl je živi ugovor. Pri promeni event-a, close code-a, ili formata tokena — ažurirati ovde **i** odgovarajuće Pydantic/TypeScript šeme u istom PR-u.*
