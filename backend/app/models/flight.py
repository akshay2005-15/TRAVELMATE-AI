"""
SQLAlchemy models for Flight Searches and Flight Offers.
Complies with SRS Section 6 Data Requirements and FR-022 to FR-027.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class FlightSearch(Base):
    """
    Persists flight search criteria submitted by a user or conversational assistant.
    """
    __tablename__ = "flight_searches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    origin_iata = Column(String(3), nullable=False, index=True)
    destination_iata = Column(String(3), nullable=False, index=True)
    departure_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    return_date = Column(String(10), nullable=True)     # YYYY-MM-DD
    passenger_count = Column(Integer, default=1, nullable=False)
    cabin_class = Column(String(30), default="economy", nullable=False)
    provider_used = Column(String(50), nullable=False)   # 'duffel' or 'mock'
    data_source = Column(String(50), nullable=False)     # 'duffel_sandbox', 'duffel_production', 'mock_simulation'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    offers = relationship(
        "FlightOffer",
        back_populates="search",
        cascade="all, delete-orphan",
        order_by="FlightOffer.total_amount"
    )

    def __repr__(self) -> str:
        return f"<FlightSearch(id={self.id}, {self.origin_iata}->{self.destination_iata}, date={self.departure_date})>"


class FlightOffer(Base):
    """
    Stores normalized flight offers returned by an authorized provider or mock engine.
    Condition 2 & SRS FR-023: Clearly tags data_source to distinguish simulation vs real sandbox.
    """
    __tablename__ = "flight_offers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    search_id = Column(Integer, ForeignKey("flight_searches.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_offer_id = Column(String(255), nullable=False, index=True)
    
    # Airline details
    airline_name = Column(String(100), nullable=False)
    airline_code = Column(String(10), nullable=False)
    flight_number = Column(String(30), nullable=False)

    # Route details
    origin_iata = Column(String(3), nullable=False)
    destination_iata = Column(String(3), nullable=False)
    departure_time = Column(String(30), nullable=False)  # ISO 8601 string
    arrival_time = Column(String(30), nullable=False)    # ISO 8601 string
    duration_minutes = Column(Integer, nullable=False)
    stops = Column(Integer, default=0, nullable=False)
    stop_details = Column(String(255), nullable=True)     # e.g. "1 stop via BOM (1h 20m)"

    # Pricing & terms
    total_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    cabin_class = Column(String(30), default="economy", nullable=False)
    baggage_included = Column(String(100), nullable=True)  # e.g. "15 kg Check-in, 7 kg Cabin"

    # Data integrity & source tracking
    data_source = Column(String(50), nullable=False)     # 'duffel_sandbox', 'duffel_production', 'mock_simulation'
    raw_offer_json = Column(Text, nullable=True)         # Complete provider payload for revalidation & booking
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    search = relationship("FlightSearch", back_populates="offers")

    def __repr__(self) -> str:
        return f"<FlightOffer(id={self.id}, {self.airline_code} {self.flight_number}, amount={self.currency} {self.total_amount})>"
