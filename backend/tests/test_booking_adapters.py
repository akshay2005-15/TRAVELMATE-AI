"""
Automated Pytest Suite for Provider Adapter Revalidation and Order Creation.
Validates Phase 4, Step 3:
- DuffelFlightProviderAdapter: revalidate_offer & create_order (mocked network calls)
- MockFlightProviderAdapter: revalidate_offer & create_order (deterministic simulation)
- Strict compliance with Condition 2 (simulation transparency & isolation)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from app.adapters.duffel_adapter import DuffelFlightProviderAdapter
from app.adapters.mock_adapter import MockFlightProviderAdapter


# ===========================================================================
# 1. DUFFEL ADAPTER REVALIDATION TESTS (MOCKED HTTP)
# ===========================================================================

@pytest.mark.anyio
async def test_duffel_revalidate_offer_success_same_price():
    """
    Test Duffel revalidation when offer is valid and price is unchanged.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")
    assert adapter.data_source_type == "duffel_sandbox"

    future_exp = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    mock_payload = {
        "data": {
            "id": "off_0000AjX9Test1",
            "total_amount": "450.00",
            "total_currency": "GBP",
            "expires_at": future_exp,
            "slices": []
        }
    }

    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://api.duffel.com/air/offers/off_0000AjX9Test1")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await adapter.revalidate_offer(
            provider_offer_id="off_0000AjX9Test1",
            expected_amount=450.00,
            currency="GBP"
        )

        assert result["is_valid"] is True
        assert result["price_changed"] is False
        assert result["current_amount"] == 450.00
        assert result["original_amount"] == 450.00
        assert result["currency"] == "GBP"
        assert result["data_source"] == "duffel_sandbox"
        assert result["is_simulation"] is False
        assert "valid and available" in result["message"]
        assert result["raw_offer"] is not None


@pytest.mark.anyio
async def test_duffel_revalidate_offer_price_changed():
    """
    Test Duffel revalidation when provider returns an updated higher or lower price.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")
    future_exp = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    mock_payload = {
        "data": {
            "id": "off_0000AjX9Test2",
            "total_amount": "495.50",
            "total_currency": "GBP",
            "expires_at": future_exp,
        }
    }

    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://api.duffel.com/air/offers/off_0000AjX9Test2")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await adapter.revalidate_offer(
            provider_offer_id="off_0000AjX9Test2",
            expected_amount=450.00,
            currency="GBP"
        )

        assert result["is_valid"] is True
        assert result["price_changed"] is True
        assert result["original_amount"] == 450.00
        assert result["current_amount"] == 495.50
        assert result["currency"] == "GBP"
        assert result["is_simulation"] is False
        assert "Price changed from GBP 450.00 to GBP 495.50" in result["message"]


@pytest.mark.anyio
async def test_duffel_revalidate_offer_expired():
    """
    Test Duffel revalidation when expires_at timestamp is in the past.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")
    past_exp = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

    mock_payload = {
        "data": {
            "id": "off_0000AjX9Expired",
            "total_amount": "450.00",
            "total_currency": "GBP",
            "expires_at": past_exp,
        }
    }

    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://api.duffel.com/air/offers/off_0000AjX9Expired")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await adapter.revalidate_offer(
            provider_offer_id="off_0000AjX9Expired",
            expected_amount=450.00,
            currency="GBP"
        )

        assert result["is_valid"] is False
        assert result["is_simulation"] is False
        assert "expired" in result["message"].lower()


