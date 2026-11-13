"""
Automated Pytest Suite for Centralized BookingService.
Validates Phase 4, Step 4 specifications:
- 13-step booking sequence
- Live offer revalidation
- Explicit price-change detection and fresh user approval protection
- Currency mismatch detection
- Duplicate booking prevention
- Provider failure and timeout handling (no blind retries)
- Ownership enforcement and booking history privacy protection
- Strict simulation transparency (Condition 2)
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import pytest
import httpx
from pydantic import ValidationError

from app.models.user import User, UserRole
from app.models.flight import FlightSearch, FlightOffer
from app.models.booking import Booking
from app.schemas.booking import (
    BookingCreateRequest,
    PassengerBookingDetails,
    BookingContactDetails,
    BookingResponse,
    BookingSummaryResponse,
    OfferRevalidationResponse,
    mask_passport_number,
)
from app.services.booking_service import (
    BookingService,
    booking_service,
    BookingServiceError,
    BookingOfferNotFoundError,
    BookingOfferExpiredError,
    BookingOfferUnavailableError,
    BookingPriceChangedError,
    BookingCurrencyMismatchError,
    BookingMissingConsentError,
    BookingStaleConsentError,
    BookingInvalidPassengerError,
    BookingDuplicateError,
    BookingProviderError,
    BookingProviderAmbiguousError,
    BookingProviderTimeoutError,
    BookingDatabaseError,
    BookingAccessDeniedError,
)
from app.adapters.duffel_adapter import DuffelFlightProviderAdapter
from app.adapters.mock_adapter import MockFlightProviderAdapter


# ===========================================================================
# Helper Fixtures & Test Data
# ===========================================================================

def create_test_user(db_session, email="traveler@example.com", name="Traveler"):
    user = User(
        email=email,
        hashed_password="hashed_pw_xyz",
        full_name=name,
        role=UserRole.USER
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_test_flight_offer(
    db_session,
    provider_offer_id="mock_off_blr_del_101",
    total_amount=5400.0,
    currency="INR",
    data_source="mock_simulation",
    provider_used="mock"
):
    search = FlightSearch(
        origin_iata="BLR",
        destination_iata="DEL",
        departure_date="2026-11-25",
        passenger_count=1,
        cabin_class="economy",
        provider_used=provider_used,
        data_source=data_source
    )
    db_session.add(search)
    db_session.flush()

    offer = FlightOffer(
        search_id=search.id,
        provider_offer_id=provider_offer_id,
        airline_name="IndiGo" if provider_used == "mock" else "British Airways",
        airline_code="6E" if provider_used == "mock" else "BA",
        flight_number="6E-2054" if provider_used == "mock" else "BA-117",
        origin_iata="BLR" if provider_used == "mock" else "LHR",
        destination_iata="DEL" if provider_used == "mock" else "JFK",
        departure_time="2026-11-25T06:00:00Z",
        arrival_time="2026-11-25T08:45:00Z",
        duration_minutes=165,
        stops=0,
        total_amount=total_amount,
        currency=currency,
        cabin_class="economy",
        data_source=data_source,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    db_session.add(offer)
    db_session.flush()
    return offer


def create_valid_passenger(first_name="Aarav", last_name="Sharma", dob="1992-04-15", gender="male"):
    return PassengerBookingDetails(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=dob,
        gender=gender,
        passport_number="P12345678"
    )


def create_valid_contact(email="aarav.sharma@example.com", phone="+919876543210"):
    return BookingContactDetails(email=email, phone=phone)


# ===========================================================================
# 1. Offer Revalidation Tests
# ===========================================================================

@pytest.mark.anyio
async def test_booking_service_revalidate_offer_success(db_session):
    """Verify offer revalidation through BookingService returns standardized schema."""
    offer = create_test_flight_offer(db_session)
    reval = await booking_service.revalidate_flight_offer(db_session, offer.id)

    assert isinstance(reval, OfferRevalidationResponse)
    assert reval.flight_offer_id == offer.id
    assert reval.is_valid is True
    assert reval.price_changed is False
    assert reval.current_amount == 5400.0
    assert reval.currency == "INR"
    assert reval.is_simulation is True


@pytest.mark.anyio
async def test_booking_service_revalidate_offer_not_found(db_session):
    """Revalidating a non-existent offer ID raises BookingOfferNotFoundError."""
    with pytest.raises(BookingOfferNotFoundError):
        await booking_service.revalidate_flight_offer(db_session, 999999)


# ===========================================================================
# 2. Successful Booking Workflows (Mock & Duffel Sandbox)
# ===========================================================================

@pytest.mark.anyio
async def test_booking_service_successful_mock_booking(db_session):
    """Verify full successful booking workflow for a simulated offer."""
    user = create_test_user(db_session)
    offer = create_test_flight_offer(db_session, total_amount=5400.0, currency="INR")

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True,
        expected_amount=5400.0,
        expected_currency="INR"
    )

    response = await booking_service.create_booking(db_session, request, user_id=user.id)

    assert isinstance(response, BookingResponse)
    assert response.status == "confirmed"
    assert response.is_simulation is True
    assert response.data_source == "mock_simulation"
    assert response.booking_reference.startswith("MOCK-")
    assert response.total_amount == 5400.0
    assert response.currency == "INR"
    assert response.user_confirmed is True

    # Confirm database record was saved
    db_booking = db_session.query(Booking).filter(Booking.id == response.id).first()
    assert db_booking is not None
    assert db_booking.user_id == user.id
    assert db_booking.flight_offer_id == offer.id
    assert db_booking.status == "confirmed"
    assert len(db_booking.passenger_details) == 1
    assert db_booking.passenger_details[0]["first_name"] == "Aarav"


@pytest.mark.anyio
async def test_booking_service_successful_duffel_booking(db_session):
    """Verify full successful booking workflow for a Duffel sandbox offer (mocked HTTP)."""
    user = create_test_user(db_session)
    offer = create_test_flight_offer(
        db_session,
        provider_offer_id="off_0000AjX9DuffelLive",
        total_amount=450.0,
        currency="GBP",
        data_source="duffel_sandbox",
        provider_used="duffel"
    )

    mock_reval_data = {
        "id": "off_0000AjX9DuffelLive",
        "total_amount": "450.00",
        "total_currency": "GBP",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    }
    mock_order_data = {
        "id": "ord_0000AjX9OrderConfirmed",
        "booking_reference": "K7LM9P",
        "total_amount": "450.00",
        "total_currency": "GBP"
    }

    mock_get = httpx.Response(status_code=200, json={"data": mock_reval_data}, request=httpx.Request("GET", "http://test"))
    mock_post = httpx.Response(status_code=201, json={"data": mock_order_data}, request=httpx.Request("POST", "http://test"))

    with patch.object(booking_service.duffel, "api_token", "duffel_test_mock_token_12345678"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as m_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m_post:
        m_get.return_value = mock_get
        m_post.return_value = mock_post

        request = BookingCreateRequest(
            flight_offer_id=offer.id,
            passengers=[create_valid_passenger()],
            contact=create_valid_contact(),
            confirmed_by_user=True,
            expected_amount=450.0,
            expected_currency="GBP"
        )

        response = await booking_service.create_booking(db_session, request, user_id=user.id)

        assert response.status == "confirmed"
        assert response.is_simulation is False
        assert response.data_source == "duffel_sandbox"
        assert response.booking_reference == "K7LM9P"
        assert response.provider_booking_id == "ord_0000AjX9OrderConfirmed"
        assert response.total_amount == 450.0
        assert response.currency == "GBP"


# ===========================================================================
# 3. Price-Change Approval & Fresh Confirmation Protection
# ===========================================================================

@pytest.mark.anyio
async def test_booking_service_price_changed_blocks_booking_without_fresh_approval(db_session):
    """
    If provider price increases/decreases from what was quoted or confirmed by user,
    service MUST STOP immediately and raise BookingPriceChangedError.
    """
    offer = create_test_flight_offer(
        db_session,
        provider_offer_id="mock_off_price_changed",  # Triggers +500 simulation increase in mock adapter
        total_amount=5400.0,
        currency="INR"
    )

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True,
        expected_amount=5400.0,
        expected_currency="INR",
        price_change_accepted=False
    )

    with pytest.raises(BookingPriceChangedError) as exc_info:
        await booking_service.create_booking(db_session, request)

    err = exc_info.value
    assert err.original_amount == 5400.0
    assert err.current_amount == 5900.0
    assert "Fresh user confirmation required" in str(err)

    # Confirm no booking was saved in database
    booking_count = db_session.query(Booking).count()
    assert booking_count == 0


@pytest.mark.anyio
async def test_booking_service_fresh_approval_allows_booking_after_price_change(db_session):
    """
    When the user is notified of a price change and submits fresh explicit confirmation
    matching the new price (5900.0) with price_change_accepted=True, booking proceeds.
    """
    offer = create_test_flight_offer(
        db_session,
        provider_offer_id="mock_off_price_changed",
        total_amount=5400.0,
        currency="INR"
    )

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True,
        expected_amount=5900.0,  # Explicitly matches newly revalidated price!
        expected_currency="INR",
        price_change_accepted=True  # Fresh user approval
    )

    response = await booking_service.create_booking(db_session, request)

    assert response.status == "confirmed"
    assert response.total_amount == 5900.0
    assert response.currency == "INR"


@pytest.mark.anyio
async def test_booking_service_stale_confirmation_rejected(db_session):
    """
    If the user previously confirmed a price change to 5600, but live revalidation
    returns 5900, the stale approval is rejected.
    """
    offer = create_test_flight_offer(
        db_session,
        provider_offer_id="mock_off_price_changed",
        total_amount=5400.0
    )

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True,
        expected_amount=5600.0,  # Stale amount, does not match 5900.0!
        price_change_accepted=True
    )

    with pytest.raises(BookingPriceChangedError):
        await booking_service.create_booking(db_session, request)


@pytest.mark.anyio
async def test_booking_service_currency_changed_blocks_booking(db_session):
    """If provider changes currency from original offer, booking is blocked."""
    offer = create_test_flight_offer(db_session, currency="INR")

    # Mock adapter returning USD instead of INR
    with patch.object(MockFlightProviderAdapter, "revalidate_offer", new_callable=AsyncMock) as m_reval:
        m_reval.return_value = {
            "is_valid": True,
            "price_changed": False,
            "current_amount": 75.0,
            "currency": "USD",
            "data_source": "mock_simulation",
            "is_simulation": True
        }

        request = BookingCreateRequest(
            flight_offer_id=offer.id,
            passengers=[create_valid_passenger()],
            contact=create_valid_contact(),
            confirmed_by_user=True
        )

        with pytest.raises(BookingCurrencyMismatchError):
            await booking_service.create_booking(db_session, request)


# ===========================================================================
# 4. Expiration, Availability & Error Handling Tests
# ===========================================================================

@pytest.mark.anyio
async def test_booking_service_offer_not_found(db_session):
    """Booking a non-existent flight offer ID raises BookingOfferNotFoundError."""
    request = BookingCreateRequest(
        flight_offer_id=999999,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )
    with pytest.raises(BookingOfferNotFoundError):
        await booking_service.create_booking(db_session, request)


@pytest.mark.anyio
async def test_booking_service_expired_offer_blocks_booking(db_session):
    """If provider revalidation reports offer expired, booking is stopped."""
    offer = create_test_flight_offer(db_session, provider_offer_id="mock_off_expired_offer")

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )

    with pytest.raises(BookingOfferExpiredError):
        await booking_service.create_booking(db_session, request)


@pytest.mark.anyio
async def test_booking_service_unavailable_offer_blocks_booking(db_session):
    """If provider revalidation reports offer unavailable, booking is stopped."""
    offer = create_test_flight_offer(db_session, provider_offer_id="mock_off_unavailable_offer")

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )

    with pytest.raises(BookingOfferUnavailableError):
        await booking_service.create_booking(db_session, request)


@pytest.mark.anyio
async def test_booking_service_provider_failure(db_session):
    """When provider order creation fails, service raises BookingProviderError."""
    offer = create_test_flight_offer(db_session, provider_offer_id="mock_off_fail_order_test")

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )

    with pytest.raises(BookingProviderError):
        await booking_service.create_booking(db_session, request)


@pytest.mark.anyio
async def test_booking_service_provider_timeout_without_blind_retry(db_session):
    """
    When provider order creation times out, service raises BookingProviderTimeoutError.
    Prohibits blind automatic retry to prevent double-charging or duplicate bookings.
    """
    offer = create_test_flight_offer(db_session)

    with patch.object(MockFlightProviderAdapter, "create_order", new_callable=AsyncMock) as m_order:
        m_order.return_value = {
            "success": False,
            "provider_booking_id": "",
            "booking_reference": None,
            "status": "failed",
            "error_message": "Connection timed out with airline gateway."
        }

        request = BookingCreateRequest(
            flight_offer_id=offer.id,
            passengers=[create_valid_passenger()],
            contact=create_valid_contact(),
            confirmed_by_user=True
        )

        with pytest.raises(BookingProviderTimeoutError) as exc_info:
            await booking_service.create_booking(db_session, request)

        assert "blind retry prohibited" in str(exc_info.value).lower()
        # Verify adapter was called only once (no blind retry loop)
        assert m_order.call_count == 1


@pytest.mark.anyio
async def test_booking_service_ambiguous_connection_reset_raises_ambiguous_error(db_session):
    """
    Connection reset after request submission is an ambiguous outcome.
    Must raise BookingProviderAmbiguousError and prohibit blind retry.
    """
    offer = create_test_flight_offer(db_session, provider_offer_id="mock_off_connection_reset_test")

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )

    with pytest.raises(BookingProviderAmbiguousError) as exc_info:
        await booking_service.create_booking(db_session, request)

    assert "ambiguous outcome" in str(exc_info.value).lower()
    assert "blind retry prohibited" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_booking_service_ambiguous_server_500_raises_ambiguous_error(db_session):
    """
    HTTP 500/502/503 from provider is an ambiguous outcome.
    Must raise BookingProviderAmbiguousError and prohibit blind retry.
    """
    offer = create_test_flight_offer(db_session, provider_offer_id="mock_off_server_500_test")

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )

    with pytest.raises(BookingProviderAmbiguousError) as exc_info:
        await booking_service.create_booking(db_session, request)

    assert "ambiguous outcome" in str(exc_info.value).lower()
    assert "blind retry prohibited" in str(exc_info.value).lower()



# ===========================================================================
# 5. Duplicate Booking Prevention
# ===========================================================================

@pytest.mark.anyio
async def test_booking_service_duplicate_booking_prevention(db_session):
    """Attempting to book the exact same offer with identical passengers and contact is blocked."""
    offer = create_test_flight_offer(db_session)

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger("Sneha", "Kulkarni", "1995-10-10", "female")],
        contact=create_valid_contact("sneha@example.com"),
        confirmed_by_user=True
    )

    # First booking succeeds
    res1 = await booking_service.create_booking(db_session, request)
    assert res1.status == "confirmed"

    # Second identical booking attempt is rejected
    with pytest.raises(BookingDuplicateError):
        await booking_service.create_booking(db_session, request)


# ===========================================================================
# 6. Privacy & Ownership Enforcement
# ===========================================================================

@pytest.mark.anyio
async def test_booking_service_cross_user_access_denied(db_session):
    """User B cannot view or retrieve User A's booking."""
    user_a = create_test_user(db_session, email="alice@test.com", name="Alice")
    user_b = create_test_user(db_session, email="bob@test.com", name="Bob")
    offer = create_test_flight_offer(db_session)

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger("Alice", "Smith")],
        contact=create_valid_contact("alice@test.com"),
        confirmed_by_user=True
    )

    booking_a = await booking_service.create_booking(db_session, request, user_id=user_a.id)

    # User A can access their booking
    retrieved = booking_service.get_booking_by_id(db_session, booking_a.id, user_id=user_a.id)
    assert retrieved.id == booking_a.id

    # User B is forbidden from accessing User A's booking
    with pytest.raises(BookingAccessDeniedError):
        booking_service.get_booking_by_id(db_session, booking_a.id, user_id=user_b.id)


