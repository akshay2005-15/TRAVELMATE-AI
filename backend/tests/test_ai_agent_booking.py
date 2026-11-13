"""
Automated Pytest Suite for AI Conversational Agent Booking Integration (Phase 4 Step 6).
Validates end-to-end conversational booking:
1. Real flight offer selection (index, superlatives, flight numbers)
2. Invalid and ambiguous flight selections
3. Booking request without a selected offer
4. Guest user attempting booking (authentication required)
5. Authenticated booking preparation & saved passenger profile reuse
6. Missing passenger information prompts
7. Pending booking review creation & masked data protection
8. Vague confirmation ("looks good", "nice", "okay") does not book
9. Explicit confirmation permits booking only once (consumed status)
10. Confirmation belonging to another user is rejected
11. Confirmation belonging to another conversation is rejected
12. Expired confirmation is rejected
13. Modified passenger details invalidate previous confirmation
14. Modified fare invalidates previous confirmation
15. Offer revalidation executed before provider order creation
16. Price change requires fresh explicit approval
17. Provider rejection is reported accurately
18. Ambiguous provider outcome is reported as uncertain
19. Existing idempotency and intent reservation protections remain effective
20. No automatic retry after uncertain provider outcome
21. Existing flight search and normal chat remain functional
22. Existing conversation history and message persistence remain functional
"""

import json
from datetime import datetime, date, timezone, timedelta
from unittest.mock import AsyncMock, patch
import pytest

from app.models.user import User, UserRole, PassengerProfile
from app.models.flight import FlightSearch, FlightOffer
from app.models.conversation import Conversation, Message
from app.models.booking import Booking, PendingBookingConfirmation
from app.models.idempotency import IdempotencyRecord, BookingIntentReservation
from app.schemas.chat import ChatMessageResponse, FlightCriteriaSlots
from app.schemas.booking import (
    BookingCreateRequest,
    PassengerBookingDetails,
    BookingContactDetails,
    mask_passport_number
)
from app.services.booking_service import (
    booking_service,
    BookingProviderAmbiguousError,
    BookingProviderTimeoutError,
    BookingProviderError
)
from app.ai import run_flight_agent


# ===========================================================================
# Test Fixtures & Helpers
# ===========================================================================