@pytest.mark.anyio
async def test_duffel_revalidate_offer_404_not_found():
    """
    Test Duffel revalidation when API returns 404 (offer expired or discarded by airline).
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")

    mock_response = httpx.Response(
        status_code=404,
        json={"errors": [{"message": "Offer no longer available", "code": "offer_gone"}]},
        request=httpx.Request("GET", "https://api.duffel.com/air/offers/off_gone")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await adapter.revalidate_offer(
            provider_offer_id="off_gone",
            expected_amount=500.00,
            currency="GBP"
        )

        assert result["is_valid"] is False
        assert "no longer available" in result["message"]
        assert result["raw_offer"] is None


@pytest.mark.anyio
async def test_duffel_revalidate_unconfigured():
    """
    Test Duffel revalidation when adapter has no valid API token.
    """
    adapter = DuffelFlightProviderAdapter(api_token="")
    result = await adapter.revalidate_offer("off_test", 100.0, "GBP")

    assert result["is_valid"] is False
    assert "not configured" in result["message"]


# ===========================================================================
# 2. DUFFEL ADAPTER ORDER CREATION TESTS (MOCKED HTTP)
# ===========================================================================

@pytest.mark.anyio
async def test_duffel_create_order_success():
    """
    Test Duffel sandbox order creation when API responds with HTTP 201 Created.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")

    mock_order_data = {
        "id": "ord_0000AjX9Order123",
        "booking_reference": "G4HK8P",
        "total_amount": "450.00",
        "total_currency": "GBP",
        "slices": [],
        "synced_at": datetime.now(timezone.utc).isoformat()
    }

    mock_response = httpx.Response(
        status_code=201,
        json={"data": mock_order_data},
        request=httpx.Request("POST", "https://api.duffel.com/air/orders")
    )

    passengers = [
        {
            "first_name": "Rohan",
            "last_name": "Sharma",
            "date_of_birth": "1994-05-12",
            "gender": "male",
            "title": "mr"
        }
    ]
    contact = {"email": "rohan.sharma@example.com", "phone": "+919876543210"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await adapter.create_order(
            provider_offer_id="off_0000AjX9Test1",
            passengers=passengers,
            contact=contact,
            total_amount=450.00,
            currency="GBP"
        )

        assert result["success"] is True
        assert result["provider_booking_id"] == "ord_0000AjX9Order123"
        assert result["booking_reference"] == "G4HK8P"
        assert result["status"] == "confirmed"
        assert result["total_amount"] == 450.00
        assert result["currency"] == "GBP"
        assert result["data_source"] == "duffel_sandbox"
        assert result["is_simulation"] is False
        assert result["error_message"] is None

        # Verify outgoing request payload
        called_payload = mock_post.call_args.kwargs["json"]["data"]
        assert called_payload["selected_offers"] == ["off_0000AjX9Test1"]
        assert len(called_payload["passengers"]) == 1
        assert called_payload["passengers"][0]["given_name"] == "Rohan"
        assert called_payload["passengers"][0]["family_name"] == "Sharma"
        assert called_payload["passengers"][0]["gender"] == "m"
        assert called_payload["payments"][0]["type"] == "balance"
        assert called_payload["payments"][0]["amount"] == "450.00"


@pytest.mark.anyio
async def test_duffel_create_order_api_error_400():
    """
    Test Duffel sandbox order creation when API returns 400 Bad Request.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")

    mock_response = httpx.Response(
        status_code=400,
        headers={"content-type": "application/json"},
        json={"errors": [{"message": "The offer has expired and can no longer be booked", "code": "offer_expired"}]},
        request=httpx.Request("POST", "https://api.duffel.com/air/orders")
    )

    passengers = [{"first_name": "Rohan", "last_name": "Sharma", "date_of_birth": "1994-05-12", "gender": "male"}]
    contact = {"email": "rohan@example.com", "phone": "+919876543210"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await adapter.create_order(
            provider_offer_id="off_expired",
            passengers=passengers,
            contact=contact,
            total_amount=450.00,
            currency="GBP"
        )

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["provider_booking_id"] == ""
        assert result["booking_reference"] is None
        assert "offer has expired" in result["error_message"]
        assert result["is_simulation"] is False


@pytest.mark.anyio
async def test_duffel_create_order_network_exception():
    """
    Test Duffel sandbox order creation when a network/transport exception occurs.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectTimeout("Connection timed out")):
        result = await adapter.create_order(
            provider_offer_id="off_test",
            passengers=[{"first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01", "gender": "male"}],
            contact={"email": "a@b.com", "phone": "+919876543210"},
            total_amount=100.0,
            currency="GBP"
        )

        assert result["success"] is False
        assert result["status"] == "failed"
        assert "timed out" in result["error_message"].lower()


# ===========================================================================
# 3. MOCK ADAPTER REVALIDATION & ORDER CREATION TESTS
# ===========================================================================

