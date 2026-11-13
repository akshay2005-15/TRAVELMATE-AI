"""
Automated Pytest Suite for FastAPI Flight Booking Endpoints.
Validates Phase 4, Step 5 specifications & Security Remediation:
- POST /api/v1/bookings/revalidate (Offer revalidation, price change detection - unauthenticated allowed)
- POST /api/v1/bookings (Order creation, price protection, validation - strictly requires authentication)
- GET  /api/v1/bookings (Authenticated user history with strict privacy protection)
- GET  /api/v1/bookings/{id} (Booking details with ownership enforcement & passport masking)
- Database-backed idempotency & duplicate submission protection
- Error-to-HTTP status code mappings (400, 401, 403, 404, 409, 410, 422, 502, 504)
"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from app.models.flight import FlightSearch, FlightOffer
from app.models.booking import Booking
from app.models.idempotency import IdempotencyRecord, BookingIntentReservation
from app.models.user import User
from app.adapters.mock_adapter import MockFlightProviderAdapter
from app.services.booking_service import booking_service


# ===========================================================================
# Helper Setup Functions
# ===========================================================================

def get_auth_token(client, email="user@travelmate.ai", password="Password123!"):
    """Registers a test user and returns access token and headers."""
    reg_res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test Traveler"
    })
    token = reg_res.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def create_test_offer(
    client,
    db_session,
    provider_offer_id="mock_off_blr_del_201",
    total_amount=5400.0,
    currency="INR",
    data_source="mock_simulation",
    provider_used="mock"
):
    """Directly creates a test flight offer in the test database."""
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
        airline_name="IndiGo",
        airline_code="6E",
        flight_number="6E-2054",
        origin_iata="BLR",
        destination_iata="DEL",
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
    db_session.commit()
    db_session.refresh(offer)
    return offer


def make_booking_payload(
    flight_offer_id: int,
    first_name="Rohan",
    last_name="Verma",
    email="rohan.verma@example.com",
    confirmed=True,
    expected_amount=None,
    expected_currency=None,
    price_change_accepted=False,
    passport_number="P88776655"
):
    payload = {
        "flight_offer_id": flight_offer_id,
        "passengers": [
            {
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": "1993-07-21",
                "gender": "male",
                "passport_number": passport_number
            }
        ],
        "contact": {
            "email": email,
            "phone": "+919876543210"
        },
        "confirmed_by_user": confirmed,
        "price_change_accepted": price_change_accepted
    }
    if expected_amount is not None:
        payload["expected_amount"] = expected_amount
    if expected_currency is not None:
        payload["expected_currency"] = expected_currency
    return payload


# ===========================================================================
# 1. POST /api/v1/bookings/revalidate Tests (Unauthenticated Allowed)
# ===========================================================================

def test_revalidate_endpoint_success(client, db_session):
    """Revalidates an active flight offer and returns current fare and validity."""
    offer = create_test_offer(client, db_session)

    res = client.post("/api/v1/bookings/revalidate", json={"flight_offer_id": offer.id})
    assert res.status_code == 200
    data = res.json()

    assert data["flight_offer_id"] == offer.id
    assert data["is_valid"] is True
    assert data["price_changed"] is False
    assert data["current_amount"] == 5400.0
    assert data["currency"] == "INR"
    assert data["is_simulation"] is True


def test_revalidate_endpoint_price_change(client, db_session):
    """Revalidates an offer that has experienced a provider price update."""
    offer = create_test_offer(
        client,
        db_session,
        provider_offer_id="mock_off_blr_price_changed",
        total_amount=5400.0
    )

    res = client.post("/api/v1/bookings/revalidate", json={"flight_offer_id": offer.id})
    assert res.status_code == 200
    data = res.json()

    assert data["flight_offer_id"] == offer.id
    assert data["is_valid"] is True
    assert data["price_changed"] is True
    assert data["current_amount"] == 5900.0  # +500 simulation increase
    assert data["original_amount"] == 5400.0


def test_revalidate_endpoint_offer_not_found(client):
    """Revalidating a nonexistent offer ID returns 404 Not Found."""
    res = client.post("/api/v1/bookings/revalidate", json={"flight_offer_id": 999999})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# ===========================================================================
# 2. POST /api/v1/bookings (Create Booking) Tests (Strict Auth Required)
# ===========================================================================

def test_create_booking_endpoint_success_authenticated(client, db_session):
    """Authenticated user creates a simulated flight booking order."""
    token, headers = get_auth_token(client, "traveler1@travelmate.ai")
    offer = create_test_offer(client, db_session)

    payload = make_booking_payload(offer.id, expected_amount=5400.0, expected_currency="INR")
    res = client.post("/api/v1/bookings", json=payload, headers=headers)

    assert res.status_code == 201
    data = res.json()

    assert data["id"] > 0
    assert data["status"] == "confirmed"
    assert data["booking_reference"].startswith("MOCK-")
    assert data["is_simulation"] is True
    assert data["data_source"] == "mock_simulation"
    assert data["total_amount"] == 5400.0
    assert data["currency"] == "INR"
    assert data["user_confirmed"] is True
    assert len(data["passengers"]) == 1
    assert data["passengers"][0]["first_name"] == "Rohan"
    assert data["passengers"][0]["passport_number"] == "****6655"  # Masked passport


def test_create_booking_unauthenticated_fails(client, db_session):
    """Guest / unauthenticated request to create booking returns 401 Unauthorized."""
    offer = create_test_offer(client, db_session)
    payload = make_booking_payload(offer.id, first_name="Guest", last_name="User", email="guest@example.com")
    res = client.post("/api/v1/bookings", json=payload)  # No auth headers

    assert res.status_code == 401


def test_create_booking_endpoint_missing_consent(client, db_session):
    """Booking creation without explicit user confirmation is rejected with 422 Unprocessable Entity."""
    token, headers = get_auth_token(client, "consent_user@travelmate.ai")
    offer = create_test_offer(client, db_session)

    payload = make_booking_payload(offer.id, confirmed=False)
    res = client.post("/api/v1/bookings", json=payload, headers=headers)

    assert res.status_code == 422
    assert "explicit user consent" in str(res.json()).lower()


def test_create_booking_endpoint_price_changed_blocks_booking(client, db_session):
    """
    When live price differs from quoted fare, API stops immediately with 409 Conflict
    and returns detailed information prompting fresh confirmation.
    """
    token, headers = get_auth_token(client, "price_change_user@travelmate.ai")
    offer = create_test_offer(
        client,
        db_session,
        provider_offer_id="mock_off_price_changed",
        total_amount=5400.0
    )

    payload = make_booking_payload(offer.id, expected_amount=5400.0, price_change_accepted=False)
    res = client.post("/api/v1/bookings", json=payload, headers=headers)

    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["error_code"] == "price_changed"
    assert detail["price_changed"] is True
    assert detail["original_amount"] == 5400.0
    assert detail["current_amount"] == 5900.0
    assert detail["requires_fresh_confirmation"] is True


def test_create_booking_endpoint_fresh_price_approval_succeeds(client, db_session):
    """
    When client passes updated expected_amount matching revalidated fare along with
    price_change_accepted=True, booking proceeds and succeeds with 201 Created.
    """
    token, headers = get_auth_token(client, "fresh_price_user@travelmate.ai")
    offer = create_test_offer(
        client,
        db_session,
        provider_offer_id="mock_off_price_changed",
        total_amount=5400.0
    )

    payload = make_booking_payload(
        offer.id,
        expected_amount=5900.0,  # Explicit fresh approval matching revalidation
        price_change_accepted=True
    )
    res = client.post("/api/v1/bookings", json=payload, headers=headers)

    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "confirmed"
    assert data["total_amount"] == 5900.0


def test_create_booking_endpoint_invalid_passenger_data(client, db_session):
    """Validation failure on passenger details returns 422 Unprocessable Entity."""
    token, headers = get_auth_token(client, "invalid_pax_user@travelmate.ai")
    offer = create_test_offer(client, db_session)

    payload = {
        "flight_offer_id": offer.id,
        "passengers": [
            {
                "first_name": "",  # Empty name fails min_length=1
                "last_name": "Test",
                "date_of_birth": "1990-01-01"
            }
        ],
        "contact": {"email": "test@test.com", "phone": "+919876543210"},
        "confirmed_by_user": True
    }
    res = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res.status_code == 422


def test_create_booking_endpoint_provider_failure(client, db_session):
    """Provider order creation failure returns 502 Bad Gateway."""
    token, headers = get_auth_token(client, "fail_prov_user@travelmate.ai")
    offer = create_test_offer(
        client,
        db_session,
        provider_offer_id="mock_off_fail_order_test"
    )

    payload = make_booking_payload(offer.id)
    res = client.post("/api/v1/bookings", json=payload, headers=headers)

    assert res.status_code == 502
    assert "provider_error" in res.json()["detail"]["error_code"]


def test_create_booking_endpoint_provider_timeout(client, db_session):
    """
    Provider timeout returns 504 Gateway Timeout and clearly notifies the user
    that status is uncertain and blind retry is prohibited.
    """
    token, headers = get_auth_token(client, "timeout_prov_user@travelmate.ai")
    offer = create_test_offer(client, db_session)

    with patch.object(MockFlightProviderAdapter, "create_order", new_callable=AsyncMock) as m_order:
        m_order.return_value = {
            "success": False,
            "provider_booking_id": "",
            "booking_reference": None,
            "status": "failed",
            "error_message": "Gateway connection timed out after 25s."
        }

        payload = make_booking_payload(offer.id)
        res = client.post("/api/v1/bookings", json=payload, headers=headers)

        assert res.status_code == 504
        detail = res.json()["detail"]
        assert detail["error_code"] in ("provider_timeout", "provider_uncertain")
        assert "uncertain" in detail["message"].lower()
        assert "prohibited" in detail["message"].lower()


def test_create_booking_endpoint_duplicate_request_protection(client, db_session):
    """
    Attempting to book the identical flight offer and passenger identity with a new key returns 409 Conflict.
    """
    token, headers = get_auth_token(client, "dup_test_user@travelmate.ai")
    offer = create_test_offer(client, db_session)
    payload1 = make_booking_payload(offer.id, email="unique_person@test.com")
    payload1["idempotency_key"] = "test-dup-key-alpha"

    # 1. First booking succeeds
    res1 = client.post("/api/v1/bookings", json=payload1, headers=headers)
    assert res1.status_code == 201

    # 2. Immediate duplicate booking attempt with different key is rejected by duplicate passenger guard
    payload2 = make_booking_payload(offer.id, email="unique_person@test.com")
    payload2["idempotency_key"] = "test-dup-key-beta"
    res2 = client.post("/api/v1/bookings", json=payload2, headers=headers)
    assert res2.status_code == 409
    assert "duplicate_booking" in res2.json()["detail"]["error_code"]


# ===========================================================================
# 3. GET /api/v1/bookings (History & Privacy) Tests
# ===========================================================================

def test_get_booking_history_authenticated(client, db_session):
    """Authenticated user retrieves their booking history."""
    token, headers = get_auth_token(client, "history_user@travelmate.ai")
    offer1 = create_test_offer(client, db_session, provider_offer_id="mock_off_hist_1")

    payload = make_booking_payload(offer1.id)
    client.post("/api/v1/bookings", json=payload, headers=headers)

    res = client.get("/api/v1/bookings", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["status"] == "confirmed"
    assert items[0]["passenger_count"] == 1
    assert items[0]["passenger_names"] == ["Rohan Verma"]


def test_get_booking_history_unauthenticated_fails(client):
    """Unauthenticated request to booking history returns 401 Unauthorized."""
    res = client.get("/api/v1/bookings")
    assert res.status_code == 401


def test_booking_history_excludes_sensitive_data(client, db_session):
    """
    STRICT PRIVACY REQUIREMENT:
    Booking history response must NEVER contain passport numbers, date of birth,
    or phone numbers.
    """
    token, headers = get_auth_token(client, "privacy_tester@travelmate.ai")
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_priv_1")

    payload = {
        "flight_offer_id": offer.id,
        "passengers": [
            {
                "first_name": "Siddharth",
                "last_name": "Menon",
                "date_of_birth": "1988-09-14",
                "gender": "male",
                "passport_number": "TOP_SECRET_PASSPORT_888"
            }
        ],
        "contact": {
            "email": "sid@test.com",
            "phone": "+918888877777"
        },
        "confirmed_by_user": True
    }
    client.post("/api/v1/bookings", json=payload, headers=headers)

    res = client.get("/api/v1/bookings", headers=headers)
    assert res.status_code == 200
    raw_text = res.text

    assert "TOP_SECRET_PASSPORT_888" not in raw_text
    assert "1988-09-14" not in raw_text
    assert "+918888877777" not in raw_text
    assert "passport_number" not in raw_text
    assert "date_of_birth" not in raw_text


# ===========================================================================
# 4. GET /api/v1/bookings/{booking_id} (Details & Ownership) Tests
# ===========================================================================

def test_get_booking_detail_success(client, db_session):
    """User can view details of their own booking."""
    token, headers = get_auth_token(client, "owner_user@travelmate.ai")
    offer = create_test_offer(client, db_session)

    payload = make_booking_payload(offer.id)
    create_res = client.post("/api/v1/bookings", json=payload, headers=headers)
    booking_id = create_res.json()["id"]

    res = client.get(f"/api/v1/bookings/{booking_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == booking_id
    assert data["status"] == "confirmed"


def test_get_booking_detail_unauthenticated_fails(client, db_session):
    """Unauthenticated request to view booking detail returns 401 Unauthorized."""
    token, headers = get_auth_token(client, "owner_for_401@travelmate.ai")
    offer = create_test_offer(client, db_session)

    payload = make_booking_payload(offer.id)
    create_res = client.post("/api/v1/bookings", json=payload, headers=headers)
    booking_id = create_res.json()["id"]

    # Calling without Authorization header returns 401
    res = client.get(f"/api/v1/bookings/{booking_id}")
    assert res.status_code == 401


def test_get_booking_detail_cross_user_forbidden(client, db_session):
    """User B attempting to view User A's booking receives 403 Forbidden."""
    token_a, headers_a = get_auth_token(client, "user_a@travelmate.ai")
    token_b, headers_b = get_auth_token(client, "user_b@travelmate.ai")
    offer = create_test_offer(client, db_session)

    payload = make_booking_payload(offer.id)
    create_res = client.post("/api/v1/bookings", json=payload, headers=headers_a)
    booking_id = create_res.json()["id"]

    # User B tries to view User A's booking
    res = client.get(f"/api/v1/bookings/{booking_id}", headers=headers_b)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


