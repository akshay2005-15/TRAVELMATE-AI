"""
Lightweight, safe, idempotent database migrations for TRAVELMATE AI.
Ensures existing SQLite / PostgreSQL database schemas stay aligned with SQLAlchemy models
without resetting, recreating, or losing existing production data.
"""

import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("travelmate.migrations")


def apply_schema_migrations(db_engine: Engine) -> None:
    """
    Applies incremental schema updates idempotently.
    Safe to run repeatedly on application startup across SQLite and PostgreSQL.
    Preserves all existing rows, tables, relationships, and constraints.
    """
    try:
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()

        # Migration: messages.booking_id
        # Introduced in Phase 4 to associate chat dialogue turns with flight bookings.
        if "messages" in tables:
            columns = {col["name"] for col in inspector.get_columns("messages")}
            if "booking_id" not in columns:
                logger.info("Database migration: adding missing column 'booking_id' to 'messages' table...")
                with db_engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE messages ADD COLUMN booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL")
                    )
                logger.info("Database migration: successfully added 'booking_id' column to 'messages' table.")
            else:
                logger.debug("Database migration: 'messages.booking_id' already exists. Skipping column addition.")

            # Ensure index ix_messages_booking_id exists for fast lookup
            indexes = {idx["name"] for idx in inspector.get_indexes("messages")}
            if "ix_messages_booking_id" not in indexes:
                logger.info("Database migration: creating index 'ix_messages_booking_id' on 'messages(booking_id)'...")
                with db_engine.begin() as conn:
                    conn.execute(
                        text("CREATE INDEX IF NOT EXISTS ix_messages_booking_id ON messages (booking_id)")
                    )
                logger.info("Database migration: index 'ix_messages_booking_id' created successfully.")
            else:
                logger.debug("Database migration: index 'ix_messages_booking_id' already exists. Skipping index creation.")

    except Exception as exc:
        logger.error(f"Error during database schema migration: {exc}", exc_info=True)
        raise