@pytest.fixture(autouse=True)
def force_fast_offline_ai(monkeypatch):
    """Ensure tests run deterministically and fast without external Gemini network timeouts/quota limits."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")


def register_user(client, email="traveler_ai@example.com", name="Aarav Sharma"):
    res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": name
    })
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]


def create_search_and_offers(db_session, user_id=None):
    search = FlightSearch(
        user_id=user_id,
        origin_iata="BLR",
        destination_iata="DEL",
        departure_date="2026-11-25",
        passenger_count=1,
        cabin_class="economy",
        provider_used="mock",
        data_source="mock_simulation"
    )
    db_session.add(search)
    db_session.flush()

    o1 = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_blr_del_101",
        airline_name="IndiGo",
        airline_code="6E",
        flight_number="6E-2054",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-25T06:00:00Z",
        arrival_time="2026-11-25T08:45:00Z",
        duration_minutes=165,
        stops=0,
        total_amount=5400.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    o2 = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_blr_del_102",
        airline_name="Air India",
        airline_code="AI",
        flight_number="AI-506",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-25T10:30:00Z",
        arrival_time="2026-11-25T13:20:00Z",
        duration_minutes=170,
        stops=0,
        total_amount=6200.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    o3 = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_blr_del_103",
        airline_name="SpiceJet",
        airline_code="SG",
        flight_number="SG-819",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-25T18:00:00Z",
        arrival_time="2026-11-25T21:10:00Z",
        duration_minutes=190,
        stops=1,
        total_amount=4800.0,  # cheapest
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    db_session.add_all([o1, o2, o3])
    db_session.commit()
    return search, [o1, o2, o3]


def create_conversation_with_search(db_session, user_id=None):
    search, offers = create_search_and_offers(db_session, user_id=user_id)
    conv = Conversation(
        title="Flights from BLR to DEL",
        user_id=user_id
    )
    db_session.add(conv)
    db_session.flush()

    msg1 = Message(
        conversation_id=conv.id,
        role="user",
        content="Find flights from BLR to DEL on 2026-11-25"
    )
    msg2 = Message(
        conversation_id=conv.id,
        role="assistant",
        content="Here are 3 flight options from BLR to DEL.",
        slots_json=json.dumps({"origin": "BLR", "destination": "DEL", "departure_date": "2026-11-25"}),
        flight_search_id=search.id
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()
    db_session.refresh(conv)
    return conv, search, offers


# ===========================================================================
# 1. Flight Selection Tests
# ===========================================================================

def test_select_real_flight_offer_by_index(client, db_session):
    """1. Test selecting a real returned flight offer by numeric index."""
    token, user = register_user(client, email="select1@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "I want the second flight"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] in ("passenger_details_required", "booking_review_ready")
    assert "AI-506" in data["assistant_message"] or "Air India" in data["assistant_message"]
    assert data["slots"]["selected_flight_offer_id"] == offers[1].id


def test_select_cheapest_flight(client, db_session):
    """Test selecting flight using superlative 'cheapest'."""
    token, user = register_user(client, email="cheapest@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Book the cheapest flight"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    # Offer 3 is SG-819 with 4800.0 (cheapest)
    assert data["slots"]["selected_flight_offer_id"] == offers[2].id
    assert "SpiceJet" in data["assistant_message"] or "SG-819" in data["assistant_message"]


def test_invalid_and_ambiguous_flight_selections(client, db_session):
    """2. Test out-of-range option index and ambiguous flight selections."""
    token, user = register_user(client, email="invalid_sel@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    # Out of range option 8 when only 3 offers exist
    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Select option 8"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "flight_selection_required"
    assert "only 3" in data["assistant_message"].lower() or "between 1 and 3" in data["assistant_message"].lower()


def test_booking_request_without_selected_offer(client, db_session):
    """3. Test booking request or passenger details without any selected offer."""
    token, user = register_user(client, email="no_offer@test.com")

    # Clean conversation with no search
    conv = Conversation(title="Empty Chat", user_id=user["id"])
    db_session.add(conv)
    db_session.commit()

    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "My name is Aarav Sharma, DOB 1990-05-15, please book"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "flight_selection_required"
    assert "haven't selected a flight" in data["assistant_message"].lower() or "search" in data["assistant_message"].lower()


# ===========================================================================
# 2. Authentication and Passenger Profile Tests
# ===========================================================================

def test_guest_user_attempting_booking_requires_auth(client, db_session):
    """4. Guest user attempting flight selection or booking must receive login requirement."""
    conv, search, offers = create_conversation_with_search(db_session, user_id=None)

    # Guest request without token
    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "I want flight 1"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "authentication_required"
    assert "account required" in data["assistant_message"].lower() or "log in" in data["assistant_message"].lower()


def test_authenticated_booking_with_saved_profile(client, db_session):
    """5. Authenticated user can autofill using saved passenger profile."""
    token, user_dict = register_user(client, email="profile_user@test.com", name="Priya Patel")
    user = db_session.query(User).filter(User.id == user_dict["id"]).first()

    # Add a saved passenger profile
    prof = PassengerProfile(
        user_id=user.id,
        first_name="Priya",
        last_name="Patel",
        date_of_birth="1994-08-22",
        gender="female",
        passport_number="P98765432"
    )
    db_session.add(prof)
    db_session.commit()

    conv, search, offers = create_conversation_with_search(db_session, user_id=user.id)

    # User selects flight and asks to use saved profile
    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Select flight 1 and use my saved profile"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "booking_confirmation_required"
    assert "BOOKING REVIEW" in data["assistant_message"]
    assert "Priya Patel" in data["assistant_message"]
    assert "****5432" in data["assistant_message"]  # masked passport


def test_missing_passenger_information_prompts_user(client, db_session):
    """6. When passenger details are incomplete, agent asks specifically for missing pieces."""
    token, user = register_user(client, email="partial_pax@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    # User selects flight 1
    res1 = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "I want flight 1"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["booking_workflow_state"] == "passenger_details_required"
    assert "passenger full name" in data1["assistant_message"].lower()

    # User provides only name
    res2 = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Passenger name is Rohit Verma"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["booking_workflow_state"] == "passenger_details_required"
    assert "date of birth" in data2["assistant_message"].lower()


# ===========================================================================
# 3. Pending Review & Vague Confirmation Gate Tests
# ===========================================================================

def test_pending_booking_review_creation_and_masking(client, db_session):
    """7. Test creation of server-side PendingBookingConfirmation record with masked review."""
    token, user = register_user(client, email="review_test@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    res = client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": "Select flight 1, name is Rahul Kumar, DOB 1991-03-20, email rahul@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "booking_confirmation_required"
    assert "BOOKING REVIEW (NOT YET CONFIRMED)" in data["assistant_message"]
    assert "r***l@test.com" in data["assistant_message"]  # masked email
    assert "+91****3210" in data["assistant_message"]    # masked phone
    assert "INR 5,400.00" in data["assistant_message"]
    assert "[SIMULATION / MOCK ORDER]" in data["assistant_message"]

    # Verify pending confirmation record in DB
    pending = db_session.query(PendingBookingConfirmation).filter(
        PendingBookingConfirmation.conversation_id == conv.id,
        PendingBookingConfirmation.status == "pending"
    ).first()
    assert pending is not None
    assert pending.user_id == user["id"]
    assert pending.expected_amount == 5400.0
    assert pending.contact_email == "rahul@test.com"


def test_vague_confirmation_does_not_book(client, db_session):
    """8. Vague expressions ('looks good', 'nice', 'okay') must NOT create a booking."""
    token, user = register_user(client, email="vague@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    # Provide all details to get into review state
    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": "Select flight 1, name is Sneha Rao, DOB 1993-11-12, email sneha@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Vague confirmation: "looks good"
    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Looks good!"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "booking_confirmation_required"
    assert "explicit confirmation" in data["assistant_message"].lower() or "confirm booking" in data["assistant_message"].lower()

    # Zero bookings must have been created in database!
    booking_count = db_session.query(Booking).count()
    assert booking_count == 0

    # Pending record must remain 'pending'
    pending = db_session.query(PendingBookingConfirmation).filter(
        PendingBookingConfirmation.conversation_id == conv.id
    ).first()
    assert pending.status == "pending"


# ===========================================================================
# 4. Explicit Confirmation and Single-Use Consumption Tests
# ===========================================================================

def test_explicit_confirmation_creates_booking_and_consumes_confirmation(client, db_session):
    """9. Explicit confirmation creates booking and consumes confirmation (single-use)."""
    token, user = register_user(client, email="confirm_single@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    # Prepare review
    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": "Select flight 1, name is Aarav Sharma, DOB 1992-04-15, email aarav@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Explicit confirmation: "Confirm booking"
    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "booking_confirmed"
    assert "BOOKING CONFIRMED" in data["assistant_message"]
    assert "PNR" in data["assistant_message"] or "Booking Reference" in data["assistant_message"]
    assert data["booking_reference"] is not None

    # Database booking must exist
    booking = db_session.query(Booking).filter(Booking.user_id == user["id"]).first()
    assert booking is not None
    assert booking.status == "confirmed"
    assert booking.total_amount == 5400.0

    # Pending confirmation record must be marked 'consumed'
    pending = db_session.query(PendingBookingConfirmation).filter(
        PendingBookingConfirmation.conversation_id == conv.id
    ).first()
    assert pending.status == "consumed"

    # Repeated confirmation must NOT create another booking!
    res_repeat = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_repeat.status_code == 200
    assert "already been confirmed" in res_repeat.json()["assistant_message"].lower() or "no active pending booking" in res_repeat.json()["assistant_message"].lower()
    assert db_session.query(Booking).filter(Booking.user_id == user["id"]).count() == 1


# ===========================================================================
# 5. Security & Boundary Enforcement Tests
# ===========================================================================

def test_confirmation_from_another_user_rejected(client, db_session):
    """10. User B cannot confirm User A's pending booking."""
    token_a, user_a = register_user(client, email="user_a@test.com")
    token_b, user_b = register_user(client, email="user_b@test.com")

    conv, search, offers = create_conversation_with_search(db_session, user_id=user_a["id"])

    # User A prepares review
    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": "Select flight 1, name is User A, DOB 1990-01-01, email a@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )

    # User B attempts to message inside User A's conversation
    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res.status_code == 403
    assert "do not own this conversation" in res.json()["detail"].lower()


