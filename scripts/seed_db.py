#!/usr/bin/env python3
"""
seed_db.py — Populates the database with initial users from PRD §1.2.

Seed data:
    Admins (studentska služba):  sluzba@fon.bg.ac.rs, sluzba@etf.bg.ac.rs
    Profesori (FON):             profesor1@fon.bg.ac.rs, profesor2@fon.bg.ac.rs
    Profesor (ETF):              profesor1@etf.bg.ac.rs
    Asistent (FON):              asistent1@fon.bg.ac.rs
    Predmeti za delegiranje:     demo FON predmeti vezani za profesor1 i asistent1

Usage (run from backend/ directory with .env present):
    python ../scripts/seed_db.py
    python ../scripts/seed_db.py --password MySecretPass123

Default seed password: Seed@2024!  (change immediately after first login)
"""

import argparse
import asyncio
import sys
from pathlib import Path

# ── Make sure backend/ is on sys.path ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import Faculty, UserRole
from app.models.professor import Professor
from app.models.subject import Subject, subject_assistants
from app.models.user import User

# ── Seed definitions ───────────────────────────────────────────────────────────

SEED_USERS: list[dict] = [
    # ── Admins (studentska služba) ─────────────────────────────────────────────
    {
        "email": "sluzba@fon.bg.ac.rs",
        "first_name": "Studentska",
        "last_name": "Služba FON",
        "role": UserRole.ADMIN,
        "faculty": Faculty.FON,
    },
    {
        "email": "sluzba@etf.bg.ac.rs",
        "first_name": "Studentska",
        "last_name": "Služba ETF",
        "role": UserRole.ADMIN,
        "faculty": Faculty.ETF,
    },
    # ── Profesori ──────────────────────────────────────────────────────────────
    {
        "email": "profesor1@fon.bg.ac.rs",
        "first_name": "Milovan",
        "last_name": "Petrović",
        "role": UserRole.PROFESOR,
        "faculty": Faculty.FON,
        "professor_profile": {
            "title": "prof. dr",
            "department": "Katedra za informacione sisteme",
            "office": "216",
            "office_description": "Zgrada FON-a, drugi sprat, kancelarija 216",
        },
    },
    {
        "email": "profesor2@fon.bg.ac.rs",
        "first_name": "Dragana",
        "last_name": "Nikolić",
        "role": UserRole.PROFESOR,
        "faculty": Faculty.FON,
        "professor_profile": {
            "title": "dr",
            "department": "Katedra za menadžment",
            "office": "305",
            "office_description": "Zgrada FON-a, treći sprat, kancelarija 305",
        },
    },
    {
        "email": "profesor1@etf.bg.ac.rs",
        "first_name": "Aleksandar",
        "last_name": "Jovanović",
        "role": UserRole.PROFESOR,
        "faculty": Faculty.ETF,
        "professor_profile": {
            "title": "prof. dr",
            "department": "Katedra za računarsku tehniku i informatiku",
            "office": "54",
            "office_description": "Zgrada ETF-a, prizemlje, kancelarija 54",
        },
    },
    # ── Asistenti ──────────────────────────────────────────────────────────────
    {
        "email": "asistent1@fon.bg.ac.rs",
        "first_name": "Jelena",
        "last_name": "Marković",
        "role": UserRole.ASISTENT,
        "faculty": Faculty.FON,
    },
]

SEED_SUBJECTS: list[dict] = [
    {
        "code": "FON-BP-2026",
        "name": "Baze podataka",
        "faculty": Faculty.FON,
        "professor_email": "profesor1@fon.bg.ac.rs",
        "assistant_emails": ["asistent1@fon.bg.ac.rs"],
    },
    {
        "code": "FON-OS-2026",
        "name": "Operativni sistemi",
        "faculty": Faculty.FON,
        "professor_email": "profesor1@fon.bg.ac.rs",
        "assistant_emails": ["asistent1@fon.bg.ac.rs"],
    },
]


# ── Core seeding logic ─────────────────────────────────────────────────────────

async def seed(password: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        created = 0
        skipped = 0
        users_by_email: dict[str, User] = {}

        for entry in SEED_USERS:
            email = entry["email"].lower()

            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                print(f"  SKIP  {email} (already exists)")
                skipped += 1
                users_by_email[email] = existing
                continue

            user = User(
                email=email,
                hashed_password=hash_password(password),
                first_name=entry["first_name"],
                last_name=entry["last_name"],
                role=entry["role"],
                faculty=entry["faculty"],
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.flush()
            users_by_email[email] = user

            if prof_data := entry.get("professor_profile"):
                db.add(
                    Professor(
                        user_id=user.id,
                        title=prof_data["title"],
                        department=prof_data["department"],
                        office=prof_data.get("office"),
                        office_description=prof_data.get("office_description"),
                    )
                )

            print(f"  CREATE {email}  [{entry['role'].value} / {entry['faculty'].value}]")
            created += 1

        await db.commit()

        subject_created = 0
        subject_skipped = 0

        for subject_data in SEED_SUBJECTS:
            code = subject_data["code"]

            existing_subject = (
                await db.execute(select(Subject).where(Subject.code == code))
            ).scalar_one_or_none()
            if existing_subject:
                print(f"  SKIP  subject {code} (already exists)")
                subject_skipped += 1
                subject = existing_subject
            else:
                professor_email = subject_data["professor_email"].lower()
                professor_user = users_by_email.get(professor_email)
                if professor_user is None:
                    raise RuntimeError(f"Professor seed user not found: {professor_email}")

                professor = (
                    await db.execute(select(Professor).where(Professor.user_id == professor_user.id))
                ).scalar_one_or_none()
                if professor is None:
                    raise RuntimeError(f"Professor profile not found for: {professor_email}")

                subject = Subject(
                    name=subject_data["name"],
                    code=code,
                    faculty=subject_data["faculty"],
                    professor_id=professor.id,
                )
                db.add(subject)
                await db.flush()
                print(f"  CREATE subject {code}  [{subject_data['name']}]")
                subject_created += 1

            for assistant_email in subject_data["assistant_emails"]:
                assistant_user = users_by_email.get(assistant_email.lower())
                if assistant_user is None:
                    raise RuntimeError(f"Assistant seed user not found: {assistant_email}")

                existing_link = await db.execute(
                    select(subject_assistants.c.subject_id).where(
                        subject_assistants.c.subject_id == subject.id,
                        subject_assistants.c.assistant_id == assistant_user.id,
                    )
                )
                if existing_link.scalar_one_or_none() is not None:
                    continue

                await db.execute(
                    insert(subject_assistants).values(
                        subject_id=subject.id,
                        assistant_id=assistant_user.id,
                    )
                )

        await db.commit()

    await engine.dispose()
    print(
        f"\nDone. Users created: {created}  |  Users skipped: {skipped}"
        f"  |  Subjects created: {subject_created}  |  Subjects skipped: {subject_skipped}"
    )
    if created:
        print(f"\n⚠  Seed password used: {password!r}")
        print("   Change all passwords immediately after first login!\n")


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the database with initial users.")
    parser.add_argument(
        "--password",
        default="Seed@2024!",
        help="Password to assign to all seeded accounts (default: Seed@2024!)",
    )
    args = parser.parse_args()

    print("Seeding database...\n")
    asyncio.run(seed(args.password))


if __name__ == "__main__":
    main()
