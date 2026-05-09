from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Faculty, UserRole


# ── Request schemas ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ── Response schemas ───────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    faculty: Faculty
    is_active: bool
    is_verified: bool
    profile_image_url: str | None
    created_at: datetime

    # Strike sistem (PRD §5.3) — relevantno samo za STUDENT uloge.
    # Za ostale uloge ovi fildovi su uvek 0 / None.
    # Frontend StrikeStatusCard čita direktno odavde umesto da održava
    # poseban query — strike data ide kroz isti `/auth/me` ciklus kao i
    # ostali profilski podaci, pa svaki refresh access tokena (svakih
    # 15 min default-no) automatski osveži broj poena i status blokade.
    total_strike_points: int = 0
    blocked_until: datetime | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
