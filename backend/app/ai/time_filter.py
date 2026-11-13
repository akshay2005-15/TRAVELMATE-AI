"""
Departure-Time Filtering and Airport Local Timezone Resolution Module for TRAVELMATE AI.
Interprets flight timestamps in airport local time (e.g. Asia/Kolkata for BLR),
implements precise time window filtering, and handles UTC-to-IST conversion.
"""

from datetime import datetime, date, time, timezone, timedelta
from typing import Optional, Dict, Any, List, Union
import logging

from app.adapters.airports import get_airport_timezone

logger = logging.getLogger(__name__)

# Standard Timezone Offsets (Zero-dependency fallback across all OS platforms, including Windows)
TIMEZONE_OFFSETS: Dict[str, timezone] = {
    "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30), name="IST"),
    "Europe/London": timezone(timedelta(hours=0), name="GMT"),
    "America/New_York": timezone(timedelta(hours=-5), name="EST"),
    "America/Los_Angeles": timezone(timedelta(hours=-8), name="PST"),
    "Asia/Dubai": timezone(timedelta(hours=4), name="GST"),
    "Asia/Qatar": timezone(timedelta(hours=3), name="AST"),
    "Asia/Singapore": timezone(timedelta(hours=8), name="SGT"),
    "Asia/Bangkok": timezone(timedelta(hours=7), name="ICT"),
    "Asia/Kuala_Lumpur": timezone(timedelta(hours=8), name="MYT"),
    "Asia/Tokyo": timezone(timedelta(hours=9), name="JST"),
    "Europe/Paris": timezone(timedelta(hours=1), name="CET"),
    "Europe/Berlin": timezone(timedelta(hours=1), name="CET"),
    "Europe/Amsterdam": timezone(timedelta(hours=1), name="CET"),
    "Australia/Sydney": timezone(timedelta(hours=10), name="AEST"),
    "America/Toronto": timezone(timedelta(hours=-5), name="EST"),
}


def get_timezone_obj(tz_name: str) -> timezone:
    """
    Returns a tzinfo object for the specified IANA timezone name.
    Tries ZoneInfo first, and gracefully falls back to standard datetime.timezone offset.
    For Asia/Kolkata (BLR), returns UTC+05:30.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        pass
    return TIMEZONE_OFFSETS.get(tz_name, timezone(timedelta(hours=5, minutes=30), name="IST"))


def parse_local_departure_datetime(
    departure_time_str: str,
    origin_iata: Optional[str] = None
) -> datetime:
    """
    Parses a flight departure timestamp (ISO 8601 with UTC/offset or naive)
    and converts it to the departure airport's local timezone.
    For BLR and all Indian hubs, converts to Asia/Kolkata (IST = UTC+05:30).

    Examples:
      - '2026-11-12T00:30:00Z' (BLR) -> 06:00:00 IST (UTC+05:30)
      - '2026-11-12T06:00:00+00:00' (BLR) -> 11:30:00 IST (UTC+05:30)
      - '2026-11-12T08:15:00+00:00' (BLR) -> 13:45:00 IST (UTC+05:30)
      - '2026-11-12T06:00:00' (BLR naive) -> 06:00:00 IST
    """
    if not departure_time_str:
        raise ValueError("departure_time_str cannot be empty")

    tz_name = get_airport_timezone(origin_iata)
    tz = get_timezone_obj(tz_name)

    raw_str = departure_time_str.strip()
    if raw_str.endswith("Z") or raw_str.endswith("z"):
        raw_str = raw_str[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(raw_str)
    except ValueError:
        # Fallback if only HH:MM was supplied
        if ":" in raw_str and "T" not in raw_str:
            parts = raw_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            today = date.today()
            return datetime(today.year, today.month, today.day, h, m, tzinfo=tz)
        raise

    if dt.tzinfo is not None:
        # Convert timezone-aware datetime (e.g. UTC) to airport's local timezone
        return dt.astimezone(tz)
    else:
        # Naive datetime is treated as already in the airport's local timezone
        return dt.replace(tzinfo=tz)


def matches_departure_time_filter(
    offer: Dict[str, Any],
    preferred_time: Optional[str] = None,
    origin_iata: Optional[str] = None,
    departure_date: Optional[Union[str, date]] = None
) -> bool:
    """
    Determines whether a flight offer departs within the requested time window
    AND on the requested departure date, interpreted strictly in the origin airport's local timezone.

    Conditions applied together (Requirements 1, 2, 3):
      1. Departure date matches requested date in origin airport local timezone.
      2. Departure time falls within requested window (e.g. before 12:00 PM for 'morning')
         in origin airport local timezone.
    """
    dep_str = offer.get("departure_time")
    if not dep_str:
        return False

    orig = origin_iata or offer.get("origin_iata")
    try:
        local_dt = parse_local_departure_datetime(dep_str, origin_iata=orig)
    except Exception as e:
        logger.warning(f"Failed to parse departure time '{dep_str}' for time filter: {e}")
        return False

    # 1. Date Matching Condition (Requirement 1)
    if departure_date:
        expected_date: Optional[date] = None
        if isinstance(departure_date, str):
            try:
                expected_date = datetime.strptime(departure_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                expected_date = None
        elif isinstance(departure_date, date):
            expected_date = departure_date

        if expected_date is not None and local_dt.date() != expected_date:
            return False

    # 2. Time Window Condition (Requirement 2 & 4)
    if preferred_time:
        local_t = local_dt.time()
        pref = preferred_time.lower().strip()

        if pref == "morning":
            # Requirement 4: "For 'before 12 PM', include only departures earlier than 12:00 local time."
            if not (local_t < time(12, 0)):
                return False
        elif pref == "afternoon":
            if not (time(12, 0) <= local_t < time(17, 0)):
                return False
        elif pref == "evening":
            if not (time(17, 0) <= local_t < time(21, 0)):
                return False
        elif pref == "night":
            if not (local_t >= time(21, 0) or local_t < time(5, 0)):
                return False

    return True


def filter_flight_offers_by_time(
    offers: List[Dict[str, Any]],
    preferred_time: Optional[str] = None,
    origin_iata: Optional[str] = None,
    departure_date: Optional[Union[str, date]] = None
) -> List[Dict[str, Any]]:
    """
    Filters a list of flight offers to include ONLY those matching:
      - Requested departure date in the origin airport's local timezone (Requirement 1).
      - Requested departure time window in the origin airport's local timezone (Requirement 2 & 4).
    Both conditions are applied together (Requirement 3).
    Removes all non-matching flights (Requirement 5).
    """
    if not preferred_time and not departure_date:
        return list(offers)

    return [
        o for o in offers
        if matches_departure_time_filter(
            o,
            preferred_time=preferred_time,
            origin_iata=origin_iata,
            departure_date=departure_date
        )
    ]