@pytest.mark.anyio
async def test_booking_service_booking_history_privacy(db_session):
    """
    STRICT PRIVACY GUARANTEE:
    Booking history returns BookingSummaryResponse which deliberately omits
    sensitive personal information (passport numbers, DOB, phone numbers).
    """
    user = create_test_user(db_session)
    offer = create_test_flight_offer(db_session)

    passenger = PassengerBookingDetails(
        first_name="Meera",
        last_name="Iyer",
        date_of_birth="1989-12-05",
        gender="female",
        passport_number="SECRET_PASSPORT_999"
    )
    contact = BookingContactDetails(email="meera@test.com", phone="+919999988888")

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[passenger],
        contact=contact,
        confirmed_by_user=True
    )

    await booking_service.create_booking(db_session, request, user_id=user.id)

    summaries = booking_service.get_user_bookings(db_session, user_id=user.id)
    assert len(summaries) == 1
    item = summaries[0]

    assert isinstance(item, BookingSummaryResponse)
    assert item.passenger_names == ["Meera Iyer"]
    assert item.passenger_count == 1
    assert item.status == "confirmed"

    # Verify sensitive fields are completely absent from summary schema
    summary_dict = item.model_dump()
    assert "passport_number" not in summary_dict
    assert "date_of_birth" not in summary_dict
    assert "contact_phone" not in summary_dict
    assert "SECRET_PASSPORT_999" not in str(summary_dict)
    assert "+919999988888" not in str(summary_dict)


