# Import all models here so that SQLAlchemy metadata is populated
# and Alembic autogenerate can detect all tables.
from app.models.base import Base  # noqa: F401
from app.models.enums import (  # noqa: F401
    AppointmentStatus,
    ConsultationType,
    DocumentStatus,
    DocumentType,
    Faculty,
    ParticipantStatus,
    StrikeReason,
    TopicCategory,
    UserRole,
)
from app.models.user import User  # noqa: F401
from app.models.professor import Professor  # noqa: F401
from app.models.subject import Subject, subject_assistants  # noqa: F401
from app.models.availability_slot import AvailabilitySlot, BlackoutDate  # noqa: F401
from app.models.appointment import Appointment, AppointmentParticipant, Waitlist  # noqa: F401
from app.models.file import File  # noqa: F401
from app.models.chat import TicketChatMessage  # noqa: F401
from app.models.crm_note import CrmNote  # noqa: F401
from app.models.strike import StrikeRecord, StudentBlock  # noqa: F401
from app.models.faq import FaqItem  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.canned_response import CannedResponse  # noqa: F401
from app.models.document_request import DocumentRequest  # noqa: F401
from app.models.password_reset_token import PasswordResetToken  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Professor",
    "Subject",
    "subject_assistants",
    "AvailabilitySlot",
    "BlackoutDate",
    "Appointment",
    "AppointmentParticipant",
    "Waitlist",
    "File",
    "TicketChatMessage",
    "CrmNote",
    "StrikeRecord",
    "StudentBlock",
    "FaqItem",
    "Notification",
    "AuditLog",
    "CannedResponse",
    "DocumentRequest",
    "PasswordResetToken",
]
