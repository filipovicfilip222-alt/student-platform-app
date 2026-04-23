"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-04-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum type helpers ──────────────────────────────────────────────────────────

def _create_enums() -> None:
    op.execute("CREATE TYPE userrole AS ENUM ('STUDENT', 'ASISTENT', 'PROFESOR', 'ADMIN')")
    op.execute("CREATE TYPE faculty AS ENUM ('FON', 'ETF')")
    op.execute("CREATE TYPE consultationtype AS ENUM ('UZIVO', 'ONLINE')")
    op.execute("CREATE TYPE appointmentstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'COMPLETED')")
    op.execute("CREATE TYPE topiccategory AS ENUM ('SEMINARSKI', 'PREDAVANJA', 'ISPIT', 'PROJEKAT', 'OSTALO')")
    op.execute("CREATE TYPE participantstatus AS ENUM ('PENDING', 'CONFIRMED', 'DECLINED')")
    op.execute("CREATE TYPE strikereason AS ENUM ('LATE_CANCEL', 'NO_SHOW')")
    op.execute("CREATE TYPE documenttype AS ENUM ('POTVRDA_STATUSA', 'UVERENJE_ISPITI', 'UVERENJE_PROSEK', 'PREPIS_OCENA', 'POTVRDA_SKOLARINE', 'OSTALO')")
    op.execute("CREATE TYPE documentstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED')")


def _drop_enums() -> None:
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS faculty")
    op.execute("DROP TYPE IF EXISTS consultationtype")
    op.execute("DROP TYPE IF EXISTS appointmentstatus")
    op.execute("DROP TYPE IF EXISTS topiccategory")
    op.execute("DROP TYPE IF EXISTS participantstatus")
    op.execute("DROP TYPE IF EXISTS strikereason")
    op.execute("DROP TYPE IF EXISTS documenttype")
    op.execute("DROP TYPE IF EXISTS documentstatus")


