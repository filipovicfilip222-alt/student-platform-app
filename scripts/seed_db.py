#!/usr/bin/env python3
"""
seed_db.py — Populates the database with initial users from PRD §1.2.

Seed data:
  Admins (studentska služba):  sluzba@fon.bg.ac.rs, sluzba@etf.bg.ac.rs
  Profesori (FON):             profesor1@fon.bg.ac.rs, profesor2@fon.bg.ac.rs
  Profesor (ETF):              profesor1@etf.bg.ac.rs
  Asistent (FON):              asistent1@fon.bg.ac.rs

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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import Faculty, UserRole
from app.models.professor import Professor
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


# ── Core seeding logic ─────────────────────────────────────────────────────────

async def seed(password: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        created = 0
        skipped = 0

        for entry in SEED_USERS:
            email = entry["email"].lower()

            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                print(f"  SKIP  {email} (already exists)")
                skipped += 1
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

    await engine.dispose()
    print(f"\nDone. Created: {created}  |  Skipped (already exist): {skipped}")
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
