"""
Automated Pytest Suite for Departure-Time Filtering and Airport Local Timezone Resolution.
Validates:
1. Airport timezone lookup (BLR -> Asia/Kolkata).
2. UTC-to-IST conversion of flight timestamps.
3. Accurate time window filtering:
   - Morning (< 12:00 PM local time).
   - Afternoon (12:00 PM - 5:00 PM local time).
   - Evening (5:00 PM - 9:00 PM local time).
   - Night (>= 9:00 PM or < 5:00 AM local time).
4. Strict removal of non-matching flights from results and assistant reply.
5. Clear notification when no matching flights exist (without hallucinating).
6. Preservation of provider/mock simulation status labels.
7. Consistent filtering in both AI state machine and API responses.
"""

from datetime import date, datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo
import pytest

from app.adapters.airports import get_airport_timezone
from app.ai.time_filter import (
    parse_local_departure_datetime,
    matches_departure_time_filter,
    filter_flight_offers_by_time,
)
from app.ai.extractor import extract_time_preference
from app.ai.graph import format_flight_offers_summary
from app.ai import run_flight_agent


# ===========================================================================
# 1. Airport Timezone Resolution & UTC-to-IST Conversion Tests
# ===========================================================================

def test_airport_timezone_lookup():
    """Verify IATA codes map to correct regional IANA timezones."""
    assert get_airport_timezone("BLR") == "Asia/Kolkata"
    assert get_airport_timezone("DEL") == "Asia/Kolkata"
    assert get_airport_timezone("BOM") == "Asia/Kolkata"
    assert get_airport_timezone("LHR") == "Europe/London"
    assert get_airport_timezone("JFK") == "America/New_York"
    assert get_airport_timezone("DXB") == "Asia/Dubai"
    assert get_airport_timezone(None) == "Asia/Kolkata"


def test_utc_to_ist_conversion():
    """
    Verify UTC departure timestamps are converted to Asia/Kolkata (+05:30)
    for BLR departures.
    """
    # 00:30 UTC -> 06:00 IST (Early morning)
    dt1 = parse_local_departure_datetime("2026-11-12T00:30:00Z", origin_iata="BLR")
    assert dt1.hour == 6
    assert dt1.minute == 0
    assert dt1.utcoffset() == timedelta(hours=5, minutes=30)

    # 06:00 UTC -> 11:30 IST (Morning before 12 PM)
    dt2 = parse_local_departure_datetime("2026-11-12T06:00:00+00:00", origin_iata="BLR")
    assert dt2.hour == 11
    assert dt2.minute == 30

    # 08:15 UTC -> 13:45 IST (Afternoon at 1:45 PM)
    dt3 = parse_local_departure_datetime("2026-11-12T08:15:00+00:00", origin_iata="BLR")
    assert dt3.hour == 13
    assert dt3.minute == 45

    # 13:00 UTC -> 18:30 IST (Evening at 6:30 PM)
    dt4 = parse_local_departure_datetime("2026-11-12T13:00:00Z", origin_iata="BLR")
    assert dt4.hour == 18
    assert dt4.minute == 30

    # 18:00 UTC -> 23:30 IST (Night at 11:30 PM)
    dt5 = parse_local_departure_datetime("2026-11-12T18:00:00+00:00", origin_iata="BLR")
    assert dt5.hour == 23
    assert dt5.minute == 30

    # Naive timestamp treated as local time
    dt6 = parse_local_departure_datetime("2026-11-12T08:30:00", origin_iata="BLR")
    assert dt6.hour == 8
    assert dt6.minute == 30


# ===========================================================================
# 2. Departure Time Window Matching Tests
# ===========================================================================

