"""
Automated Test Suite for Phase 3 Step 4: Conversational AI Engine & LangGraph State Machine.
Tests intent extraction, slot accumulation, missing field detection, context retention,
rule-based fallback, tool execution, and error handling.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from app.ai import run_flight_agent, rule_based_extract, parse_relative_date, format_flight_offers_summary
from app.ai.state import AgentState
from app.ai.extractor import extract_slots_and_intent
from app.adapters.airports import resolve_iata


# ===========================================================================
# 1. Intent Extraction & Normalization Tests
# ===========================================================================

@pytest.mark.anyio
async def test_intent_greeting():
    """Verify greetings are classified and assistant responds with welcome message."""
    state = await run_flight_agent("Hello TRAVELMATE", force_fallback=True)
    assert state["intent"] == "greeting"
    assert state["search_ready"] is False
    assert "TRAVELMATE AI" in state["assistant_reply"]
    assert "flight" in state["assistant_reply"].lower()


@pytest.mark.anyio
async def test_intent_out_of_scope():
    """Verify non-flight requests (hotels, cabs) are classified as out of scope."""
    state = await run_flight_agent("Can you book a hotel room in Paris for 3 nights?", force_fallback=True)
    assert state["intent"] == "out_of_scope"
    assert state["search_ready"] is False
    assert "flights" in state["assistant_reply"].lower()
    assert "hotel" in state["assistant_reply"].lower()


@pytest.mark.anyio
async def test_intent_search_flights():
    """Verify flight search requests are identified and criteria extracted."""
    future_date = (date.today() + timedelta(days=5)).isoformat()
    state = await run_flight_agent(f"Find flights from Bangalore to Delhi on {future_date}", force_fallback=True)
    assert state["intent"] == "search_flights"
    assert state["slots"].get("origin") == "BLR"
    assert state["slots"].get("destination") == "DEL"
    assert state["slots"].get("departure_date") == future_date


# ===========================================================================
# 2. Airport and City IATA Resolution Tests
# ===========================================================================

def test_resolve_iata_codes_and_cities():
    """Verify IATA resolution handles raw codes, city names, and common aliases."""
    assert resolve_iata("BLR") == "BLR"
    assert resolve_iata("blr") == "BLR"
    assert resolve_iata("Bengaluru") == "BLR"
    assert resolve_iata("Bangalore") == "BLR"
    assert resolve_iata("Delhi") == "DEL"
    assert resolve_iata("New Delhi") == "DEL"
    assert resolve_iata("Mumbai") == "BOM"
    assert resolve_iata("Bombay") == "BOM"
    assert resolve_iata("London") == "LHR"
    assert resolve_iata("Dubai") == "DXB"
    assert resolve_iata("NonExistentCityXYZ") is None


# ===========================================================================
# 3. Date Parsing & Relative Date Tests
# ===========================================================================

def test_parse_relative_dates():
    """Verify relative date expressions are calculated based on reference date."""
    ref = date(2026, 11, 10)  # Tuesday
    assert parse_relative_date("tomorrow", reference_date=ref) == "2026-11-11"
    assert parse_relative_date("day after tomorrow", reference_date=ref) == "2026-11-12"
    assert parse_relative_date("next week", reference_date=ref) == "2026-11-17"
    assert parse_relative_date("2026-12-25", reference_date=ref) == "2026-12-25"

    # Next Friday from Tuesday (10th) should be Friday the 13th
    next_fri = parse_relative_date("next friday", reference_date=ref)
    assert next_fri == "2026-11-13"


# ===========================================================================
# 4. Slot Filling & Missing Field Detection Tests
# ===========================================================================

@pytest.mark.anyio
async def test_missing_mandatory_fields_detection():
    """Verify agent detects when origin, destination, or date is missing."""
    # Only destination provided
    state1 = await run_flight_agent("I want to fly to Delhi", force_fallback=True)
    assert state1["search_ready"] is False
    assert "origin" in state1["missing_fields"]
    assert "departure_date" in state1["missing_fields"]
    assert state1["slots"].get("destination") == "DEL"
    assert "departing from" in state1["assistant_reply"].lower()

    # Origin and destination provided, missing date
    state2 = await run_flight_agent("Flights from BLR to DEL", force_fallback=True)
    assert state2["search_ready"] is False
    assert state2["missing_fields"] == ["departure_date"]
    assert "date" in state2["assistant_reply"].lower()


# ===========================================================================
# 5. Multi-Turn Conversation Context Retention Tests
# ===========================================================================

@pytest.mark.anyio
async def test_multi_turn_context_retention():
    """
    Test a 3-turn conversation where details are supplied incrementally.
    Verifies that previously supplied slots are remembered across turns.
    """
    # Turn 1: User mentions destination
    turn1 = await run_flight_agent("I want to go to Delhi", force_fallback=True)
    assert turn1["slots"].get("destination") == "DEL"
    assert "origin" in turn1["missing_fields"]

    # Turn 2: User provides origin
    turn2 = await run_flight_agent(
        "Departing from Bangalore",
        current_slots=turn1["slots"],
        messages=turn1["messages"],
        force_fallback=True
    )
    # Origin added, destination remembered!
    assert turn2["slots"].get("origin") == "BLR"
    assert turn2["slots"].get("destination") == "DEL"
    assert turn2["missing_fields"] == ["departure_date"]

    # Turn 3: User provides departure date
    turn3 = await run_flight_agent(
        "Tomorrow",
        current_slots=turn2["slots"],
        messages=turn2["messages"],
        force_fallback=True
    )
    assert turn3["slots"].get("origin") == "BLR"
    assert turn3["slots"].get("destination") == "DEL"
    assert turn3["slots"].get("departure_date") is not None
    assert turn3["search_ready"] is True
    assert turn3["flight_search_results"] is not None
    assert turn3["flight_search_results"]["total_offers"] > 0


# ===========================================================================
# 6. Passenger Count and Cabin Class Extraction
# ===========================================================================

@pytest.mark.anyio
async def test_passenger_and_cabin_class_extraction():
    """Verify passenger count and cabin class extraction."""
    future_date = (date.today() + timedelta(days=10)).isoformat()
    msg = f"Find 2 tickets in business class from BLR to DEL on {future_date}"
    state = await run_flight_agent(msg, force_fallback=True)

    assert state["slots"].get("passengers") == 2
    assert state["slots"].get("cabin_class") == "business"
    assert state["search_ready"] is True


# ===========================================================================
# 7. Validation Error Handling Tests
# ===========================================================================

@pytest.mark.anyio
async def test_validation_identical_origin_and_destination():
    """Verify agent catches when origin and destination are the same airport."""
    future_date = (date.today() + timedelta(days=5)).isoformat()
    state = await run_flight_agent(f"Flights from BLR to BLR on {future_date}", force_fallback=True)
    assert state["search_ready"] is False
    assert "cannot both be" in state["assistant_reply"]


@pytest.mark.anyio
async def test_validation_past_departure_date():
    """Verify agent catches past departure dates."""
    state = await run_flight_agent("Flights from BLR to DEL on 2020-01-01", force_fallback=True)
    assert state["search_ready"] is False
    assert "past" in state["assistant_reply"].lower()


# ===========================================================================
# 8. Grounded Formatter & Provider Labeling Tests (Condition 2)
# ===========================================================================

def test_grounded_response_formatter_mock_simulation():
    """Verify formatter displays clear simulation label for mock offers."""
    mock_results = {
        "origin_iata": "BLR",
        "destination_iata": "DEL",
        "departure_date": "2026-11-20",
        "data_source": "mock_simulation",
        "is_simulation": True,
        "offers": [
            {
                "airline_name": "Air India",
                "flight_number": "AI 502",
                "total_amount": "5400.00",
                "currency": "INR",
                "departure_time": "06:00",
                "arrival_time": "08:45",
                "duration_minutes": 165,
                "stops": 0,
                "cabin_class": "economy"
            }
        ]
    }
    reply = format_flight_offers_summary(mock_results)
    assert "SIMULATION / MOCK OFFER" in reply
    assert "Air India AI 502" in reply
    assert "5,400.00" in reply
    assert "Lowest Fare" in reply


def test_grounded_response_formatter_duffel_sandbox():
    """Verify formatter displays clear duffel sandbox label for duffel offers."""
    duffel_results = {
        "origin_iata": "LHR",
        "destination_iata": "JFK",
        "departure_date": "2026-12-01",
        "data_source": "duffel_sandbox",
        "is_simulation": False,
        "offers": [
            {
                "airline_name": "British Airways",
                "flight_number": "BA 117",
                "total_amount": "450.00",
                "currency": "GBP",
                "departure_time": "10:00",
                "arrival_time": "13:30",
                "duration_minutes": 450,
                "stops": 0,
                "cabin_class": "economy"
            }
        ]
    }
    reply = format_flight_offers_summary(duffel_results)
    assert "DUFFEL TEST SANDBOX" in reply
    assert "British Airways BA 117" in reply
    assert "GBP 450.00" in reply


# ===========================================================================
# 9. Gemini Client Fallback Resiliency Test
# ===========================================================================

@pytest.mark.anyio
async def test_gemini_exception_triggers_safe_fallback():
    """Verify that if Gemini client throws an exception, rule-based fallback succeeds."""
    with patch("google.genai.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = RuntimeError("Simulated Gemini API rate limit or outage")
        mock_client.return_value = mock_instance

        with patch("app.core.config.settings.GEMINI_API_KEY", "AQ.simulated_valid_key_string"):
            intent, slots = await extract_slots_and_intent(
                "Find flights from Mumbai to Delhi tomorrow",
                current_slots={},
                force_fallback=False
            )
            assert intent == "search_flights"
            assert slots.get("origin") == "BOM"
            assert slots.get("destination") == "DEL"
            assert slots.get("departure_date") is not None

