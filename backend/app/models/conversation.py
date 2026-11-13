"""
SQLAlchemy models for Conversations and Messages.
Complies with SRS Section 6 Data Requirements and FR-006 to FR-015.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Conversation(Base):
    """
    Persists conversational sessions between a user (or guest) and the AI assistant.
    Maintains context across multiple flight-search inquiries.
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), default="Flight Search Assistant", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title='{self.title}')>"


class Message(Base):
    """
    Stores individual dialogue turns within a conversation session.
    Tracks user inputs, assistant responses, extracted flight criteria slots,
    and associated provider flight search records.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    slots_json = Column(Text, nullable=True)   # JSON string storing extracted travel slots
    flight_search_id = Column(Integer, ForeignKey("flight_searches.id", ondelete="SET NULL"), nullable=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    flight_search = relationship("FlightSearch")
    booking = relationship("Booking")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role='{self.role}', conv_id={self.conversation_id})>"