def test_morning_window_filter_before_12_pm():
    """
    Requirement 4: For 'before 12 PM', include only departures earlier than 12:00 local time.
    """
    # 06:00 IST (< 12:00) -> True
    offer_0600 = {"departure_time": "2026-11-12T00:30:00Z", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_0600, "morning") is True

    # 11:30 IST (< 12:00) -> True
    offer_1130 = {"departure_time": "2026-11-12T06:00:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_1130, "morning") is True

    # 11:59 IST (< 12:00) -> True
    offer_1159 = {"departure_time": "2026-11-12T06:29:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_1159, "morning") is True

    # Exactly 12:00 IST -> False (not earlier than 12:00)
    offer_1200 = {"departure_time": "2026-11-12T06:30:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_1200, "morning") is False

    # 13:45 IST (Afternoon) -> False
    offer_1345 = {"departure_time": "2026-11-12T08:15:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_1345, "morning") is False

    # 23:30 IST (Night) -> False
    offer_2330 = {"departure_time": "2026-11-12T18:00:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_2330, "morning") is False


def test_afternoon_and_night_window_filters():
    """Verify afternoon, evening, and night windows with UTC-to-IST conversion."""
    # 13:45 IST (08:15 UTC): Afternoon
    offer_aft = {"departure_time": "2026-11-12T08:15:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_aft, "afternoon") is True
    assert matches_departure_time_filter(offer_aft, "morning") is False
    assert matches_departure_time_filter(offer_aft, "night") is False

    # 18:30 IST (13:00 UTC): Evening
    offer_eve = {"departure_time": "2026-11-12T13:00:00Z", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_eve, "evening") is True
    assert matches_departure_time_filter(offer_eve, "afternoon") is False

    # 23:30 IST (18:00 UTC): Night
    offer_ngt = {"departure_time": "2026-11-12T18:00:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_ngt, "night") is True
    assert matches_departure_time_filter(offer_ngt, "morning") is False

    # 02:30 IST (21:00 UTC previous day): Night / Red-eye
    offer_redeye = {"departure_time": "2026-11-11T21:00:00+00:00", "origin_iata": "BLR"}
    assert matches_departure_time_filter(offer_redeye, "night") is True
    assert matches_departure_time_filter(offer_redeye, "afternoon") is False


# ===========================================================================
# 3. Preference Query Parsing Tests
# ===========================================================================

def test_extract_time_preference_queries():
    """Verify various user phrases extract the correct departure-time preference."""
    assert extract_time_preference("Show me only morning flights before 12 PM") == "morning"
    assert extract_time_preference("Show me flights before 12 PM") == "morning"
    assert extract_time_preference("flights before 12pm") == "morning"
    assert extract_time_preference("flights before noon") == "morning"
    assert extract_time_preference("I prefer morning flights") == "morning"
    assert extract_time_preference("Flights after 12 PM") == "afternoon"
    assert extract_time_preference("Looking for an afternoon departure") == "afternoon"
    assert extract_time_preference("Evening flights only") == "evening"
    assert extract_time_preference("Late night or red-eye flight") == "night"


# ===========================================================================
# 4. Strict List Filtering & Omission of Non-Matching Flights
# ===========================================================================

def test_filter_flight_offers_removes_non_matching():
    """
    Requirement 5: Remove flights outside the requested time range from displayed results.
    """
    mixed_offers = [
        {"flight_number": "6E-2054", "departure_time": "2026-11-12T00:30:00Z", "origin_iata": "BLR", "total_amount": 5400.0},  # 06:00 IST (Morning)
        {"flight_number": "AI-804", "departure_time": "2026-11-12T06:00:00+00:00", "origin_iata": "BLR", "total_amount": 6200.0},  # 11:30 IST (Morning)
        {"flight_number": "6E-5032", "departure_time": "2026-11-12T08:15:00+00:00", "origin_iata": "BLR", "total_amount": 4600.0}, # 13:45 IST (Afternoon)
        {"flight_number": "AI-506", "departure_time": "2026-11-12T18:00:00+00:00", "origin_iata": "BLR", "total_amount": 6800.0},  # 23:30 IST (Night)
    ]

    # Filter for morning (< 12:00 PM)
    morning_offers = filter_flight_offers_by_time(mixed_offers, "morning", origin_iata="BLR")
    flight_nums = [o["flight_number"] for o in morning_offers]

    assert len(morning_offers) == 2
    assert "6E-2054" in flight_nums
    assert "AI-804" in flight_nums
    # Afternoon and night flights MUST NOT be in the result
    assert "6E-5032" not in flight_nums
    assert "AI-506" not in flight_nums


def test_format_summary_strictly_omits_non_matching():
    """
    Requirement 6: Apply the filter consistently to AI text responses.
    """
    search_data = {
        "origin_iata": "BLR",
        "destination_iata": "DEL",
        "departure_date": "2026-11-12",
        "data_source": "mock_simulation",
        "is_simulation": True,
        "offers": [
            {
                "airline_name": "IndiGo",
                "flight_number": "6E-2054",
                "departure_time": "2026-11-12T00:30:00Z",  # 06:00 IST (Morning)
                "arrival_time": "2026-11-12T03:15:00Z",
                "total_amount": 5400.0,
                "currency": "INR",
                "cabin_class": "economy",
                "stops": 0,
                "duration_minutes": 165
            },
            {
                "airline_name": "IndiGo",
                "flight_number": "6E-5032",
                "departure_time": "2026-11-12T08:15:00+00:00",  # 13:45 IST (Afternoon)
                "arrival_time": "2026-11-12T12:35:00+00:00",
                "total_amount": 4600.0,
                "currency": "INR",
                "cabin_class": "economy",
                "stops": 1,
                "duration_minutes": 260
            }
        ]
    }

    summary = format_flight_offers_summary(search_data, preferred_time="morning")

    assert "6E-2054" in summary
    assert "6E-5032" not in summary  # Afternoon flight strictly excluded
    assert "Filtered strictly for your morning departure preference" in summary
    assert "SIMULATION / MOCK OFFER" in summary


# ===========================================================================
# 5. Empty Results When No Matching Flights Exist
# ===========================================================================

def test_no_matching_flights_returns_clear_message():
    """
    Requirement 7 & 8: If no matching flights exist, clearly say so without inventing alternatives.
    Preserve original provider/mock labels.
    """
    search_data = {
        "origin_iata": "BLR",
        "destination_iata": "DEL",
        "departure_date": "2026-11-12",
        "data_source": "mock_simulation",
        "is_simulation": True,
        "offers": [
            {
                "airline_name": "Air India",
                "flight_number": "AI-506",
                "departure_time": "2026-11-12T18:00:00+00:00",  # 23:30 IST (Night)
                "arrival_time": "2026-11-12T20:55:00+00:00",
                "total_amount": 6800.0,
                "currency": "INR",
                "cabin_class": "economy",
                "stops": 0,
                "duration_minutes": 175
            }
        ]
    }

    summary = format_flight_offers_summary(search_data, preferred_time="morning")

    # Explains no morning flights found
    assert "no **morning (departing before 12:00 PM)** flights were found" in summary
    # Does not list the night flight
    assert "AI-506" not in summary
    # Preserves provider transparency label
    assert "SIMULATION / MOCK OFFER" in summary


# ===========================================================================
# 6. End-to-End AI Agent Conversation Test
# ===========================================================================

@pytest.mark.anyio
async def test_agent_show_me_only_morning_flights_before_12_pm():
    """
    End-to-End Test: 'Show me only morning flights before 12 PM'.
    Verifies state slots, filtered results, and response formatting.
    """
    fixed_ref_date = date(2026, 11, 10)
    query = "Find flights from Bangalore to Delhi on 2026-11-12. Show me only morning flights before 12 PM."

    state = await run_flight_agent(
        query,
        reference_date=fixed_ref_date,
        force_fallback=True
    )

    assert state["slots"].get("origin") == "BLR"
    assert state["slots"].get("destination") == "DEL"
    assert state["slots"].get("departure_date") == "2026-11-12"
    assert state["slots"].get("preferred_time") == "morning"
    assert state["search_ready"] is True

    results = state.get("flight_search_results")
    assert results is not None
    offers = results.get("offers", [])

    # Every returned offer MUST depart strictly before 12:00 PM local time (Asia/Kolkata)
    for off in offers:
        dt = parse_local_departure_datetime(off["departure_time"], origin_iata="BLR")
        assert dt.time() < time(12, 0), f"Offer {off['flight_number']} departs at {dt.time()}, expected < 12:00"

    # Assistant reply must acknowledge morning filter and simulation status
    reply = state["assistant_reply"]
    assert "morning" in reply.lower()
    assert "SIMULATION / MOCK OFFER" in reply


# ===========================================================================
# 7. Date Rollover Regression Tests (Requirement 7)
# ===========================================================================

def test_regression_november_17_vs_november_18_departures():
    """
    Requirement 7: Regression test for a flight departing at 03:00 AM on November 18
    and another departing at 11:30 AM on November 17, when November 17 is requested.

    - Flight 1: 03:00 AM on 18 November 2026 IST (e.g. 2026-11-17T21:30:00+00:00 UTC)
    - Flight 2: 11:30 AM on 17 November 2026 IST (e.g. 2026-11-17T06:00:00+00:00 UTC)

    Result: Flight 1 MUST NOT be included. Flight 2 MUST be included.
    """
    requested_date = "2026-11-17"
    requested_time = "morning"

    # Flight 1: Departs at 21:30 UTC on Nov 17 -> which is 03:00 AM on Nov 18 in BLR (Asia/Kolkata)
    flight_1_nov_18 = {
        "airline_name": "IndiGo",
        "flight_number": "6E-2134",
        "departure_time": "2026-11-17T21:30:00+00:00",
        "arrival_time": "2026-11-18T00:10:00+00:00",
        "origin_iata": "BLR",
        "destination_iata": "DEL",
        "total_amount": 5200.0,
        "currency": "INR",
        "cabin_class": "economy",
        "stops": 0,
        "duration_minutes": 160
    }

    # Flight 2: Departs at 06:00 UTC on Nov 17 -> which is 11:30 AM on Nov 17 in BLR (Asia/Kolkata)
    flight_2_nov_17 = {
        "airline_name": "IndiGo",
        "flight_number": "6E-2054",
        "departure_time": "2026-11-17T06:00:00+00:00",
        "arrival_time": "2026-11-17T08:45:00+00:00",
        "origin_iata": "BLR",
        "destination_iata": "DEL",
        "total_amount": 5400.0,
        "currency": "INR",
        "cabin_class": "economy",
        "stops": 0,
        "duration_minutes": 165
    }

    # Verify individual matching evaluations in BLR local timezone (Asia/Kolkata)
    assert matches_departure_time_filter(
        flight_1_nov_18,
        preferred_time=requested_time,
        origin_iata="BLR",
        departure_date=requested_date
    ) is False, "Flight 1 (Nov 18 03:00 AM IST) must NOT match requested date Nov 17"

    assert matches_departure_time_filter(
        flight_2_nov_17,
        preferred_time=requested_time,
        origin_iata="BLR",
        departure_date=requested_date
    ) is True, "Flight 2 (Nov 17 11:30 AM IST) MUST match requested date Nov 17 before 12 PM"

    # Test list filtering
    all_offers = [flight_1_nov_18, flight_2_nov_17]
    filtered = filter_flight_offers_by_time(
        all_offers,
        preferred_time=requested_time,
        origin_iata="BLR",
        departure_date=requested_date
    )

    filtered_numbers = [f["flight_number"] for f in filtered]
    assert "6E-2054" in filtered_numbers, "Flight 2 (6E-2054) must be in filtered results"
    assert "6E-2134" not in filtered_numbers, "Flight 1 (6E-2134) MUST NOT be in filtered results"
    assert len(filtered) == 1

    # Test summary formatting
    search_data = {
        "origin_iata": "BLR",
        "destination_iata": "DEL",
        "departure_date": requested_date,
        "data_source": "mock_simulation",
        "is_simulation": True,
        "offers": all_offers
    }

    summary = format_flight_offers_summary(search_data, preferred_time=requested_time)
    assert "6E-2054" in summary, "Summary must include Flight 2"
    assert "6E-2134" not in summary, "Summary MUST NOT include Flight 1"
    assert "11:30 AM" in summary, "Summary must display local departure time 11:30 AM"


@pytest.mark.anyio
async def test_agent_november_17_morning_flight_browser_test_scenario():
    """
    End-to-End Agent Test matching the exact user browser test:
    - Requested departure date: 17 November 2026
    - Requested departure time: Before 12 PM
    - Origin: BLR, Destination: DEL
    """
    fixed_ref_date = date(2026, 11, 10)
    user_query = "Find flights from Bangalore to Delhi on 17 November 2026. Show me only morning flights before 12 PM."

    state = await run_flight_agent(
        user_query,
        reference_date=fixed_ref_date,
        force_fallback=True
    )

    assert state["slots"].get("origin") == "BLR"
    assert state["slots"].get("destination") == "DEL"
    assert state["slots"].get("departure_date") == "2026-11-17"
    assert state["slots"].get("preferred_time") == "morning"

    results = state.get("flight_search_results")
    assert results is not None
    offers = results.get("offers", [])

    # Verify that:
    # 1. At least one morning flight exists (6E-2054)
    # 2. Every single offer departs on 2026-11-17 in Asia/Kolkata
    # 3. Every single offer departs before 12:00 PM in Asia/Kolkata
    # 4. 6E-2134 (departs on Nov 18 03:00 AM IST) is strictly excluded
    flight_nums = [o["flight_number"] for o in offers]
    assert "6E-2054" in flight_nums
    assert "6E-2134" not in flight_nums

    for off in offers:
        dt = parse_local_departure_datetime(off["departure_time"], origin_iata="BLR")
        assert dt.date() == date(2026, 11, 17), f"Offer {off['flight_number']} departs on {dt.date()}, expected 2026-11-17"
        assert dt.time() < time(12, 0), f"Offer {off['flight_number']} departs at {dt.time()}, expected < 12:00"

    # Assistant reply verification
    reply = state["assistant_reply"]
    assert "6E-2054" in reply
    assert "6E-2134" not in reply
    assert "SIMULATION / MOCK OFFER" in reply

