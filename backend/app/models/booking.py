"""
SQLAlchemy ORM model for Flight Bookings.
Complies with SRS Section 6 Data Requirements and Phase 4 Step 2 specifications.
"""

from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Booking(Base):
    """
    Persists flight bookings and simulation orders.
    Enforces data integrity, safety rules, and explicit user consent audit trail.
    Strictly avoids storing payment cards or sensitive financial credentials.
    """
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # User association (nullable for guest bookings; SET NULL on user deletion to preserve audit records)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Selected flight offer association (RESTRICT prevents deleting offers linked to active bookings)
    flight_offer_id = Column(Integer, ForeignKey("flight_offers.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Provider order references
    provider_booking_id = Column(String(255), nullable=True, unique=True, index=True)  # Duffel order id (ord_0000...) or mock order id
    booking_reference = Column(String(100), nullable=True, index=True)  # PNR code (only when supplied by provider)

    # Provider identity and transparency (Condition 2)
    provider_used = Column(String(50), nullable=False)  # 'duffel' or 'mock'
    data_source = Column(String(50), nullable=False)    # 'duffel_sandbox', 'duffel_production', 'mock_simulation'
    is_simulation = Column(Boolean, default=False, nullable=False)

    # Booking lifecycle status: 'pending_confirmation', 'confirmed', 'cancelled', 'failed'
    status = Column(String(30), default="pending_confirmation", nullable=False, index=True)

    # Pricing details
    total_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)

    # Contact information
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=False)

    # Passenger details stored as structured JSON array
    passenger_details_json = Column(Text, nullable=False)

    # Complete raw provider response stored for verification & auditing
    raw_provider_order_json = Column(Text, nullable=True)

    # Explicit user confirmation and consent audit fields
    user_confirmed = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    user = relationship("User", backref="bookings")
    flight_offer = relationship("FlightOffer", backref="bookings")

    @property
    def passenger_details(self) -> List[Dict[str, Any]]:
        """Parses passenger details from JSON."""
        if not self.passenger_details_json:
            return []
        try:
            return json.loads(self.passenger_details_json)
        except Exception:
            return []

    @property
    def raw_provider_order(self) -> Dict[str, Any]:
        """Parses raw provider response from JSON."""
        if not self.raw_provider_order_json:
            return {}
        try:
            return json.loads(self.raw_provider_order_json)
        except Exception:
            return []

    def __repr__(self) -> str:
        return (
            f"<Booking(id={self.id}, ref='{self.booking_reference}', "
            f"status='{self.status}', amount={self.currency} {self.total_amount})>"
        )


class PendingBookingConfirmation(Base):
    """
    Server-side pending booking confirmation record for conversational workflows.
    Binds explicit user confirmation to:
    - user_id (authenticated user)
    - conversation_id (active conversation context)
    - flight_offer_id (selected flight offer)
    - provider_offer_id
    - passenger_hash (SHA-256 hash of normalized passenger list)
    - passenger_details_json (stored passenger details)
    - contact_email
    - contact_phone
    - expected_amount (authoritative fare from provider revalidation)
    - currency
    - status ('pending', 'confirmed', 'consumed', 'invalidated', 'expired')
    - price_change_accepted (boolean)
    - expires_at (expiration timestamp, e.g. 15 minutes)
    - created_at, updated_at
    """
    __tablename__ = "pending_booking_confirmations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    flight_offer_id = Column(Integer, ForeignKey("flight_offers.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_offer_id = Column(String(255), nullable=False)

    passenger_hash = Column(String(64), nullable=False)
    passenger_details_json = Column(Text, nullable=False)

    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=False)

    expected_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)

    status = Column(String(30), default="pending", nullable=False, index=True)  # pending | confirmed | consumed | invalidated | expired
    price_change_accepted = Column(Boolean, default=False, nullable=False)

    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    user = relationship("User", backref="pending_confirmations")
    conversation = relationship("Conversation", backref="pending_confirmations")
    flight_offer = relationship("FlightOffer", backref="pending_confirmations")

    @property
    def passenger_details(self) -> List[Dict[str, Any]]:
        """Parses passenger details from JSON."""
        if not self.passenger_details_json:
            return []
        try:
            return json.loads(self.passenger_details_json)
        except Exception:
            return []

    def __repr__(self) -> str:
        return (
            f"<PendingBookingConfirmation(id={self.id}, conv_id={self.conversation_id}, "
            f"user_id={self.user_id}, offer_id={self.flight_offer_id}, status='{self.status}')>"
        )


