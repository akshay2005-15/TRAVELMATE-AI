"""
Unit test suite for Flight Booking Pydantic Schemas.
Tests passenger validation, consent enforcement, data sanitation, and ordinary history privacy protection.
"""

from datetime import datetime, date, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.schemas.booking import (
    PassengerBookingDetails,
    BookingContactDetails,
    BookingCreateRequest,
    BookingResponse,
    BookingSummaryResponse,
    OfferRevalidationRequest,
    OfferRevalidationResponse,
)
from app.models.booking import Booking
from app.models.flight import FlightOffer


def test_valid_passenger_booking_details():
    p = PassengerBookingDetails(
        first_name="  Aarav  ",
        last_name="  Sharma  ",
        date_of_birth="1992-08-24",
        gender="MALE",
        passport_number="  z1234567  "
    )
    assert p.first_name == "Aarav"
    assert p.last_name == "Sharma"
    assert p.date_of_birth == "1992-08-24"
    assert p.gender == "male"
    assert p.passport_number == "Z1234567"


def test_invalid_passenger_name_rejected():
    # Empty first name
    with pytest.raises(ValidationError) as exc:
        PassengerBookingDetails(
            first_name="",
            last_name="Verma",
            date_of_birth="1995-01-01"
        )
    assert "at least 1 character" in str(exc.value) or "cannot be empty" in str(exc.value)

    # Whitespace only
    with pytest.raises(ValidationError):
        PassengerBookingDetails(
            first_name="   ",
            last_name="Verma",
            date_of_birth="1995-01-01"
        )


def test_future_date_of_birth_rejected():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError) as exc:
        PassengerBookingDetails(
            first_name="Siddharth",
            last_name="Mehta",
            date_of_birth=tomorrow
        )
    assert "must be in the past" in str(exc.value)


def test_invalid_dob_format_rejected():
    with pytest.raises(ValidationError) as exc:
        PassengerBookingDetails(
            first_name="Siddharth",
            last_name="Mehta",
            date_of_birth="24/08/1992"  # non-ISO format
        )
    assert "date_of_birth" in str(exc.value).lower()


def test_invalid_gender_rejected():
    with pytest.raises(ValidationError) as exc:
        PassengerBookingDetails(
            first_name="Siddharth",
            last_name="Mehta",
            date_of_birth="1992-08-24",
            gender="robot"
        )
    assert "Gender must be 'male', 'female', or 'other'" in str(exc.value)


def test_contact_details_validation():
    # Valid contact
    contact = BookingContactDetails(
        email="traveler@example.com",
        phone="+91 98765 43210"
    )
    assert contact.email == "traveler@example.com"
    assert contact.phone == "+91 98765 43210"

    # Invalid email
    with pytest.raises(ValidationError):
        BookingContactDetails(email="not-an-email", phone="+919876543210")

    # Invalid phone (too short)
    with pytest.raises(ValidationError) as exc1:
        BookingContactDetails(email="test@example.com", phone="12345")
    assert "at least 7 digits" in str(exc1.value) or "at least 7 characters" in str(exc1.value)

    # Invalid phone (contains letters)
    with pytest.raises(ValidationError) as exc2:
        BookingContactDetails(email="test@example.com", phone="phone1234567")
    assert "Invalid phone number format" in str(exc2.value)


def test_booking_create_request_requires_explicit_consent():
    """
    CRITICAL SAFETY REQUIREMENT:
    A booking request must not be considered authorized unless the user explicitly confirms it.
    """
    passenger = PassengerBookingDetails(
        first_name="Neha",
        last_name="Kapoor",
        date_of_birth="1998-11-12",
        gender="female"
    )
    contact = BookingContactDetails(
        email="neha@example.com",
        phone="+919988776655"
    )

    # Valid with confirmed_by_user=True
    req = BookingCreateRequest(
        flight_offer_id=10,
        passengers=[passenger],
        contact=contact,
        confirmed_by_user=True
    )
    assert req.confirmed_by_user is True

    # REJECTED if confirmed_by_user=False
    with pytest.raises(ValidationError) as exc:
        BookingCreateRequest(
            flight_offer_id=10,
            passengers=[passenger],
            contact=contact,
            confirmed_by_user=False
        )
    assert "Explicit user consent and confirmation are required" in str(exc.value)


