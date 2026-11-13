"""
Automated Pytest Suite for Flight Search, Provider Adapters, and Normalization.
Validates compliance with SRS FR-022 to FR-027 and User Conditions 1, 2, 3.
"""

from datetime import date, timedelta
import pytest
from app.adapters.airports import resolve_iata, search_airports
from app.adapters.duffel_adapter import DuffelFlightProviderAdapter
from app.schemas.flight import FlightSearchRequest


def test_airport_search_and_autocomplete(client):
    # Search by IATA code
    res1 = client.get("/api/v1/flights/airports?q=BLR")
    assert res1.status_code == 200
    airports = res1.json()
    assert len(airports) >= 1
    assert airports[0]["iata_code"] == "BLR"
    assert "Bengaluru" in airports[0]["city_name"]

    # Search by City Name
    res2 = client.get("/api/v1/flights/airports?q=delhi")
    assert res2.status_code == 200
    delhi_matches = res2.json()
    assert any(a["iata_code"] == "DEL" for a in delhi_matches)


def test_iata_resolver():
    assert resolve_iata("Bengaluru") == "BLR"
    assert resolve_iata("delhi") == "DEL"
    assert resolve_iata("London") in ["LHR", "LGW"]
    assert resolve_iata("JFK") == "JFK"
    assert resolve_iata("UnknownFakeCity") is None