@pytest.mark.anyio
async def test_booking_service_missing_confirmation_blocks_booking():
    """Verify that omitting explicit user confirmation is rejected before booking."""
    with pytest.raises(ValidationError) as exc:
        BookingCreateRequest(
            flight_offer_id=1,
            passengers=[create_valid_passenger()],
            contact=create_valid_contact(),
            confirmed_by_user=False  # Consent omitted
        )
    assert "Explicit user consent" in str(exc.value)


@pytest.mark.anyio
async def test_booking_service_invalid_passenger_validation(db_session):
    """Verify passenger validation failures raise appropriate exceptions."""
    offer = create_test_flight_offer(db_session)

    # Empty names fail at Pydantic schema level
    with pytest.raises(ValidationError):
        PassengerBookingDetails(
            first_name="   ",
            last_name="Kumar",
            date_of_birth="1990-01-01"
        )

    # Future date of birth fails
    future_dob = (datetime.now().date() + timedelta(days=10)).isoformat()
    with pytest.raises(ValidationError):
        PassengerBookingDetails(
            first_name="Raj",
            last_name="Kumar",
            date_of_birth=future_dob
        )


@pytest.mark.anyio
async def test_booking_service_mock_transparency_guarantee(db_session):
    """
    Condition 2 Compliance:
    All simulated bookings must carry explicit transparency markers:
    is_simulation = True, data_source = 'mock_simulation', and MOCK- reference.
    """
    offer = create_test_flight_offer(db_session)
    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )

    response = await booking_service.create_booking(db_session, request)

    assert response.is_simulation is True
    assert response.data_source == "mock_simulation"
    assert response.booking_reference.startswith("MOCK-")
    assert "MOCK-" in response.booking_reference


