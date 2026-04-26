import enum


class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    ASISTENT = "ASISTENT"
    PROFESOR = "PROFESOR"
    ADMIN = "ADMIN"


class Faculty(str, enum.Enum):
    FON = "FON"
    ETF = "ETF"


class ConsultationType(str, enum.Enum):
    UZIVO = "UZIVO"
    ONLINE = "ONLINE"


class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class TopicCategory(str, enum.Enum):
    SEMINARSKI = "SEMINARSKI"
    PREDAVANJA = "PREDAVANJA"
    ISPIT = "ISPIT"
    PROJEKAT = "PROJEKAT"
    OSTALO = "OSTALO"


class ParticipantStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"


class StrikeReason(str, enum.Enum):
    LATE_CANCEL = "LATE_CANCEL"
    NO_SHOW = "NO_SHOW"


class DocumentType(str, enum.Enum):
    POTVRDA_STATUSA = "POTVRDA_STATUSA"
    UVERENJE_ISPITI = "UVERENJE_ISPITI"
    UVERENJE_PROSEK = "UVERENJE_PROSEK"
    PREPIS_OCENA = "PREPIS_OCENA"
    POTVRDA_SKOLARINE = "POTVRDA_SKOLARINE"
    OSTALO = "OSTALO"


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


# ── Notifications ─────────────────────────────────────────────────────────────
# 16 vrednosti uparene 1:1 sa frontend/types/notification.ts::NotificationType
# i docs/websocket-schema.md §4.4 (redosled iz tabele kataloga).
#
# Backend kolona ``notifications.type`` je VARCHAR(50) (vidi
# ``alembic/versions/20260423_0001_initial_schema.py:306``), NIJE PG ENUM —
# zato dodavanje novih vrednosti ne traži migraciju. Service sloj koristi
# ovu klasu za striktnu validaciju ulaza; baza prihvata bilo koji string
# koji prethodno prošao kroz ``NotificationType(...).value``.
class NotificationType(str, enum.Enum):
    APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED"
    APPOINTMENT_REJECTED = "APPOINTMENT_REJECTED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_DELEGATED = "APPOINTMENT_DELEGATED"
    APPOINTMENT_REMINDER_24H = "APPOINTMENT_REMINDER_24H"
    APPOINTMENT_REMINDER_1H = "APPOINTMENT_REMINDER_1H"
    NEW_APPOINTMENT_REQUEST = "NEW_APPOINTMENT_REQUEST"
    NEW_CHAT_MESSAGE = "NEW_CHAT_MESSAGE"
    WAITLIST_OFFER = "WAITLIST_OFFER"
    STRIKE_ADDED = "STRIKE_ADDED"
    BLOCK_ACTIVATED = "BLOCK_ACTIVATED"
    BLOCK_LIFTED = "BLOCK_LIFTED"
    DOCUMENT_REQUEST_APPROVED = "DOCUMENT_REQUEST_APPROVED"
    DOCUMENT_REQUEST_REJECTED = "DOCUMENT_REQUEST_REJECTED"
    DOCUMENT_REQUEST_COMPLETED = "DOCUMENT_REQUEST_COMPLETED"
    BROADCAST = "BROADCAST"


# ── Audit log actions (Faza 4.4 + 4.5) ────────────────────────────────────────
# Tabela ``audit_log`` postoji u ``alembic/versions/20260423_0001_initial_schema.py``
# (kolona ``action`` je ``Text``, ne PG ENUM) — zato Python enum služi kao
# striktna validacija na servisnom sloju. Dodavanje novih vrednosti ne traži
# migraciju (isti pattern kao ``NotificationType`` iz Faze 4.2).
#
# Faza 4.4 (KORAK 6): IMPERSONATION_START / IMPERSONATION_END.
# Faza 4.5 (KORAK 7): STRIKE_UNBLOCKED (admin override blokade) i
# BROADCAST_SENT (admin globalni broadcast — title/body/recipient_count
# je u tabeli ``broadcasts`` iz migracije 0003, audit log nosi samo
# činjenicu da se desilo + admin ip/identitet).
class AuditAction(str, enum.Enum):
    IMPERSONATION_START = "IMPERSONATION_START"
    IMPERSONATION_END = "IMPERSONATION_END"
    STRIKE_UNBLOCKED = "STRIKE_UNBLOCKED"
    BROADCAST_SENT = "BROADCAST_SENT"
