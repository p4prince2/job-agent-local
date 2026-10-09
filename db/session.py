"""Database session and connection management for Prince AI Team."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from config import DATABASE_URL
from db.models import Base

# Setup SQLite engine with proper concurrency and foreign keys
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

# Enable SQLite foreign key enforcement
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Creates all database tables defined in models.py."""
    Base.metadata.create_all(bind=engine)

    # Lightweight SQLite migration for added columns
    if DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            try:
                res = conn.exec_driver_sql("PRAGMA table_info(tasks)").fetchall()
                col_names = [row[1] for row in res]
                if col_names and "executive_summary" not in col_names:
                    conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN executive_summary TEXT")
                    conn.commit()
            except Exception:
                pass


def get_db():
    """FastAPI dependency for yielding database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
