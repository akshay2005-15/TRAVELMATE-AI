"""
SQLAlchemy ORM model for Idempotency Records.
Ensures persistent, crash-resilient duplicate-submission protection for flight bookings.
Complies with Phase 4 Step 5 security remediation requirements.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class IdempotencyRecord(Base):
    """
    Persists client idempotency keys scoped per user to prevent duplicate bookings.
    Lifecycle statuses:
      - 'processing': In-flight request being executed.
      - 'completed': Order successfully placed; cached response is safe to replay.
      - 'uncertain': Provider timed out; status unknown, automatic retry prohibited.
      - 'failed': Booking attempt failed (e.g. invalid offer or payment); safe for fresh attempt.
    """
    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False, index=True)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, default="processing")  # 'processing', 'completed', 'uncertain', 'failed'
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    response_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_user_idempotency_key"),
    )

    # Relationships
    user = relationship("User", backref="idempotency_records")
    booking = relationship("Booking", backref="idempotency_records")

    def __repr__(self) -> str:
        return (
            f"<IdempotencyRecord(id={self.id}, user_id={self.user_id}, "
            f"key='{self.idempotency_key}', status='{self.status}', booking_id={self.booking_id})>"
        )


class BookingIntentReservation(Base):
    """
    Persists durable flight-booking intent reservations to prevent concurrent or duplicate bookings
    for the same user, flight offer, and passenger set, even when requests use different client idempotency keys.
    Works reliably across both SQLite and PostgreSQL.
    Lifecycle statuses:
      - 'processing': An active order creation attempt is in progress.
      - 'completed': Order successfully ticketed; duplicate attempts are blocked with 409 Conflict.
      - 'uncertain': Ambiguous provider outcome (timeout, reset, 5xx); automatic retries blocked with 504.
      - 'failed': Booking attempt definitively failed; safe to allow fresh attempt.
    """
    __tablename__ = "booking_intent_reservations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    flight_offer_id = Column(Integer, ForeignKey("flight_offers.id", ondelete="RESTRICT"), nullable=False, index=True)
    passenger_hash = Column(String(64), nullable=False, index=True)
    intent_key = Column(String(128), nullable=False, unique=True, index=True)  # {user_id}_{flight_offer_id}_{passenger_hash}
    idempotency_key = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="processing")  # 'processing', 'completed', 'uncertain', 'failed'
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    user = relationship("User", backref="intent_reservations")
    flight_offer = relationship("FlightOffer", backref="intent_reservations")
    booking = relationship("Booking", backref="intent_reservations")

    def __repr__(self) -> str:
        return (
            f"<BookingIntentReservation(id={self.id}, intent_key='{self.intent_key}', "
            f"status='{self.status}', booking_id={self.booking_id})>"
        )


