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
