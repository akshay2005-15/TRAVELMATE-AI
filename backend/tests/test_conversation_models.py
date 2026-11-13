"""
Unit tests for Conversation and Message database models.
Validates compliance with SRS Section 6 Data Requirements and FR-006 to FR-009.
"""

from app.models.conversation import Conversation, Message
from app.models.user import User, UserRole


def test_conversation_and_message_lifecycle(db_session):
    # 1. Create a user
    user = User(
        email="chat_user@travelmate.ai",
        hashed_password="hashedpassword123",
        full_name="Chat Tester",
        role=UserRole.USER
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # 2. Create a conversation owned by the user
    conv = Conversation(
        user_id=user.id,
        title="Flight to Delhi"
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    assert conv.id is not None
    assert conv.user_id == user.id
    assert conv.title == "Flight to Delhi"
    assert conv.created_at is not None

    # 3. Add dialogue messages
    msg1 = Message(
        conversation_id=conv.id,
        role="user",
        content="Find flights from Bangalore to Delhi next Friday",
        slots_json='{"origin": "BLR", "destination": "DEL"}'
    )
    msg2 = Message(
        conversation_id=conv.id,
        role="assistant",
        content="I found 6 flights from Bangalore (BLR) to Delhi (DEL).",
        slots_json='{"origin": "BLR", "destination": "DEL"}'
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    # 4. Verify message retrieval and ordering
    db_session.refresh(conv)
    assert len(conv.messages) == 2
    assert conv.messages[0].role == "user"
    assert conv.messages[1].role == "assistant"
    assert "BLR" in conv.messages[0].slots_json

    # 5. Verify cascade deletion
    db_session.delete(conv)
    db_session.commit()

    remaining_messages = db_session.query(Message).filter(Message.conversation_id == conv.id).all()
    assert len(remaining_messages) == 0


def test_guest_conversation_support(db_session):
    """
    SRS FR-006 & FR-009: Guest sessions should be supported without requiring a user_id.
    """
    guest_conv = Conversation(
        user_id=None,
        title="Guest Flight Inquiry"
    )
    db_session.add(guest_conv)
    db_session.commit()
    db_session.refresh(guest_conv)

    assert guest_conv.id is not None
    assert guest_conv.user_id is None

    msg = Message(
        conversation_id=guest_conv.id,
        role="user",
        content="What flights are available from London to New York?"
    )
    db_session.add(msg)
    db_session.commit()

    db_session.refresh(guest_conv)
    assert len(guest_conv.messages) == 1
    assert guest_conv.messages[0].content == "What flights are available from London to New York?"