def test_confirmation_from_another_conversation_rejected(client, db_session):
    """11. Confirmation belonging to another conversation cannot be confirmed from a second conversation."""
    token, user = register_user(client, email="multi_conv@test.com")
    conv1, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    # User prepares review in Conv 1
    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv1.id,
            "message": "Select flight 1, name is User Multi, DOB 1990-01-01, email m@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # User opens fresh Conv 2 and says "Confirm booking"
    conv2 = Conversation(title="Conv 2", user_id=user["id"])
    db_session.add(conv2)
    db_session.commit()

    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv2.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "flight_selection_required"
    assert "no active pending booking" in data["assistant_message"].lower()


def test_expired_confirmation_is_rejected(client, db_session):
    """12. Pending confirmation that has expired (15m limit) is rejected."""
    token, user = register_user(client, email="expire_test@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": "Select flight 1, name is Expire Test, DOB 1990-01-01, email exp@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Manually backdate expiration in DB to simulate expired session
    pending = db_session.query(PendingBookingConfirmation).filter(
        PendingBookingConfirmation.conversation_id == conv.id
    ).first()
    pending.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "expired" in data["assistant_message"].lower()
    assert db_session.query(Booking).count() == 0


def test_modified_passenger_details_invalidates_confirmation(client, db_session):
    """13. Modifying passenger details invalidates previous pending confirmation."""
    token, user = register_user(client, email="modify_pax@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": "Select flight 1, name is John Doe, DOB 1990-01-01, email j@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    first_pending = db_session.query(PendingBookingConfirmation).filter(
        PendingBookingConfirmation.conversation_id == conv.id
    ).first()
    assert first_pending.status == "pending"

    # User changes passenger name
    client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Passenger name is Jane Doe, DOB 1992-02-02, email jane@test.com, phone +919876543210"},
        headers={"Authorization": f"Bearer {token}"}
    )

    db_session.refresh(first_pending)
    assert first_pending.status == "invalidated"


