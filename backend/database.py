"""Database engine + session helpers.

Storage is chosen by the DATABASE_URL environment variable (12-factor config):

  * Unset (local dev)  -> a zero-config SQLite file next to this module.
  * Set (production)   -> whatever you point it at, e.g. Cloud SQL Postgres:
        postgresql+psycopg2://USER:PASSWORD@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE

The rest of the app is DB-agnostic because it only talks to SQLModel/SQLAlchemy.
"""

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # e.g. Cloud SQL Postgres. pool_pre_ping avoids stale-connection errors on
    # serverless platforms that pause/resume instances.
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
else:
    # Local development default: single SQLite file.
    DB_PATH = Path(__file__).parent / "wee1.db"
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},  # SQLite-only setting
    )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