def test_booking_create_request_rejects_duplicate_passengers():
    p1 = PassengerBookingDetails(
        first_name="Rohan",
        last_name="Joshi",
        date_of_birth="1990-03-15",
        gender="male"
    )
    p2 = PassengerBookingDetails(
        first_name="Rohan",
        last_name="Joshi",
        date_of_birth="1990-03-15",  # identical passenger
        gender="male"
    )
    contact = BookingContactDetails(email="rohan@example.com", phone="+919876543210")

    with pytest.raises(ValidationError) as exc:
        BookingCreateRequest(
            flight_offer_id=5,
            passengers=[p1, p2],
            contact=contact,
            confirmed_by_user=True
        )
    assert "Duplicate passenger detected" in str(exc.value)


def test_booking_create_passenger_count_boundaries():
    contact = BookingContactDetails(email="user@example.com", phone="+919876543210")

    # Min 1 passenger
    with pytest.raises(ValidationError):
        BookingCreateRequest(
            flight_offer_id=1,
            passengers=[],
            contact=contact,
            confirmed_by_user=True
        )

    # Max 9 passengers
    passengers_10 = [
        PassengerBookingDetails(
            first_name=f"Traveler{i}",
            last_name="Test",
            date_of_birth=f"199{i}-01-01"
        )
        for i in range(10)
    ]
    with pytest.raises(ValidationError):
        BookingCreateRequest(
            flight_offer_id=1,
            passengers=passengers_10,
            contact=contact,
            confirmed_by_user=True
        )


def test_booking_summary_conceals_sensitive_passenger_info():
    """
    CRITICAL PRIVACY REQUIREMENT:
    Ordinary booking-history responses MUST NOT expose passport numbers, birth dates, or phone numbers.
    """
    raw_booking = {
        "id": 101,
        "booking_reference": "MOCK-6E-8899",
        "status": "confirmed",
        "total_amount": 10800.0,
        "currency": "INR",
        "data_source": "mock_simulation",
        "is_simulation": True,
        "passenger_details_json": '[{"first_name": "Kavita", "last_name": "Nair", "date_of_birth": "1994-07-20", "passport_number": "P8765432"}, {"first_name": "Vikram", "last_name": "Nair", "date_of_birth": "1991-03-10", "passport_number": "P1234567"}]',
        "created_at": datetime.now(timezone.utc)
    }

    summary = BookingSummaryResponse.model_validate(raw_booking)

    # Verify summary fields
    assert summary.id == 101
    assert summary.booking_reference == "MOCK-6E-8899"
    assert summary.passenger_count == 2
    assert summary.passenger_names == ["Kavita Nair", "Vikram Nair"]

    # Export dictionary and verify NO sensitive fields exist
    dumped = summary.model_dump()
    assert "passport_number" not in dumped
    assert "passports" not in dumped
    assert "date_of_birth" not in dumped
    assert "contact_phone" not in dumped
    assert "contact_email" not in dumped
    assert "passenger_details_json" not in dumped