def test_flight_search_mock_success(client):
    # Departure date 7 days in the future
    future_date = (date.today() + timedelta(days=7)).isoformat()
    payload = {
        "origin": "BLR",
        "destination": "DEL",
        "departure_date": future_date,
        "passengers": 1,
        "cabin_class": "economy",
        "force_provider": "mock"
    }

    response = client.post("/api/v1/flights/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["origin_iata"] == "BLR"
    assert data["destination_iata"] == "DEL"
    assert data["total_offers"] >= 3
    assert data["provider_used"] == "mock"
    assert data["data_source"] == "mock_simulation"
    assert data["is_simulation"] is True

    # Check offer structure
    first_offer = data["offers"][0]
    assert "airline_name" in first_offer
    assert "flight_number" in first_offer
    assert first_offer["origin_iata"] == "BLR"
    assert first_offer["destination_iata"] == "DEL"
    assert first_offer["total_amount"] > 0
    assert first_offer["currency"] == "INR"
    assert first_offer["duration_minutes"] > 0
    assert first_offer["is_simulation"] is True


def test_condition_2_simulation_transparency(client):
    """
    User Condition 2: Clearly distinguish mock flight data, sandbox bookings, and real confirmed bookings.
    Never display simulated flights as real.
    """
    future_date = (date.today() + timedelta(days=5)).isoformat()
    payload = {
        "origin": "BOM",
        "destination": "DEL",
        "departure_date": future_date,
        "passengers": 2,
        "cabin_class": "economy",
        "force_provider": "mock"
    }
    response = client.post("/api/v1/flights/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Verify top-level transparency flags
    assert data["is_simulation"] is True
    assert data["data_source"] == "mock_simulation"

    # Verify every individual offer contains explicit simulation tags
    for offer in data["offers"]:
        assert offer["is_simulation"] is True
        assert offer["data_source"] == "mock_simulation"


def test_flight_search_validation_errors(client):
    future_date = (date.today() + timedelta(days=3)).isoformat()

    # Error 1: Same origin and destination (uppercase)
    res1 = client.post("/api/v1/flights/search", json={
        "origin": "BLR",
        "destination": "BLR",
        "departure_date": future_date,
        "passengers": 1
    })
    assert res1.status_code == 422
    assert "Origin and destination airports must be different" in str(res1.json())

    # Error 1b: Same origin and destination (case-insensitive "blr" vs "BLR")
    res1b = client.post("/api/v1/flights/search", json={
        "origin": "blr",
        "destination": "BLR",
        "departure_date": future_date,
        "passengers": 1
    })
    assert res1b.status_code == 422
    assert "Origin and destination airports must be different" in str(res1b.json())

    # Error 2: Past departure date
    past_date = (date.today() - timedelta(days=1)).isoformat()
    res2 = client.post("/api/v1/flights/search", json={
        "origin": "BLR",
        "destination": "DEL",
        "departure_date": past_date,
        "passengers": 1
    })
    assert res2.status_code == 422
    assert "past" in str(res2.json()).lower()

    # Error 3: Passenger count out of bounds (> 9)
    res3 = client.post("/api/v1/flights/search", json={
        "origin": "BLR",
        "destination": "DEL",
        "departure_date": future_date,
        "passengers": 15
    })
    assert res3.status_code == 422

    # Error 4: Return date before departure date
    earlier_return = (date.today() + timedelta(days=2)).isoformat()
    res4 = client.post("/api/v1/flights/search", json={
        "origin": "BLR",
        "destination": "DEL",
        "departure_date": future_date,
        "return_date": earlier_return,
        "passengers": 1
    })
    assert res4.status_code == 422
    assert "Return date cannot be earlier" in str(res4.json())


def test_flight_search_persistence_and_retrieval(client):
    future_date = (date.today() + timedelta(days=10)).isoformat()
    search_payload = {
        "origin": "LHR",
        "destination": "JFK",
        "departure_date": future_date,
        "passengers": 1,
        "cabin_class": "economy",
        "force_provider": "mock"
    }

    create_res = client.post("/api/v1/flights/search", json=search_payload)
    assert create_res.status_code == 200
    created_data = create_res.json()
    search_id = created_data["search_id"]
    assert search_id > 0

    # Retrieve by search ID
    get_res = client.get(f"/api/v1/flights/searches/{search_id}")
    assert get_res.status_code == 200
    retrieved_data = get_res.json()
    assert retrieved_data["search_id"] == search_id
    assert retrieved_data["origin_iata"] == "LHR"
    assert retrieved_data["destination_iata"] == "JFK"
    assert len(retrieved_data["offers"]) == len(created_data["offers"])


def test_flight_provider_status_endpoint(client):
    response = client.get("/api/v1/flights/provider-status")
    assert response.status_code == 200
    data = response.json()
    assert "configured_provider" in data
    assert "mock_fallback_enabled" in data
    assert data["mock_fallback_enabled"] is True


def test_duffel_adapter_normalization():
    """
    Unit test verifying Duffel response mapping logic.
    """
    adapter = DuffelFlightProviderAdapter(api_token="duffel_test_mock_token_12345678")
    assert adapter.data_source_type == "duffel_sandbox"

    sample_duffel_offers = [
        {
            "id": "off_0000AjX9K12345",
            "total_amount": "450.00",
            "total_currency": "GBP",
            "owner": {"name": "British Airways", "iata_code": "BA"},
            "slices": [
                {
                    "duration": "PT7H30M",
                    "segments": [
                        {
                            "origin": {"iata_code": "LHR"},
                            "destination": {"iata_code": "JFK"},
                            "departing_at": "2026-11-20T10:00:00",
                            "arriving_at": "2026-11-20T12:30:00",
                            "marketing_carrier": {"iata_code": "BA"},
                            "marketing_carrier_flight_number": "117"
                        }
                    ]
                }
            ],
            "passengers": [{"baggages": [{"type": "checked"}]}]
        }
    ]

    criteria = FlightSearchRequest(
        origin="LHR",
        destination="JFK",
        departure_date=(date.today() + timedelta(days=10)).isoformat(),
        passengers=1,
        cabin_class="economy"
    )

    normalized = adapter._normalize_duffel_offers(sample_duffel_offers, criteria)
    assert len(normalized) == 1
    item = normalized[0]
    assert item.provider_offer_id == "off_0000AjX9K12345"
    assert item.airline_name == "British Airways"
    assert item.airline_code == "BA"
    assert item.total_amount == 450.00
    assert item.currency == "GBP"
    assert item.duration_minutes == 450  # 7h 30m = 450 mins
    assert item.data_source == "duffel_sandbox"
    assert item.is_simulation is False  # Explicitly NOT simulation