@pytest.mark.anyio
async def test_booking_service_database_error_handling(db_session):
    """Database commit failure during booking creation raises BookingDatabaseError."""
    from sqlalchemy.exc import OperationalError

    offer = create_test_flight_offer(db_session)
    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )

    with patch.object(db_session, "commit", side_effect=OperationalError("db locked", {}, None)):
        with pytest.raises(BookingDatabaseError):
            await booking_service.create_booking(db_session, request)


# ===========================================================================
# 7. Passport Masking & Privacy Remediation Unit Tests
# ===========================================================================

def test_mask_passport_number_cases():
    """
    Validates passport number masking across all categories:
    - Missing (None, empty string, whitespace)
    - Short (<= 4 characters)
    - Normal (> 4 characters)
    """
    # 1. Missing
    assert mask_passport_number(None) is None
    assert mask_passport_number("") is None
    assert mask_passport_number("   ") is None

    # 2. Short (<= 4 characters)
    assert mask_passport_number("1234") == "****"
    assert mask_passport_number("AB") == "****"
    assert mask_passport_number("X") == "****"

    # 3. Normal (> 4 characters) - Only the last 4 characters are exposed
    assert mask_passport_number("A1235678") == "****5678"
    assert mask_passport_number("US987654321") == "****4321"
    assert mask_passport_number("TOP_SECRET_PASSPORT_888") == "****_888"