def test_get_booking_detail_not_found(client):
    """Requesting nonexistent booking ID returns 404 Not Found."""
    token, headers = get_auth_token(client, "nonexistent_tester@travelmate.ai")
    res = client.get("/api/v1/bookings/999999", headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_legacy_guest_booking_forbidden(client, db_session):
    """Authenticated user cannot access legacy unowned/guest booking (403 Forbidden)."""
    token, headers = get_auth_token(client, "unowned_viewer@travelmate.ai")
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_guest_sec")
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

    res = client.get(f"/api/v1/bookings/{guest_booking.id}", headers=headers)
    assert res.status_code == 403


# ===========================================================================
# 5. Passport Masking Tests in API Responses
# ===========================================================================

def test_booking_api_masks_passport_normal(client, db_session):
    """Normal passport number (> 4 chars) is masked showing only the last 4 characters."""
    token, headers = get_auth_token(client, "mask_normal@travelmate.ai")
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_mask_norm")

    payload = make_booking_payload(offer.id, passport_number="AB12345678")
    res = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res.status_code == 201

    data = res.json()
    assert data["passengers"][0]["passport_number"] == "****5678"
    assert "AB1234" not in res.text

    # Verify detail retrieval also masks passport
    detail_res = client.get(f"/api/v1/bookings/{data['id']}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["passengers"][0]["passport_number"] == "****5678"
    assert "AB1234" not in detail_res.text


def test_booking_api_masks_passport_short(client, db_session):
    """Short passport number (<= 4 chars) is completely masked as '****'."""
    token, headers = get_auth_token(client, "mask_short@travelmate.ai")
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_mask_shrt")

    payload = make_booking_payload(offer.id, passport_number="1234")
    res = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res.status_code == 201

    data = res.json()
    assert data["passengers"][0]["passport_number"] == "****"


def test_booking_api_masks_passport_missing(client, db_session):
    """Missing passport number (None) remains None in responses."""
    token, headers = get_auth_token(client, "mask_none@travelmate.ai")
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_mask_none")

    payload = make_booking_payload(offer.id, passport_number=None)
    res = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res.status_code == 201

    data = res.json()
    assert data["passengers"][0]["passport_number"] is None


# ===========================================================================
# 6. Database-Backed Idempotency Tests
# ===========================================================================

def test_idempotency_same_key_same_payload_returns_cached_booking(client, db_session):
    """Same idempotency key and identical payload returns completed booking without calling provider order creation again."""
    token, headers = get_auth_token(client, "idem_success@travelmate.ai")
    headers["Idempotency-Key"] = "test-idem-key-100"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_idem_1")

    payload = make_booking_payload(offer.id)

    with patch.object(MockFlightProviderAdapter, "create_order", wraps=MockFlightProviderAdapter().create_order) as m_order:
        res1 = client.post("/api/v1/bookings", json=payload, headers=headers)
        assert res1.status_code == 201
        data1 = res1.json()

        # Second request with identical key and payload
        res2 = client.post("/api/v1/bookings", json=payload, headers=headers)
        assert res2.status_code in (200, 201)
        data2 = res2.json()

        assert data1["id"] == data2["id"]
        assert data1["booking_reference"] == data2["booking_reference"]
        # Verify provider was only called once
        assert m_order.call_count == 1


def test_idempotency_same_key_different_payload_fails(client, db_session):
    """Reusing an idempotency key with a changed request payload returns 422 Unprocessable Entity."""
    token, headers = get_auth_token(client, "idem_mismatch@travelmate.ai")
    headers["Idempotency-Key"] = "test-idem-key-mismatch"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_idem_2")

    payload1 = make_booking_payload(offer.id, first_name="First")
    res1 = client.post("/api/v1/bookings", json=payload1, headers=headers)
    assert res1.status_code == 201

    # Changed payload under identical key
    payload2 = make_booking_payload(offer.id, first_name="Changed")
    res2 = client.post("/api/v1/bookings", json=payload2, headers=headers)
    assert res2.status_code == 422
    assert "mismatch" in res2.text.lower()


def test_idempotency_in_progress_returns_409(client, db_session):
    """An idempotency record with status 'processing' rejects concurrent submission with 409 Conflict."""
    token, headers = get_auth_token(client, "idem_progress@travelmate.ai")
    headers["Idempotency-Key"] = "test-idem-key-progress"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_idem_3")

    payload = make_booking_payload(offer.id)

    # Pre-seed an in-progress record in DB
    from app.schemas.booking import BookingCreateRequest
    from app.api.v1.endpoints.bookings import _compute_request_hash
    user = db_session.query(User).filter(User.email == "idem_progress@travelmate.ai").first()
    req_obj = BookingCreateRequest.model_validate(payload)
    req_hash = _compute_request_hash(req_obj)

    rec = IdempotencyRecord(
        user_id=user.id,
        idempotency_key="test-idem-key-progress",
        request_hash=req_hash,
        status="processing"
    )
    db_session.add(rec)
    db_session.commit()

    res = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res.status_code == 409
    assert "currently processing" in res.text.lower()


def test_idempotency_uncertain_timeout_returns_504(client, db_session):
    """Retrying an idempotency key after an uncertain provider timeout returns 504 without re-calling provider."""
    token, headers = get_auth_token(client, "idem_uncertain@travelmate.ai")
    headers["Idempotency-Key"] = "test-idem-key-uncertain"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_idem_4")

    payload = make_booking_payload(offer.id)

    with patch.object(MockFlightProviderAdapter, "create_order", new_callable=AsyncMock) as m_order:
        m_order.return_value = {
            "success": False,
            "provider_booking_id": "",
            "booking_reference": None,
            "status": "failed",
            "error_message": "Gateway connection timed out after 25s."
        }

        # 1. First attempt times out -> 504 Gateway Timeout
        res1 = client.post("/api/v1/bookings", json=payload, headers=headers)
        assert res1.status_code == 504

        # 2. Second attempt with identical key -> 504 Gateway Timeout without calling provider again
        res2 = client.post("/api/v1/bookings", json=payload, headers=headers)
        assert res2.status_code == 504
        assert "uncertain" in res2.text.lower()
        assert "prohibited" in res2.text.lower()

        # Adapter should only have been called once on the initial request
        assert m_order.call_count == 1


# ===========================================================================
# 7. Final Hardening Tests: Ambiguous Provider Outcomes & Multi-Worker Intent Locks
# ===========================================================================

def test_ambiguous_provider_connection_reset_locked_as_uncertain(client, db_session):
    """
    Connection reset during order creation is treated as an ambiguous outcome.
    Both IdempotencyRecord and BookingIntentReservation MUST be locked as 'uncertain',
    and automatic retry via same or different key MUST be blocked with 504.
    """
    token, headers = get_auth_token(client, "reset_ambig@travelmate.ai")
    headers["Idempotency-Key"] = "test-key-reset-alpha"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_connection_reset_test")

    payload = make_booking_payload(offer.id)

    # 1. Connection reset causes HTTP 504
    res1 = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res1.status_code == 504
    assert "uncertain" in res1.text.lower()
    assert "prohibited" in res1.text.lower()

    # 2. Database verification: both record and reservation are persisted as 'uncertain'
    user = db_session.query(User).filter(User.email == "reset_ambig@travelmate.ai").first()
    rec = db_session.query(IdempotencyRecord).filter(
        IdempotencyRecord.user_id == user.id,
        IdempotencyRecord.idempotency_key == "test-key-reset-alpha"
    ).first()
    assert rec is not None
    assert rec.status == "uncertain"

    resv = db_session.query(BookingIntentReservation).filter(
        BookingIntentReservation.user_id == user.id,
        BookingIntentReservation.flight_offer_id == offer.id
    ).first()
    assert resv is not None
    assert resv.status == "uncertain"

    # 3. Retry with a DIFFERENT client idempotency key is ALSO blocked with 504
    headers2 = {"Authorization": headers["Authorization"], "Idempotency-Key": "test-key-reset-beta"}
    res2 = client.post("/api/v1/bookings", json=payload, headers=headers2)
    assert res2.status_code == 504
    assert "uncertain" in res2.text.lower()


def test_ambiguous_provider_http_500_502_503_locked_as_uncertain(client, db_session):
    """
    HTTP 500, 502, 503 from provider must be treated as ambiguous outcomes and locked as 'uncertain'.
    """
    token, headers = get_auth_token(client, "server_err_ambig@travelmate.ai")
    headers["Idempotency-Key"] = "test-key-502-alpha"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_server_502_test")

    payload = make_booking_payload(offer.id)

    res = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res.status_code == 504
    assert "uncertain" in res.text.lower()

    user = db_session.query(User).filter(User.email == "server_err_ambig@travelmate.ai").first()
    resv = db_session.query(BookingIntentReservation).filter(
        BookingIntentReservation.user_id == user.id,
        BookingIntentReservation.flight_offer_id == offer.id
    ).first()
    assert resv is not None
    assert resv.status == "uncertain"


def test_definitive_pre_request_failure_allows_safe_retry(client, db_session):
    """
    Definitive rejections (e.g. simulated definitive failure) mark status as 'failed',
    allowing a clean subsequent retry.
    """
    token, headers = get_auth_token(client, "def_fail_user@travelmate.ai")
    headers["Idempotency-Key"] = "test-key-def-fail"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_fail_order_test")

    payload = make_booking_payload(offer.id)

    # 1. Definitive failure returns 502 Bad Gateway
    res1 = client.post("/api/v1/bookings", json=payload, headers=headers)
    assert res1.status_code == 502

    # 2. Database verification: status is 'failed', not 'uncertain'
    user = db_session.query(User).filter(User.email == "def_fail_user@travelmate.ai").first()
    rec = db_session.query(IdempotencyRecord).filter(
        IdempotencyRecord.user_id == user.id,
        IdempotencyRecord.idempotency_key == "test-key-def-fail"
    ).first()
    assert rec is not None
    assert rec.status == "failed"


def test_simultaneous_requests_different_idempotency_keys_intent_lock(client, db_session):
    """
    Two application workers handling requests with DIFFERENT idempotency keys for the SAME
    user, flight offer, and passenger intent are serialized by the BookingIntentReservation lock.
    The second worker is stopped with HTTP 409 Conflict.
    """
    token, headers1 = get_auth_token(client, "concurrent_workers@travelmate.ai")
    headers1["Idempotency-Key"] = "worker1-key-aaa"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_concur_1")

    payload = make_booking_payload(offer.id)

    # Simulate Worker 1 holding the intent reservation in 'processing' state
    user = db_session.query(User).filter(User.email == "concurrent_workers@travelmate.ai").first()
    pax_tokens = sorted([f"rohan:verma:1993-07-21"])
    pax_hash = hashlib.sha256("|".join(pax_tokens).encode("utf-8")).hexdigest()
    intent_key = f"{user.id}_{offer.id}_{pax_hash}"

    worker1_resv = BookingIntentReservation(
        user_id=user.id,
        flight_offer_id=offer.id,
        passenger_hash=pax_hash,
        intent_key=intent_key,
        idempotency_key="worker1-key-aaa",
        status="processing"
    )
    db_session.add(worker1_resv)
    db_session.commit()

    # Worker 2 arrives with a DIFFERENT idempotency key for the identical booking intent
    headers2 = {"Authorization": headers1["Authorization"], "Idempotency-Key": "worker2-key-bbb"}
    res = client.post("/api/v1/bookings", json=payload, headers=headers2)

    # Worker 2 MUST be stopped with HTTP 409 Conflict
    assert res.status_code == 409
    assert "booking_in_progress" in res.json()["detail"]["error_code"]
    assert "currently processing" in res.text.lower()


def test_different_passengers_same_flight_independent(client, db_session):
    """
    Legitimate bookings for different passengers on the same flight offer remain completely independent.
    """
    token, headers = get_auth_token(client, "diff_pax_user@travelmate.ai")
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_diff_pax")

    # Passenger 1
    headers1 = {"Authorization": headers["Authorization"], "Idempotency-Key": "key-pax-1"}
    payload1 = make_booking_payload(offer.id, first_name="Rohan", last_name="Verma")
    res1 = client.post("/api/v1/bookings", json=payload1, headers=headers1)
    assert res1.status_code == 201

    # Passenger 2 on the same flight
    headers2 = {"Authorization": headers["Authorization"], "Idempotency-Key": "key-pax-2"}
    payload2 = make_booking_payload(offer.id, first_name="Priya", last_name="Sharma")
    res2 = client.post("/api/v1/bookings", json=payload2, headers=headers2)
    assert res2.status_code == 201

    assert res1.json()["id"] != res2.json()["id"]


def test_different_flights_same_passenger_independent(client, db_session):
    """
    Legitimate bookings for the same passenger across different flight offers remain completely independent.
    """
    token, headers = get_auth_token(client, "diff_flt_user@travelmate.ai")
    offer1 = create_test_offer(client, db_session, provider_offer_id="mock_off_diff_flt_1")
    offer2 = create_test_offer(client, db_session, provider_offer_id="mock_off_diff_flt_2")

    # Flight 1
    headers1 = {"Authorization": headers["Authorization"], "Idempotency-Key": "key-flt-1"}
    payload1 = make_booking_payload(offer1.id, first_name="Rohan", last_name="Verma")
    res1 = client.post("/api/v1/bookings", json=payload1, headers=headers1)
    assert res1.status_code == 201

    # Flight 2
    headers2 = {"Authorization": headers["Authorization"], "Idempotency-Key": "key-flt-2"}
    payload2 = make_booking_payload(offer2.id, first_name="Rohan", last_name="Verma")
    res2 = client.post("/api/v1/bookings", json=payload2, headers=headers2)
    assert res2.status_code == 201

    assert res1.json()["id"] != res2.json()["id"]


def test_crash_window_preserves_processing_and_blocks_blind_retry(client, db_session):
    """
    If the application crashes during order creation (leaving status='processing' in the database),
    any subsequent retry must be blocked with HTTP 409 without calling the provider again.
    """
    token, headers = get_auth_token(client, "crash_window_user@travelmate.ai")
    headers["Idempotency-Key"] = "crash-sim-key"
    offer = create_test_offer(client, db_session, provider_offer_id="mock_off_crash_sim")

    payload = make_booking_payload(offer.id)

    # Pre-seed stranded intent reservation in 'processing' status
    user = db_session.query(User).filter(User.email == "crash_window_user@travelmate.ai").first()
    pax_tokens = sorted([f"rohan:verma:1993-07-21"])
    pax_hash = hashlib.sha256("|".join(pax_tokens).encode("utf-8")).hexdigest()
    intent_key = f"{user.id}_{offer.id}_{pax_hash}"

    stranded_resv = BookingIntentReservation(
        user_id=user.id,
        flight_offer_id=offer.id,
        passenger_hash=pax_hash,
        intent_key=intent_key,
        idempotency_key="crash-sim-key",
        status="processing"
    )
    db_session.add(stranded_resv)
    db_session.commit()

    with patch.object(MockFlightProviderAdapter, "create_order", new_callable=AsyncMock) as m_order:
        res = client.post("/api/v1/bookings", json=payload, headers=headers)
        assert res.status_code == 409
        assert "currently processing" in res.text.lower()
        # Verify provider create_order was NOT called
        assert m_order.call_count == 0

