"""
Emergency utility to reseed agent_settings using canonical app seed data.

Usage:
  python scripts/emergency_reseed_agents.py
"""
from __future__ import annotations

from app.database import SessionLocal
from app.seeds import seed_agents
from sqlalchemy import text


def main() -> None:
    db = SessionLocal()
    try:
        inserted = seed_agents(db)
        total = db.execute(text("SELECT COUNT(*) FROM agent_settings")).scalar()
        print(f"seed_agents inserted={inserted} total={int(total or 0)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