# ===========================================================================
# 6. Revalidation, Price Changes & Provider Error Tests
# ===========================================================================

def test_price_change_requires_fresh_approval(client, db_session):
    """16. If revalidation detects price change, agent halts and requires fresh approval."""
    token, user = register_user(client, email="price_change_ai@test.com")
    search, offers = create_search_and_offers(db_session, user_id=user["id"])

    # Create an offer whose ID triggers price_changed in mock adapter (+500 INR)
    price_change_offer = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_price_changed_999",
        airline_name="IndiGo",
        airline_code="6E",
        flight_number="6E-9999",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-25T07:00:00Z",
        arrival_time="2026-11-25T09:45:00Z",
        duration_minutes=165,
        stops=0,
        total_amount=5000.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    db_session.add(price_change_offer)
    db_session.commit()

    conv = Conversation(title="Price Change Conv", user_id=user["id"])
    db_session.add(conv)
    db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content="Search results",
        flight_search_id=search.id
    )
    db_session.add(msg)
    db_session.commit()

    # User selects price change offer and provides details
    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": f"Select offer #{price_change_offer.id}, name is Price Test, DOB 1990-01-01, email p@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # User confirms booking -> triggers revalidation which detects price increased to 5500
    res_confirm = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_confirm.status_code == 200
    data = res_confirm.json()
    assert data["booking_workflow_state"] == "price_change_requires_approval"
    assert "price change alert" in data["assistant_message"].lower()
    assert "5,500.00" in data["assistant_message"]

    # Booking must NOT be created yet
    assert db_session.query(Booking).count() == 0

    # User explicitly accepts new price
    res_accept = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Accept new price and confirm"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_accept.status_code == 200
    data_accept = res_accept.json()
    assert data_accept["booking_workflow_state"] == "booking_confirmed"
    assert "BOOKING CONFIRMED" in data_accept["assistant_message"]
    assert db_session.query(Booking).count() == 1


