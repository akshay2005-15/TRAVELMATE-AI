"""
Unit tests for Booking SQLAlchemy ORM model.
Validates constraints, foreign keys, relationships, guest bookings, and JSON properties.
"""

from datetime import datetime, timezone, timedelta
import json
import pytest

from app.models.user import User, UserRole
from app.models.flight import FlightSearch, FlightOffer
from app.models.booking import Booking


def test_booking_model_creation_and_relationships(db_session):
    # 1. Create a user
    user = User(
        email="booking_tester@travelmate.ai",
        hashed_password="hashedpassword123",
        full_name="Booking Tester",
        role=UserRole.USER
    )
    db_session.add(user)
    db_session.flush()

    # 2. Create a flight search and offer
    search = FlightSearch(
        user_id=user.id,
        origin_iata="BLR",
        destination_iata="DEL",
        departure_date="2026-11-20",
        passenger_count=1,
        cabin_class="economy",
        provider_used="mock",
        data_source="mock_simulation"
    )
    db_session.add(search)
    db_session.flush()

    offer = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_abc123",
        airline_name="IndiGo",
        airline_code="6E",
        flight_number="6E-2054",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-20T06:00:00Z",
        arrival_time="2026-11-20T08:45:00Z",
        duration_minutes=165,
        stops=0,
        total_amount=5400.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation"
    )
    db_session.add(offer)
    db_session.flush()

    # 3. Create a Booking with passenger JSON and audit details
    passengers_data = [
        {
            "first_name": "Arjun",
            "last_name": "Reddy",
            "date_of_birth": "1995-05-15",
            "gender": "male",
            "passport_number": None
        }
    ]

    booking = Booking(
        user_id=user.id,
        flight_offer_id=offer.id,
        provider_booking_id="mock_ord_999888",
        booking_reference="MOCK-6E-999888",
        provider_used="mock",
        data_source="mock_simulation",
        is_simulation=True,
        status="confirmed",
        total_amount=5400.0,
        currency="INR",
        contact_email="booking_tester@travelmate.ai",
        contact_phone="+919876543210",
        passenger_details_json=json.dumps(passengers_data),
        raw_provider_order_json=json.dumps({"provider": "mock", "order_id": "mock_ord_999888"}),
        user_confirmed=True,
        confirmed_at=datetime.now(timezone.utc)
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    # 4. Verify properties and relationships
    assert booking.id is not None
    assert booking.booking_reference == "MOCK-6E-999888"
    assert booking.status == "confirmed"
    assert booking.user_confirmed is True
    assert booking.confirmed_at is not None
    assert booking.user.id == user.id
    assert booking.flight_offer.id == offer.id
    assert user.bookings[0].id == booking.id
    assert offer.bookings[0].id == booking.id

    # 5. Verify JSON parsing helper properties
    parsed_passengers = booking.passenger_details
    assert len(parsed_passengers) == 1
    assert parsed_passengers[0]["first_name"] == "Arjun"
    assert parsed_passengers[0]["last_name"] == "Reddy"

    parsed_raw_order = booking.raw_provider_order
    assert parsed_raw_order.get("provider") == "mock"

    # 6. Verify Pydantic schema validation directly from ORM instance
    from app.schemas.booking import BookingResponse, BookingSummaryResponse
    resp = BookingResponse.model_validate(booking)
    assert resp.id == booking.id
    assert resp.booking_reference == "MOCK-6E-999888"
    assert len(resp.passengers) == 1
    assert resp.passengers[0].first_name == "Arjun"
    assert resp.flight_offer is not None
    assert resp.flight_offer.flight_number == "6E-2054"

    summary = BookingSummaryResponse.model_validate(booking)
    assert summary.id == booking.id
    assert summary.airline_name == "IndiGo"
    assert summary.flight_number == "6E-2054"
    assert summary.passenger_count == 1
    assert summary.passenger_names == ["Arjun Reddy"]
    assert "passport_number" not in summary.model_dump()
    assert "date_of_birth" not in summary.model_dump()


def test_guest_booking_creation(db_session):
    """
    Verifies that guest users can complete bookings with user_id=None.
    """
    search = FlightSearch(
        user_id=None,
        origin_iata="DEL",
        destination_iata="BOM",
        departure_date="2026-11-25",
        passenger_count=1,
        cabin_class="economy",
        provider_used="mock",
        data_source="mock_simulation"
    )
    db_session.add(search)
    db_session.flush()

    offer = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_xyz789",
        airline_name="Air India",
        airline_code="AI",
        flight_number="AI-803",
        origin_iata="DEL",
        destination_iata="BOM",
        departure_time="2026-11-25T09:30:00Z",
        arrival_time="2026-11-25T11:45:00Z",
        duration_minutes=135,
        stops=0,
        total_amount=6100.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation"
    )
    db_session.add(offer)
    db_session.flush()

    booking = Booking(
        user_id=None,  # Guest user
        flight_offer_id=offer.id,
        provider_booking_id="mock_ord_guest123",
        booking_reference="MOCK-AI-GUEST123",
        provider_used="mock",
        data_source="mock_simulation",
        is_simulation=True,
        status="confirmed",
        total_amount=6100.0,
        currency="INR",
        contact_email="guest@example.com",
        contact_phone="+919123456789",
        passenger_details_json=json.dumps([{"first_name": "Rohan", "last_name": "Verma", "date_of_birth": "1990-01-01"}]),
        user_confirmed=True,
        confirmed_at=datetime.now(timezone.utc)
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    assert booking.id is not None
    assert booking.user_id is None
    assert booking.contact_email == "guest@example.com"
    assert booking.status == "confirmed"


def test_user_deletion_sets_booking_user_id_null(db_session):
    """
    Verifies that deleting an account preserves financial booking audit records (SET NULL).
    """
    user = User(
        email="delete_me@travelmate.ai",
        hashed_password="hashedpassword123",
        full_name="Delete Tester",
        role=UserRole.USER
    )
    db_session.add(user)
    db_session.flush()

    search = FlightSearch(
        user_id=user.id,
        origin_iata="BLR",
        destination_iata="DEL",
        departure_date="2026-11-22",
        passenger_count=1,
        cabin_class="economy",
        provider_used="mock",
        data_source="mock_simulation"
    )
    db_session.add(search)
    db_session.flush()

    offer = FlightOffer(
        search_id=search.id,
        provider_offer_id="mock_off_del1",
        airline_name="IndiGo",
        airline_code="6E",
        flight_number="6E-101",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-22T06:00:00Z",
        arrival_time="2026-11-22T08:45:00Z",
        duration_minutes=165,
        stops=0,
        total_amount=5000.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation"
    )
    db_session.add(offer)
    db_session.flush()

    booking = Booking(
        user_id=user.id,
        flight_offer_id=offer.id,
        provider_booking_id="mock_ord_del1",
        booking_reference="MOCK-DEL-001",
        provider_used="mock",
        data_source="mock_simulation",
        is_simulation=True,
        status="confirmed",
        total_amount=5000.0,
        currency="INR",
        contact_email="delete_me@travelmate.ai",
        contact_phone="+919876543210",
        passenger_details_json=json.dumps([{"first_name": "Test", "last_name": "User"}]),
        user_confirmed=True
    )
    db_session.add(booking)
    db_session.commit()

    booking_id = booking.id

    # Delete user
    db_session.delete(user)
    db_session.commit()

    # Booking must still exist, with user_id set to None
    persisted_booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
    assert persisted_booking is not None
    assert persisted_booking.user_id is None
