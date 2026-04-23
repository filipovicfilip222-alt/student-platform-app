# Specifikacija Zahteva Proizvoda (PRD)
## Platforma za upravljanje univerzitetskim konsultacijama i komunikacijom
## FON & ETF Univerzitet u Beogradu

**Status:** Odobreno  
**Verzija:** 2.0  
**Poslednja izmena:** April 2025  

---

## Sadržaj

1. [Arhitektura Sistema i Bezbednost](#1-arhitektura-sistema-i-bezbednost)
2. [Modul za Studente (Student Portal)](#2-modul-za-studente-student-portal)
3. [Modul za Profesore i Asistente (Staff Portal)](#3-modul-za-profesore-i-asistente-staff-portal)
4. [Modul za Studentsku Službu (Admin Panel)](#4-modul-za-studentsku-službu-admin-panel)
5. [Sistemski i Quality of Life Dodaci](#5-sistemski-i-quality-of-life-dodaci)
6. [Planirano za V2](#6-planirano-za-v2)

---

## 1. Arhitektura Sistema i Bezbednost

Sistem je dizajniran kao **zatvorena platforma** namenjena isključivo akademskom osoblju i aktivnim studentima **Fakulteta organizacionih nauka (FON)** i **Elektrotehničkog fakulteta (ETF)** Univerziteta u Beogradu.

### 1.1 Zatvorena Registracija

- Onemogućen javni "Sign Up" — ne postoji obrazac za samostalnu registraciju.
- **Studenti** se registruju isključivo sa zvaničnom fakultetskom email adresom:
  - `@student.fon.bg.ac.rs`
  - `@student.etf.bg.ac.rs`
- Sistem **automatski odbija** pokušaj registracije sa bilo kojom drugom email domenom.
- **Profesori** dobijaju naloge sa:
  - `@etf.bg.ac.rs`
  - `@fon.bg.ac.rs`
- Administrator može ručno kreirati nalog ili pokrenuti **Bulk Import** iz CSV fajla.
- **Studentska služba** ima jedan zajednički nalog (`sluzba@fon.bg.ac.rs` / `sluzba@etf.bg.ac.rs`).

### 1.2 Autentifikacija (V1 — Jednostavna)

> **Napomena V1:** Keycloak SSO se **ne implementira u prvoj verziji** radi brzine razvoja. Koristi se direktna email/password autentifikacija sa JWT tokenima. Keycloak se dodaje u kasnijoj fazi kada je MVP funkcionalan i testiran.

#### V1 Auth mehanizam:
- Email + password login forma
- Validacija email domene pri registraciji (whitelist: `@student.fon.bg.ac.rs`, `@student.etf.bg.ac.rs`, `@fon.bg.ac.rs`, `@etf.bg.ac.rs`)
- JWT access token (expires: 1h) + refresh token (expires: 7 dana)
- Lozinke se čuvaju hash-ovane (bcrypt, 12 rounds)
- "Zaboravljena lozinka" putem email verifikacije

#### Unapred kreirani nalozi (seed data):
```
# Studentska služba
sluzba@fon.bg.ac.rs    — uloga: ADMIN
sluzba@etf.bg.ac.rs    — uloga: ADMIN

# Primer profesora (bez pravih ličnih podataka)
profesor1@fon.bg.ac.rs — uloga: PROFESOR
profesor2@fon.bg.ac.rs — uloga: PROFESOR
profesor1@etf.bg.ac.rs — uloga: PROFESOR
asistent1@fon.bg.ac.rs — uloga: ASISTENT

# Studenti se registruju sami sa validiranom email adresom
```

### 1.3 RBAC (Role-Based Access Control)

Sistem ima 4 strogo definisane uloge:

| Uloga | Opis | Ključne dozvole |
|-------|------|-----------------|
| `STUDENT` | Aktivni student (auto-dodeljena pri registraciji sa student domenom) | Pretraga, zakazivanje, upload fajlova, chat, zahtevi za dokumente |
| `ASISTENT` | Asistent na predmetu | Odobravanje/odbijanje termina, CRM beleške (samo za dodeljene predmete) |
| `PROFESOR` | Nastavno osoblje | Puno upravljanje kalendarom, delegiranje, šabloni, CRM |
| `ADMIN` | Studentska služba | CRUD svih korisnika, bulk import, broadcast, strike menadžment, obrada zahteva za dokumente |

---

## 2. Modul za Studente (Student Portal)

### 2.1 Otkrivanje i Pretraga Profesora

#### Smart Search & Filter
- Pretraga po: imenu, prezimenu, katedri, predmetu
- Pretraga po **ključnim rečima** (oblasti u profilu profesora)
- Filteri: tip konsultacija (Uživo / Online), dostupnost (slobodnih termina danas / ove nedelje), fakultet (FON / ETF)

#### Profili Profesora
Svaki profesor ima mini-profil koji sadrži:
- Profilna slika, zvanje, katedra, fakultet
- Broj kabineta i opis lokacije
- Lista predmeta koje predaje
- **FAQ sekcija** — Profesor postavlja najčešća pitanja i odgovore

> **UX pravilo:** Student vidi FAQ **pre** nego što klikne na "Zakaži".

---

### 2.2 Sistem Zakazivanja

#### Interaktivni Kalendar
- Prikaz slobodnih slotova u realnom vremenu
- Redis pessimistic locking (TTL: 30 sekundi) pri početku procesa zakazivanja

#### Tipovi Konsultacija
| Tip | Opis |
|-----|------|
| **Uživo** | Prikazuje broj i opis lokacije kabineta |
| **Online** | Prikazuje Teams / Zoom link |

#### Kontekstualni Zahtev (obavezna polja)
1. **Tema** — Dropdown: Seminarski rad / Predavanja & Teorija / Priprema za ispit / Projekat / Ostalo
2. **Kratak opis** — min 20, max 500 karaktera
3. **Fajlovi** (opciono) — do 5MB, formati: PDF, DOCX, XLSX, PNG, JPG, ZIP, .py, .java, .cpp

#### Grupne Konsultacije
- Vođa tima zakazuje i taguje kolege po email-u
- Tagovani dobijaju notifikaciju i potvrđuju dolazak (rok: 24h)

#### Lista Čekanja (Waitlist)
- Aktivira se kada je profesor potpuno bukiran
- Pri otkazivanju: automatski nudi slot prvom na listi (vremenski prozor: 2 sata)
- Notifikacija putem email + in-app

---

### 2.3 Upravljanje Terminima

| Situacija | Akcija | Posledica |
|-----------|--------|-----------|
| Otkazivanje > 24h pre termina | Slobodno | — |
| Otkazivanje < 24h pre termina | Zabranjeno osim zahteva | 1 Strike poen |
| Nepojavljivanje bez otkazivanja | Automatska detekcija (30min posle) | 2 Strike poena |

---

### 2.4 Zahtevi za Dokumente (Studentska Služba)

Student može podnositi zahteve za zvanične dokumente direktno iz aplikacije.

#### Tipovi dokumenata
- Potvrda o statusu studenta
- Uverenje o položenim ispitima
- Uverenje o proseku
- Prepis ocena (transcript)
- Potvrda o uplati školarine
- Ostalo (slobodan tekst)

#### Tok zahteva
1. Student bira tip dokumenta i upisuje napomenu (opciono)
2. Zahtev odlazi u inbox studentske službe
3. Admin (studentska služba) pregleda zahtev i **odobrava ili odbija** sa obrazloženjem
4. Pri odobrenju, student dobija obaveštenje: *"Vaš dokument je spreman za preuzimanje. Možete ga pokupiti [datum] u studentskoj službi u radno vreme 09:00-13:00."*
5. Admin može uneti specifičan datum i napomenu za preuzimanje

#### Statusi zahteva
- `PENDING` — Čeka obradu
- `APPROVED` — Odobren, student obavešten o datumu preuzimanja
- `REJECTED` — Odbijen sa obrazloženjem
- `COMPLETED` — Student preuzeo dokument (admin označava)

---

### 2.5 Univerzitetska Baza Znanja

#### Google Programmable Search Engine (PSE)
- Pretraga ograničena na domene `fon.bg.ac.rs` i `etf.bg.ac.rs`
- Live pretraga putem Google API-ja, bez lokalnog čuvanja

---

## 3. Modul za Profesore i Asistente (Staff Portal)

### 3.1 Upravljanje Vremenom (Availability Engine)

#### Dinamički Šabloni (Recurring Slots)
- Ponavljajući termini sa pravilima: nedeljno, mesečno, date range
- Trajanje slota: 30/45/60 minuta
- Maksimalan broj studenata po slotu (1-N za grupne)
- Tip: Uživo / Online

#### Buffer Vreme
- Automatska pauza između termina (default: 5 minuta, konfigurabilno)

#### Override i Blackout Datumi
- Blokada dana/perioda — ako postoje zakazani termini, automatski se šalje notifikacija studentima i oni idu na prioritetnu waitlist

---

### 3.2 Obrada Zahteva

#### Auto-Approve vs. Manual-Approve
- Konfigurabilno po tipu slota (recurring = auto, posebni = manual)
- Asistent ima odvojenu konfiguraciju

#### Delegiranje Asistentu
- Prosleđivanje zahteva asistentu (mora biti dodeljen istom predmetu)

#### Šabloni Odgovora (Canned Responses)
- Brzi odgovori pri odbijanju zahteva
- Profesor može dodavati sopstvene šablone

---

### 3.3 Komunikacija

#### In-App Ticket Chat
- Mini-chat vezan za svaki termin (max 20 poruka)
- Automatski se zatvara 24h posle termina
- WebSocket implementacija

#### Privatne CRM Beleške
- Interne beleške o studentima (vidljive samo osoblju)
- Trajno čuvane, asocirane po paru (profesor, student)

---

## 4. Modul za Studentsku Službu (Admin Panel)

### 4.1 Upravljanje Korisnicima

#### Centralni Registar
- Puni CRUD za sve korisnike
- **Bulk Import** studenata iz CSV (format: `ime, prezime, email, indeks, smer, godina_upisa`)
- Validacija pre uvoza (duplikati, neispravan email, nevalidan domen)
- Preview pre potvrde uvoza

#### Impersonacija
- Dijagnostičko "ulogovanje kao" bilo koji korisnik
- Obavezni audit log (timestamp, IP, akcije)
- Crveni baner u UI: "ADMIN MODE — Impersonirate [Ime Korisnika]"

#### Globalni Broadcast
- Ciljano slanje obaveštenja (ceo fakultet / smer / godina / samo profesori)
- Kanali: in-app baner + email (max 5 minuta delay) + push

### 4.2 Obrada Zahteva za Dokumente

- Inbox svih zahteva sa filterima (status, tip dokumenta, student, datum)
- Odobrenje zahteva: unos datuma preuzimanja i napomene
- Odbijanje zahteva: obavezno obrazloženje
- Označavanje zahteva kao `COMPLETED` kada student preuzme dokument
- Pregled istorije svih zahteva

---

## 5. Sistemski i Quality of Life Dodaci

### 5.1 Strike Sistem

| Prekršaj | Poeni | Automatizacija |
|----------|-------|----------------|
| Otkazivanje < 12h | +1 | Automatski |
| Nepojavljivanje | +2 | Automatski 30min posle termina |

| Poeni | Posledica |
|-------|-----------|
| 1-2 | Upozorenje |
| 3 | Blokada 14 dana |
| 4+ | Svaki novi prekršaj +7 dana |

Admin može skinuti blokadu uz obrazloženje.

### 5.2 Pametne Notifikacije

#### Automatski Emailovi

| Okidač | Primalac | Vreme |
|--------|---------|-------|
| Termin potvrđen | Student | Odmah |
| Termin odbijen | Student | Odmah + razlog |
| Podsetnik | Student + Profesor | 24h pre |
| Podsetnik | Student + Profesor | 1h pre |
| Termin otkazan | Student | Odmah |
| Waitlist slot slobodan | Sledeći | Odmah (2h prozor) |
| Strike dodat | Student | Odmah |
| Blokada aktivirana | Student | Odmah |
| Zahtev za dokument odobren | Student | Odmah + datum preuzimanja |
| Zahtev za dokument odbijen | Student | Odmah + razlog |

### 5.3 PWA (Progressive Web App)

- Instalacija na iOS/Android bez App Store/Play Store
- Offline pregled poslednjih termina i notifikacija (read-only)
- Web Push API za push notifikacije

---

## 6. Planirano za V2

> Ove funkcionalnosti **nisu deo MVP-a**.

### 6.1 Keycloak SSO Integracija
- Zamena jednostavne JWT autentifikacije sa enterprise SSO
- Active Directory / LDAP sinhronizacija
- G-Suite i Microsoft 365 integracija
- Realm Roles, User Federation

### 6.2 Analytics Dashboard
- Statistike za profesore: najpopularniji termini, tematske kategorije
- Statistike za admina: aktivnost po smerovima, no-show stopa

### 6.3 Mobile App
- React Native wrapper ako PWA nije dovoljna

---

*Dokument je deo `docs/` foldera projekta i služi kao jedini source of truth za poslovne zahteve.*