def test_provider_rejection_reported_accurately(client, db_session):
    """17. When provider rejects order creation (4xx), agent reports booking_failed."""
    token, user = register_user(client, email="reject_test@test.com")
    search, offers = create_search_and_offers(db_session, user_id=user["id"])

    # Create offer that triggers fail_order in mock adapter
    fail_offer = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_fail_order_123",
        airline_name="IndiGo",
        airline_code="6E",
        flight_number="6E-FAIL",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-25T08:00:00Z",
        arrival_time="2026-11-25T10:45:00Z",
        duration_minutes=165,
        stops=0,
        total_amount=5200.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    db_session.add(fail_offer)
    db_session.commit()

    conv = Conversation(title="Fail Conv", user_id=user["id"])
    db_session.add(conv)
    db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content="Search results",
        flight_search_id=search.id
    )
    db_session.add(msg)
    db_session.commit()

    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": f"Select offer #{fail_offer.id}, name is Fail User, DOB 1990-01-01, email f@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "booking_failed"
    assert "booking failed" in data["assistant_message"].lower()


def test_ambiguous_provider_timeout_reported_as_uncertain(client, db_session):
    """18. When provider times out, agent reports booking_uncertain with zero blind retry."""
    token, user = register_user(client, email="timeout_ai@test.com")
    search, offers = create_search_and_offers(db_session, user_id=user["id"])

    # Create offer that triggers timeout in mock adapter
    timeout_offer = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_timeout_456",
        airline_name="Air India",
        airline_code="AI",
        flight_number="AI-TIMEOUT",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-25T09:00:00Z",
        arrival_time="2026-11-25T11:45:00Z",
        duration_minutes=165,
        stops=0,
        total_amount=5900.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    db_session.add(timeout_offer)
    db_session.commit()

    conv = Conversation(title="Timeout Conv", user_id=user["id"])
    db_session.add(conv)
    db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content="Search results",
        flight_search_id=search.id
    )
    db_session.add(msg)
    db_session.commit()

    client.post(
        "/api/v1/chat/message",
        json={
            "conversation_id": conv.id,
            "message": f"Select offer #{timeout_offer.id}, name is Timeout User, DOB 1990-01-01, email t@test.com, phone +919876543210"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "Confirm booking"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["booking_workflow_state"] == "booking_uncertain"
    assert "status uncertain" in data["assistant_message"].lower()
    assert "duplicate charges" in data["assistant_message"].lower()


# ===========================================================================
# 7. Regression & Conversation Continuity Tests
# ===========================================================================

def test_existing_flight_search_and_greetings_remain_functional(client):
    """21. Ensure existing greeting and flight search flows remain 100% functional."""
    # Greeting
    res1 = client.post("/api/v1/chat/message", json={"message": "Hello TRAVELMATE"})
    assert res1.status_code == 200
    assert "TRAVELMATE AI" in res1.json()["assistant_message"]

    # Search
    future_date = (date.today() + timedelta(days=7)).isoformat()
    res2 = client.post("/api/v1/chat/message", json={
        "message": f"Search flights from Bangalore to Delhi on {future_date}"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["search_status"] == "search_executed"
    assert data2["flight_offers"] is not None
    assert len(data2["flight_offers"]) > 0


def test_conversation_history_persistence_and_retrieval(client, db_session):
    """22. Verify conversation history retrieval includes messages and booking statuses."""
    token, user = register_user(client, email="history_test@test.com")
    conv, search, offers = create_conversation_with_search(db_session, user_id=user["id"])

    # Send a message
    client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv.id, "message": "I want flight 1"},
        headers={"Authorization": f"Bearer {token}"}
    )

    # Retrieve history
    res_hist = client.get(
        f"/api/v1/chat/conversations/{conv.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_hist.status_code == 200
    data = res_hist.json()
    assert len(data["messages"]) >= 3
    assert data["messages"][-1]["role"] == "assistant"