@pytest.mark.anyio
async def test_mock_adapter_revalidate_standard():
    """
    Test Mock adapter standard offer revalidation.
    """
    adapter = MockFlightProviderAdapter()
    assert adapter.provider_name == "mock"
    assert adapter.data_source_type == "mock_simulation"

    result = await adapter.revalidate_offer(
        provider_offer_id="mock_off_abc123456",
        expected_amount=5400.0,
        currency="INR"
    )

    assert result["is_valid"] is True
    assert result["price_changed"] is False
    assert result["current_amount"] == 5400.0
    assert result["original_amount"] == 5400.0
    assert result["currency"] == "INR"
    assert result["data_source"] == "mock_simulation"
    assert result["is_simulation"] is True
    assert "Simulated" in result["message"]


@pytest.mark.anyio
async def test_mock_adapter_revalidate_price_changed_flag():
    """
    Test Mock adapter offer revalidation with price_changed simulation flag.
    """
    adapter = MockFlightProviderAdapter()

    result = await adapter.revalidate_offer(
        provider_offer_id="mock_off_abc_price_changed",
        expected_amount=5400.0,
        currency="INR"
    )

    assert result["is_valid"] is True
    assert result["price_changed"] is True
    assert result["original_amount"] == 5400.0
    assert result["current_amount"] == 5900.0  # +500 simulation increase
    assert result["currency"] == "INR"
    assert result["is_simulation"] is True
    assert "Price changed" in result["message"]


@pytest.mark.anyio
async def test_mock_adapter_revalidate_expired_flag():
    """
    Test Mock adapter offer revalidation with expired simulation flag.
    """
    adapter = MockFlightProviderAdapter()

    result = await adapter.revalidate_offer(
        provider_offer_id="mock_off_abc_expired",
        expected_amount=5400.0,
        currency="INR"
    )

    assert result["is_valid"] is False
    assert result["is_simulation"] is True
    assert result["data_source"] == "mock_simulation"
    assert "expired" in result["message"].lower()


@pytest.mark.anyio
async def test_mock_adapter_revalidate_unavailable_flag():
    """
    Test Mock adapter offer revalidation with unavailable simulation flag.
    """
    adapter = MockFlightProviderAdapter()

    result = await adapter.revalidate_offer(
        provider_offer_id="mock_off_abc_unavailable",
        expected_amount=5400.0,
        currency="INR"
    )

    assert result["is_valid"] is False
    assert result["is_simulation"] is True
    assert "no longer available" in result["message"].lower()


@pytest.mark.anyio
async def test_mock_adapter_create_order_success():
    """
    Test Mock adapter deterministic simulated order creation.
    """
    adapter = MockFlightProviderAdapter()

    passengers = [
        {
            "first_name": "Priya",
            "last_name": "Nair",
            "date_of_birth": "1996-08-20",
            "gender": "female",
            "title": "ms"
        }
    ]
    contact = {"email": "priya.nair@example.com", "phone": "+919876543210"}

    result = await adapter.create_order(
        provider_offer_id="mock_off_test_6e",
        passengers=passengers,
        contact=contact,
        total_amount=5400.0,
        currency="INR"
    )

    assert result["success"] is True
    assert result["status"] == "confirmed"
    assert result["provider_booking_id"].startswith("mock_ord_")
    assert result["booking_reference"].startswith("MOCK-")
    assert result["total_amount"] == 5400.0
    assert result["currency"] == "INR"
    assert result["data_source"] == "mock_simulation"
    assert result["is_simulation"] is True
    assert result["error_message"] is None
    assert result["raw_order"]["is_simulation"] is True


@pytest.mark.anyio
async def test_mock_adapter_create_order_fail_flag():
    """
    Test Mock adapter simulated order creation failure.
    """
    adapter = MockFlightProviderAdapter()

    passengers = [{"first_name": "Priya", "last_name": "Nair", "date_of_birth": "1996-08-20", "gender": "female"}]
    contact = {"email": "priya@example.com", "phone": "+919876543210"}

    result = await adapter.create_order(
        provider_offer_id="mock_off_fail_order_test",
        passengers=passengers,
        contact=contact,
        total_amount=5400.0,
        currency="INR"
    )

    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["provider_booking_id"] == ""
    assert result["booking_reference"] is None
    assert result["is_simulation"] is True
    assert "Simulated provider booking failed" in result["error_message"]


