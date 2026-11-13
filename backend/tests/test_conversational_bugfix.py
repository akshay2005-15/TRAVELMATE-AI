"""
Automated Test Suite for Conversational Slot Extraction & Preference Bug Fix.
Validates:
- Explicit dates ('11 November 2026')
- Relative date offsets ('2 days later', 'in 3 days') against a fixed reference date
- Route extraction ('Bangalore to Delhi')
- Departure-time preferences ('I prefer morning flights')
- Turn-by-turn preservation of accumulated criteria
- Targeted clarification requests without redundant loops
- Flight search tool invocation upon criteria completion
- Resilient rule-based fallback when Gemini is unavailable
"""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from app.ai import (
    run_flight_agent,
    parse_date_expression,
    extract_time_preference,
    rule_based_extract,
    format_flight_offers_summary
)
from app.ai.extractor import extract_slots_and_intent


# Fixed reference date: Tuesday, 10 November 2026
FIXED_REF_DATE = date(2026, 11, 10)


# ===========================================================================
# 1. Date Expression Parsing Unit Tests
# ===========================================================================

def test_parse_explicit_month_names():
    """Verify explicit date strings with month names are correctly parsed into ISO YYYY-MM-DD."""
    assert parse_date_expression("11 November 2026", reference_date=FIXED_REF_DATE) == "2026-11-11"
    assert parse_date_expression("11th November 2026", reference_date=FIXED_REF_DATE) == "2026-11-11"
    assert parse_date_expression("November 11, 2026", reference_date=FIXED_REF_DATE) == "2026-11-11"
    assert parse_date_expression("11 Nov 2026", reference_date=FIXED_REF_DATE) == "2026-11-11"
    assert parse_date_expression("Nov 11 2026", reference_date=FIXED_REF_DATE) == "2026-11-11"
    assert parse_date_expression("25 December 2026", reference_date=FIXED_REF_DATE) == "2026-12-25"


def test_parse_relative_date_offsets():
    """Verify relative expressions ('2 days later', 'in 3 days') resolve accurately."""
    # Reference date is 2026-11-10
    assert parse_date_expression("2 days later", reference_date=FIXED_REF_DATE) == "2026-11-12"
    assert parse_date_expression("in 3 days", reference_date=FIXED_REF_DATE) == "2026-11-13"
    assert parse_date_expression("after 4 days", reference_date=FIXED_REF_DATE) == "2026-11-14"
    assert parse_date_expression("tomorrow", reference_date=FIXED_REF_DATE) == "2026-11-11"
    assert parse_date_expression("day after tomorrow", reference_date=FIXED_REF_DATE) == "2026-11-12"
    assert parse_date_expression("next week", reference_date=FIXED_REF_DATE) == "2026-11-17"


# ===========================================================================
# 2. Time of Day Preference Extraction Unit Tests
# ===========================================================================

def test_extract_departure_time_preference():
    """Verify time of day preference extraction from natural phrases."""
    assert extract_time_preference("I prefer morning flights.") == "morning"
    assert extract_time_preference("Early morning departure please") == "morning"
    assert extract_time_preference("Looking for an afternoon flight") == "afternoon"
    assert extract_time_preference("Evening flights only") == "evening"
    assert extract_time_preference("Red-eye or night flight") == "night"
    assert extract_time_preference("Flights to Delhi tomorrow") is None


# ===========================================================================
# 3. Conversational Multi-Turn Bug Fix Scenarios
# ===========================================================================