def test_offer_revalidation_schemas():
    req = OfferRevalidationRequest(flight_offer_id=42)
    assert req.flight_offer_id == 42

    with pytest.raises(ValidationError):
        OfferRevalidationRequest(flight_offer_id=0)  # gt=0

    # Response indicating valid price
    resp = OfferRevalidationResponse(
        flight_offer_id=42,
        provider_offer_id="mock_off_123",
        is_valid=True,
        price_changed=False,
        current_amount=5400.0,
        original_amount=5400.0,
        currency="INR",
        data_source="mock_simulation",
        is_simulation=True,
        message="Offer is active and verified."
    )
    assert resp.is_valid is True
    assert resp.price_changed is False

    # Response indicating price update
    resp_updated = OfferRevalidationResponse(
        flight_offer_id=42,
        provider_offer_id="mock_off_123",
        is_valid=True,
        price_changed=True,
        current_amount=5800.0,
        original_amount=5400.0,
        currency="INR",
        data_source="duffel_sandbox",
        is_simulation=False,
        message="Price has updated from 5400.0 to 5800.0."
    )
    assert resp_updated.price_changed is True
    assert resp_updated.current_amount == 5800.0


def test_booking_response_maps_flight_offer_to_toplevel():
    """
    Regression test: Verifies that BookingResponse maps flight details
    (departure_time, departure_date, stops, airports, airline) to top-level fields
    from flight_offer so frontend never encounters 'Invalid Date' or 'undefined stop'.
    """
    raw_booking = {
        "id": 1,
        "booking_reference": "MOCK-B0C465",
        "provider_booking_id": "mock_ord_b0c465",
        "provider_used": "mock",
        "data_source": "mock_simulation",
        "is_simulation": True,
        "status": "confirmed",
        "total_amount": 4600.0,
        "currency": "INR",
        "contact_email": "bob@gmail.com",
        "contact_phone": "123456789",
        "passengers": [
            {
                "first_name": "John",
                "last_name": "Tea",
                "date_of_birth": "2005-01-01",
                "gender": "male",
                "passport_number": "560099"
            }
        ],
        "flight_offer": {
            "id": 1278,
            "provider_offer_id": "mock_off_53a3c7c91c8a",
            "airline_name": "IndiGo",
            "airline_code": "6E",
            "flight_number": "6E-5032",
            "origin_iata": "BLR",
            "destination_iata": "DEL",
            "departure_time": "2026-11-18T14:45:00+00:00",
            "arrival_time": "2026-11-18T19:05:00+00:00",
            "duration_minutes": 260,
            "stops": 1,
            "stop_details": "1 stop via BOM",
            "total_amount": 4600.0,
            "currency": "INR",
            "cabin_class": "economy",
            "baggage_included": "15 kg Check-in",
            "data_source": "mock_simulation",
            "is_simulation": True
        },
        "user_confirmed": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    resp = BookingResponse.model_validate(raw_booking)
    assert resp.airline_name == "IndiGo"
    assert resp.airline_code == "6E"
    assert resp.flight_number == "6E-5032"
    assert resp.origin_iata == "BLR"
    assert resp.destination_iata == "DEL"
    assert resp.departure_time == "2026-11-18T14:45:00+00:00"
    assert resp.departure_date == "2026-11-18"
    assert resp.arrival_time == "2026-11-18T19:05:00+00:00"
    assert resp.stops == 1
    # Check passport masking
    assert resp.passengers[0].passport_number == "****0099"


def test_booking_summary_maps_flight_offer_date_and_stops():
    """
    Regression test: Verifies that BookingSummaryResponse populates departure_date and stops
    so Booking History and Dashboard never display 'Invalid Date', 'N/A', or missing stops.
    """
    raw_booking = {
        "id": 101,
        "booking_reference": "MOCK-6E-8899",
        "status": "confirmed",
        "total_amount": 10800.0,
        "currency": "INR",
        "data_source": "mock_simulation",
        "is_simulation": True,
        "passenger_details_json": '[{"first_name": "Kavita", "last_name": "Nair"}]',
        "departure_time": "2026-11-18T14:45:00+00:00",
        "created_at": datetime.now(timezone.utc)
    }

    summary = BookingSummaryResponse.model_validate(raw_booking)
    assert summary.departure_time == "2026-11-18T14:45:00+00:00"
    assert summary.departure_date == "2026-11-18"
    assert summary.stops == 0