@pytest.mark.anyio
async def test_mock_adapter_deterministic_booking_reference():
    """
    Test that Mock adapter produces deterministic references for identical bookings
    and unique references for differing bookings.
    """
    adapter = MockFlightProviderAdapter()

    pax1 = [{"first_name": "Amit", "last_name": "Patel", "date_of_birth": "1990-01-01", "gender": "male"}]
    pax2 = [{"first_name": "Sunita", "last_name": "Patel", "date_of_birth": "1992-02-02", "gender": "female"}]
    pax3 = [{"first_name": "Vikram", "last_name": "Singh", "date_of_birth": "1988-03-03", "gender": "male"}]

    res1 = await adapter.create_order("mock_off_1", pax1, {"email": "amit@test.com"}, 5000.0, "INR")
    res1_repeat = await adapter.create_order("mock_off_1", pax1, {"email": "amit@test.com"}, 5000.0, "INR")
    res2 = await adapter.create_order("mock_off_1", pax3, {"email": "vikram@test.com"}, 5000.0, "INR")

    # Identical input produces identical reference
    assert res1["booking_reference"] == res1_repeat["booking_reference"]
    assert res1["provider_booking_id"] == res1_repeat["provider_booking_id"]

    # Different passenger produces different reference
    assert res1["booking_reference"] != res2["booking_reference"]


@pytest.mark.anyio
async def test_duffel_revalidate_500_server_error():
    """
    Test Duffel revalidation when API returns HTTP 500 Internal Server Error.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_secret_token_123")

    mock_response = httpx.Response(
        status_code=500,
        text="Internal Server Error",
        request=httpx.Request("GET", "https://api.duffel.com/air/offers/off_500")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await adapter.revalidate_offer("off_500", 400.0, "GBP")

        assert result["is_valid"] is False
        assert result["is_simulation"] is False
        assert "no longer available" in result["message"].lower() or "expired" in result["message"].lower()


@pytest.mark.anyio
async def test_duffel_create_order_unconfigured():
    """
    Test Duffel order creation when adapter has no token configured.
    """
    adapter = DuffelFlightProviderAdapter(api_token="")
    result = await adapter.create_order(
        provider_offer_id="off_test",
        passengers=[{"first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01", "gender": "male"}],
        contact={"email": "a@b.com", "phone": "+919876543210"},
        total_amount=100.0,
        currency="GBP"
    )

    assert result["success"] is False
    assert result["status"] == "failed"
    assert "not configured" in result["error_message"].lower()


@pytest.mark.anyio
async def test_condition_2_adapter_simulation_transparency():
    """
    Compliance test for Condition 2:
    - Mock adapter must strictly tag is_simulation=True and data_source='mock_simulation'.
    - Duffel adapter must strictly tag is_simulation=False and data_source='duffel_sandbox'.
    """
    mock_adapter = MockFlightProviderAdapter()
    duffel_adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_token_12345678")

    # Mock adapter guarantees
    mock_reval = await mock_adapter.revalidate_offer("mock_off_123", 5000.0, "INR")
    assert mock_reval["is_simulation"] is True
    assert mock_reval["data_source"] == "mock_simulation"

    mock_order = await mock_adapter.create_order(
        "mock_off_123",
        [{"first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01", "gender": "male"}],
        {"email": "a@b.com", "phone": "+919876543210"},
        5000.0,
        "INR"
    )
    assert mock_order["is_simulation"] is True
    assert mock_order["data_source"] == "mock_simulation"

    # Duffel adapter guarantees
    future_exp = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    mock_duffel_get = httpx.Response(
        status_code=200,
        json={"data": {"id": "off_live_123", "total_amount": "350.00", "total_currency": "GBP", "expires_at": future_exp}},
        request=httpx.Request("GET", "https://api.duffel.com/air/offers/off_live_123")
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_duffel_get
        duffel_reval = await duffel_adapter.revalidate_offer("off_live_123", 350.0, "GBP")
        assert duffel_reval["is_simulation"] is False
        assert duffel_reval["data_source"] == "duffel_sandbox"