def upgrade() -> None:
    _create_enums()

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", postgresql.ENUM("STUDENT", "ASISTENT", "PROFESOR", "ADMIN", name="userrole", create_type=False), nullable=False),
        sa.Column("faculty", postgresql.ENUM("FON", "ETF", name="faculty", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("profile_image_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── professors ─────────────────────────────────────────────────────────────
    op.create_table(
        "professors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("department", sa.String(200), nullable=False),
        sa.Column("office", sa.String(100), nullable=True),
        sa.Column("office_description", sa.Text(), nullable=True),
        sa.Column("areas_of_interest", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("auto_approve_recurring", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("auto_approve_special", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("buffer_minutes", sa.Integer(), server_default="5", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_professors_user_id", "professors", ["user_id"])

    # ── subjects ───────────────────────────────────────────────────────────────
    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("faculty", postgresql.ENUM("FON", "ETF", name="faculty", create_type=False), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["professor_id"], ["professors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_subjects_professor_id", "subjects", ["professor_id"])

    # ── subject_assistants ─────────────────────────────────────────────────────
    op.create_table(
        "subject_assistants",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("subject_id", "assistant_id"),
    )

    # ── availability_slots ─────────────────────────────────────────────────────
    op.create_table(
        "availability_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("consultation_type", postgresql.ENUM("UZIVO", "ONLINE", name="consultationtype", create_type=False), nullable=False),
        sa.Column("max_students", sa.Integer(), server_default="1", nullable=False),
        sa.Column("online_link", sa.Text(), nullable=True),
        sa.Column("is_available", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("recurring_rule", postgresql.JSONB(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["professor_id"], ["professors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_availability_slots_professor_id", "availability_slots", ["professor_id"])

    # ── blackout_dates ─────────────────────────────────────────────────────────
    op.create_table(
        "blackout_dates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["professor_id"], ["professors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_blackout_dates_professor_id", "blackout_dates", ["professor_id"])

    # ── appointments ───────────────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("topic_category", postgresql.ENUM("SEMINARSKI", "PREDAVANJA", "ISPIT", "PROJEKAT", "OSTALO", name="topiccategory", create_type=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", postgresql.ENUM("PENDING", "APPROVED", "REJECTED", "CANCELLED", "COMPLETED", name="appointmentstatus", create_type=False), server_default="PENDING", nullable=False),
        sa.Column("consultation_type", postgresql.ENUM("UZIVO", "ONLINE", name="consultationtype", create_type=False), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("delegated_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_group", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["slot_id"], ["availability_slots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professor_id"], ["professors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_student_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["delegated_to"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_slot_id", "appointments", ["slot_id"])
    op.create_index("ix_appointments_professor_id", "appointments", ["professor_id"])
    op.create_index("ix_appointments_lead_student_id", "appointments", ["lead_student_id"])

    # ── appointment_participants ───────────────────────────────────────────────
    op.create_table(
        "appointment_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", postgresql.ENUM("PENDING", "CONFIRMED", "DECLINED", name="participantstatus", create_type=False), server_default="PENDING", nullable=False),
        sa.Column("is_lead", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointment_participants_appointment_id", "appointment_participants", ["appointment_id"])
    op.create_index("ix_appointment_participants_student_id", "appointment_participants", ["student_id"])

    # ── waitlist ───────────────────────────────────────────────────────────────
    op.create_table(
        "waitlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["slot_id"], ["availability_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "student_id", name="uq_waitlist_slot_student"),
    )
    op.create_index("ix_waitlist_slot_id", "waitlist", ["slot_id"])
    op.create_index("ix_waitlist_student_id", "waitlist", ["student_id"])

    # ── files ──────────────────────────────────────────────────────────────────
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("minio_object_key", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_files_appointment_id", "files", ["appointment_id"])

    # ── ticket_chat_messages ───────────────────────────────────────────────────
    op.create_table(
        "ticket_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_chat_messages_appointment_id", "ticket_chat_messages", ["appointment_id"])
    op.create_index("ix_ticket_chat_messages_sender_id", "ticket_chat_messages", ["sender_id"])

    # ── crm_notes ──────────────────────────────────────────────────────────────
    op.create_table(
        "crm_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["professor_id"], ["professors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_notes_professor_id", "crm_notes", ["professor_id"])
    op.create_index("ix_crm_notes_student_id", "crm_notes", ["student_id"])

    # ── strike_records ─────────────────────────────────────────────────────────
    op.create_table(
        "strike_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reason", postgresql.ENUM("LATE_CANCEL", "NO_SHOW", name="strikereason", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strike_records_student_id", "strike_records", ["student_id"])

    # ── student_blocks ─────────────────────────────────────────────────────────
    op.create_table(
        "student_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("removal_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["removed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id"),
    )

    # ── faq_items ──────────────────────────────────────────────────────────────
    op.create_table(
        "faq_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["professor_id"], ["professors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faq_items_professor_id", "faq_items", ["professor_id"])

    # ── notifications ──────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    # ── audit_log ──────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("impersonated_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["impersonated_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_admin_id", "audit_log", ["admin_id"])
    op.create_index("ix_audit_log_impersonated_user_id", "audit_log", ["impersonated_user_id"])

    # ── canned_responses ───────────────────────────────────────────────────────
    op.create_table(
        "canned_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["professor_id"], ["professors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_canned_responses_professor_id", "canned_responses", ["professor_id"])

    # ── document_requests ──────────────────────────────────────────────────────
    op.create_table(
        "document_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", postgresql.ENUM("POTVRDA_STATUSA", "UVERENJE_ISPITI", "UVERENJE_PROSEK", "PREPIS_OCENA", "POTVRDA_SKOLARINE", "OSTALO", name="documenttype", create_type=False), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ENUM("PENDING", "APPROVED", "REJECTED", "COMPLETED", name="documentstatus", create_type=False), server_default="PENDING", nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("pickup_date", sa.Date(), nullable=True),
        sa.Column("processed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_requests_student_id", "document_requests", ["student_id"])

    # ── password_reset_tokens ──────────────────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("document_requests")
    op.drop_table("canned_responses")
    op.drop_table("audit_log")
    op.drop_table("notifications")
    op.drop_table("faq_items")
    op.drop_table("student_blocks")
    op.drop_table("strike_records")
    op.drop_table("crm_notes")
    op.drop_table("ticket_chat_messages")
    op.drop_table("files")
    op.drop_table("waitlist")
    op.drop_table("appointment_participants")
    op.drop_table("appointments")
    op.drop_table("blackout_dates")
    op.drop_table("availability_slots")
    op.drop_table("subject_assistants")
    op.drop_table("subjects")
    op.drop_table("professors")
    op.drop_table("users")
    _drop_enums()