@pytest.mark.anyio
async def test_booking_response_masks_passports_without_altering_raw_database(db_session):
    """
    Ensures that serialized BookingResponse masks passport numbers,
    while the raw database passenger_details_json preserves the genuine document for ticketing.
    """
    user = create_test_user(db_session, email="masking_test@travelmate.ai")
    offer = create_test_flight_offer(db_session)

    raw_passport = "A87654321"
    passenger = PassengerBookingDetails(
        first_name="Ravi",
        last_name="Shankar",
        date_of_birth="1985-05-15",
        gender="male",
        passport_number=raw_passport
    )
    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[passenger],
        contact=create_valid_contact("ravi@test.com"),
        confirmed_by_user=True
    )

    response = await booking_service.create_booking(db_session, request, user_id=user.id)

    # 1. Serialized response must be masked
    assert response.passengers[0].passport_number == "****4321"
    assert raw_passport not in response.model_dump_json()

    # 2. Raw database record must retain original passport for airline ticketing
    db_booking = db_session.query(Booking).filter(Booking.id == response.id).first()
    assert db_booking is not None
    assert raw_passport in db_booking.passenger_details_json


@pytest.mark.anyio
async def test_get_booking_by_id_unauthenticated_and_guest_privacy(db_session):
    """
    Validates ownership enforcement on get_booking_by_id:
    - user_id=None raises BookingAccessDeniedError
    - Legacy guest booking with user_id=None cannot be accessed by any user
    """
    user = create_test_user(db_session, email="owner_test@travelmate.ai")
    offer = create_test_flight_offer(db_session)

    request = BookingCreateRequest(
        flight_offer_id=offer.id,
        passengers=[create_valid_passenger()],
        contact=create_valid_contact(),
        confirmed_by_user=True
    )
    booking = await booking_service.create_booking(db_session, request, user_id=user.id)

    # Unauthenticated caller denied
    with pytest.raises(BookingAccessDeniedError) as exc_info:
        booking_service.get_booking_by_id(db_session, booking.id, user_id=None)
    assert "Authentication is required" in str(exc_info.value)

    # Legacy guest booking with user_id=None created directly
    guest_booking = Booking(
        user_id=None,
        flight_offer_id=offer.id,
        provider_used="mock",
        data_source="mock_simulation",
        is_simulation=True,
        status="confirmed",
        total_amount=5400.0,
        currency="INR",
        contact_email="guest@test.com",
        contact_phone="+919876543210",
        passenger_details_json="[]",
        user_confirmed=True
    )
    db_session.add(guest_booking)
    db_session.commit()

    # Even an authenticated user cannot access an unowned/guest booking
    with pytest.raises(BookingAccessDeniedError) as exc_info2:
        booking_service.get_booking_by_id(db_session, guest_booking.id, user_id=user.id)
    assert "forbidden" in str(exc_info2.value).lower()


