"""
Database connection and session management.
"""
from __future__ import annotations

import os
from typing import Any, Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured.")

engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by registering models and creating tables.
    """
    from app.models import Base
    from app.seeds import seed_agents

    Base.metadata.create_all(bind=engine)

    # Ensure runtime-only schema additions exist on existing Supabase deployments.
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE IF EXISTS agent_settings ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'Operations'")
        )

    # Seed baseline system agents.
    db = SessionLocal()
    try:
        seed_agents(db)
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Return True when the database connection is healthy.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def database_health() -> dict[str, Any]:
    """
    Return structured database health details.
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    "SELECT current_database() AS database_name, "
                    "current_user AS database_user, "
                    "version() AS server_version"
                )
            ).mappings().one()

        return {
            "ok": True,
            "database": str(result["database_name"]),
            "user": str(result["database_user"]),
            "server_version": str(result["server_version"]),
        }
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "error": str(exc),
        }