@pytest.mark.anyio
async def test_route_followed_by_date_message():
    """Verify that a route message followed by a date message retains route and captures date."""
    # Turn 1: Route
    turn1 = await run_flight_agent(
        "I want to travel from Bangalore to Delhi.",
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert turn1["slots"].get("origin") == "BLR"
    assert turn1["slots"].get("destination") == "DEL"
    assert turn1["slots"].get("departure_date") is None
    assert turn1["search_ready"] is False
    assert turn1["missing_fields"] == ["departure_date"]
    assert "date" in turn1["assistant_reply"].lower()

    # Turn 2: Explicit Date "11 November 2026"
    turn2 = await run_flight_agent(
        "11 November 2026",
        current_slots=turn1["slots"],
        messages=turn1["messages"],
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert turn2["slots"].get("origin") == "BLR"
    assert turn2["slots"].get("destination") == "DEL"
    assert turn2["slots"].get("departure_date") == "2026-11-11"
    assert turn2["search_ready"] is True
    assert turn2["flight_search_results"] is not None
    assert turn2["flight_search_results"]["total_offers"] > 0


@pytest.mark.anyio
async def test_route_followed_by_relative_offset():
    """Verify that '2 days later' resolves and triggers search when route was already provided."""
    turn1 = await run_flight_agent(
        "I want to travel from Bangalore to Delhi.",
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert turn1["slots"].get("origin") == "BLR"
    assert turn1["slots"].get("destination") == "DEL"

    turn2 = await run_flight_agent(
        "2 days later",
        current_slots=turn1["slots"],
        messages=turn1["messages"],
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert turn2["slots"].get("origin") == "BLR"
    assert turn2["slots"].get("destination") == "DEL"
    assert turn2["slots"].get("departure_date") == "2026-11-12"
    assert turn2["search_ready"] is True
    assert turn2["flight_search_results"] is not None


@pytest.mark.anyio
async def test_preference_captured_and_retained():
    """Verify that 'I prefer morning flights' captures preferred_time and preserves route/date."""
    # Case A: Preference sent before date is provided
    turn1 = await run_flight_agent(
        "I want to travel from Bangalore to Delhi.",
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    turn2 = await run_flight_agent(
        "I prefer morning flights.",
        current_slots=turn1["slots"],
        messages=turn1["messages"],
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert turn2["slots"].get("origin") == "BLR"
    assert turn2["slots"].get("destination") == "DEL"
    assert turn2["slots"].get("preferred_time") == "morning"
    assert turn2["missing_fields"] == ["departure_date"]
    assert "morning" in turn2["assistant_reply"].lower()

    # Turn 3: Date provided after preference
    turn3 = await run_flight_agent(
        "11 November 2026",
        current_slots=turn2["slots"],
        messages=turn2["messages"],
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert turn3["slots"].get("origin") == "BLR"
    assert turn3["slots"].get("destination") == "DEL"
    assert turn3["slots"].get("departure_date") == "2026-11-11"
    assert turn3["slots"].get("preferred_time") == "morning"
    assert turn3["search_ready"] is True
    assert turn3["flight_search_results"] is not None


# ===========================================================================
# 4. Exact 4-Message Sequence from User Report
# ===========================================================================

@pytest.mark.anyio
async def test_exact_user_reported_4_message_sequence():
    """
    Test the exact sequence reported by the user:
    1. 'I want to travel from Bangalore to Delhi.'
    2. '2 days later'
    3. 'I prefer morning flights.'
    4. '11 November 2026'
    """
    # Msg 1: Route
    s1 = await run_flight_agent(
        "I want to travel from Bangalore to Delhi.",
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert s1["slots"].get("origin") == "BLR"
    assert s1["slots"].get("destination") == "DEL"
    assert s1["slots"].get("departure_date") is None
    assert s1["missing_fields"] == ["departure_date"]

    # Msg 2: '2 days later'
    s2 = await run_flight_agent(
        "2 days later",
        current_slots=s1["slots"],
        messages=s1["messages"],
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert s2["slots"].get("origin") == "BLR"
    assert s2["slots"].get("destination") == "DEL"
    assert s2["slots"].get("departure_date") == "2026-11-12"
    assert s2["search_ready"] is True
    assert s2["flight_search_results"] is not None

    # Msg 3: 'I prefer morning flights.'
    s3 = await run_flight_agent(
        "I prefer morning flights.",
        current_slots=s2["slots"],
        messages=s2["messages"],
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert s3["slots"].get("origin") == "BLR"
    assert s3["slots"].get("destination") == "DEL"
    assert s3["slots"].get("departure_date") == "2026-11-12"
    assert s3["slots"].get("preferred_time") == "morning"
    assert s3["search_ready"] is True
    assert s3["flight_search_results"] is not None

    # Msg 4: '11 November 2026'
    s4 = await run_flight_agent(
        "11 November 2026",
        current_slots=s3["slots"],
        messages=s3["messages"],
        reference_date=FIXED_REF_DATE,
        force_fallback=True
    )
    assert s4["slots"].get("origin") == "BLR"
    assert s4["slots"].get("destination") == "DEL"
    assert s4["slots"].get("departure_date") == "2026-11-11"
    assert s4["slots"].get("preferred_time") == "morning"
    assert s4["search_ready"] is True
    assert s4["flight_search_results"] is not None
    assert s4["flight_search_results"]["departure_date"] == "2026-11-11"


# ===========================================================================
# 5. Fallback Resiliency and Preference Formatting
# ===========================================================================

@pytest.mark.anyio
async def test_gemini_failure_fallback_handles_date_and_preference():
    """Verify that when Gemini throws an exception, rule-based fallback extracts date and preference."""
    with patch("google.genai.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = RuntimeError("Gemini 503 high demand outage")
        mock_client.return_value = mock_instance

        with patch("app.core.config.settings.GEMINI_API_KEY", "AQ.simulated_valid_key_string"):
            intent, slots = await extract_slots_and_intent(
                "Find morning flights from Mumbai to London on 11 November 2026",
                current_slots={},
                force_fallback=False,
                reference_date=FIXED_REF_DATE
            )
            assert intent == "search_flights"
            assert slots.get("origin") == "BOM"
            assert slots.get("destination") == "LHR"
            assert slots.get("departure_date") == "2026-11-11"
            assert slots.get("preferred_time") == "morning"


def test_format_flight_offers_with_morning_preference():
    """Verify that formatted summary acknowledges morning preference without claiming false provider filtering."""
    results = {
        "origin_iata": "BLR",
        "destination_iata": "DEL",
        "departure_date": "2026-11-11",
        "data_source": "mock_simulation",
        "is_simulation": True,
        "offers": [
            {
                "airline_name": "IndiGo",
                "flight_number": "6E-2054",
                "departure_time": "2026-11-11T06:00:00+00:00",
                "arrival_time": "2026-11-11T08:45:00+00:00",
                "duration_minutes": 165,
                "stops": 0,
                "total_amount": "5400.00",
                "currency": "INR",
                "cabin_class": "economy"
            },
            {
                "airline_name": "Air India",
                "flight_number": "AI-804",
                "departure_time": "2026-11-11T20:00:00+00:00",
                "arrival_time": "2026-11-11T22:45:00+00:00",
                "duration_minutes": 165,
                "stops": 0,
                "total_amount": "4800.00",
                "currency": "INR",
                "cabin_class": "economy"
            }
        ]
    }
    summary = format_flight_offers_summary(results, preferred_time="morning")
    assert "morning" in summary.lower()
    assert "SIMULATION / MOCK OFFER" in summary
    assert "6E-2054" in summary

