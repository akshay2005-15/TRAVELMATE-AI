"""
High-Fidelity Mock Flight Provider Adapter.
Provides realistic flight schedules and pricing for offline development, tests, and viva demonstration.
Strictly complies with User Condition 2: Explicitly tags all data as 'mock_simulation' and 'is_simulation=True'.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import hashlib

from app.adapters.base import FlightProviderAdapter
from app.schemas.flight import FlightSearchRequest, FlightOfferSchema


# Master catalog of realistic flights between key hubs
MOCK_AIRLINE_ROUTES = [
    # BLR <-> DEL
    {"from": "BLR", "to": "DEL", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-2054", "dep": "06:00", "dur": 165, "stops": 0, "base_price": 5400, "baggage": "15 kg Check-in, 7 kg Cabin"},
    {"from": "BLR", "to": "DEL", "carrier": "Air India", "code": "AI", "fl_num": "AI-804", "dep": "08:15", "dur": 170, "stops": 0, "base_price": 6200, "baggage": "25 kg Check-in, 7 kg Cabin"},
    {"from": "BLR", "to": "DEL", "carrier": "Akasa Air", "code": "QP", "fl_num": "QP-1311", "dep": "11:30", "dur": 165, "stops": 0, "base_price": 4900, "baggage": "15 kg Check-in, 7 kg Cabin"},
    {"from": "BLR", "to": "DEL", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-5032", "dep": "14:45", "dur": 260, "stops": 1, "stop_via": "1 stop via BOM (1h 15m layover)", "base_price": 4600, "baggage": "15 kg Check-in, 7 kg Cabin"},
    {"from": "BLR", "to": "DEL", "carrier": "Air India", "code": "AI", "fl_num": "AI-506", "dep": "18:00", "dur": 175, "stops": 0, "base_price": 6800, "baggage": "25 kg Check-in, 7 kg Cabin"},
    {"from": "BLR", "to": "DEL", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-2134", "dep": "21:30", "dur": 160, "stops": 0, "base_price": 5200, "baggage": "15 kg Check-in, 7 kg Cabin"},

    # DEL <-> BLR
    {"from": "DEL", "to": "BLR", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-2055", "dep": "07:00", "dur": 165, "stops": 0, "base_price": 5300, "baggage": "15 kg Check-in, 7 kg Cabin"},
    {"from": "DEL", "to": "BLR", "carrier": "Air India", "code": "AI", "fl_num": "AI-803", "dep": "09:30", "dur": 170, "stops": 0, "base_price": 6100, "baggage": "25 kg Check-in, 7 kg Cabin"},
    {"from": "DEL", "to": "BLR", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-6102", "dep": "16:20", "dur": 165, "stops": 0, "base_price": 5500, "baggage": "15 kg Check-in, 7 kg Cabin"},
    {"from": "DEL", "to": "BLR", "carrier": "Akasa Air", "code": "QP", "fl_num": "QP-1312", "dep": "19:00", "dur": 165, "stops": 0, "base_price": 5100, "baggage": "15 kg Check-in, 7 kg Cabin"},

    # BOM <-> DEL
    {"from": "BOM", "to": "DEL", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-5301", "dep": "07:30", "dur": 130, "stops": 0, "base_price": 4800, "baggage": "15 kg Check-in, 7 kg Cabin"},
    {"from": "BOM", "to": "DEL", "carrier": "Air India", "code": "AI", "fl_num": "AI-677", "dep": "13:00", "dur": 135, "stops": 0, "base_price": 5700, "baggage": "25 kg Check-in, 7 kg Cabin"},
    {"from": "BOM", "to": "DEL", "carrier": "Akasa Air", "code": "QP", "fl_num": "QP-1102", "dep": "18:45", "dur": 130, "stops": 0, "base_price": 4600, "baggage": "15 kg Check-in, 7 kg Cabin"},

    # BLR <-> BOM
    {"from": "BLR", "to": "BOM", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-5201", "dep": "08:00", "dur": 105, "stops": 0, "base_price": 3800, "baggage": "15 kg Check-in, 7 kg Cabin"},
    {"from": "BLR", "to": "BOM", "carrier": "Air India", "code": "AI", "fl_num": "AI-640", "dep": "15:30", "dur": 110, "stops": 0, "base_price": 4400, "baggage": "25 kg Check-in, 7 kg Cabin"},

    # International: LHR <-> JFK
    {"from": "LHR", "to": "JFK", "carrier": "British Airways", "code": "BA", "fl_num": "BA-117", "dep": "08:30", "dur": 475, "stops": 0, "base_price": 42000, "baggage": "23 kg Check-in, 10 kg Cabin"},
    {"from": "LHR", "to": "JFK", "carrier": "Virgin Atlantic", "code": "VS", "fl_num": "VS-003", "dep": "11:50", "dur": 485, "stops": 0, "base_price": 44500, "baggage": "23 kg Check-in, 10 kg Cabin"},
    {"from": "LHR", "to": "JFK", "carrier": "Air France", "code": "AF", "fl_num": "AF-1681", "dep": "06:15", "dur": 610, "stops": 1, "stop_via": "1 stop via CDG (1h 50m layover)", "base_price": 38500, "baggage": "23 kg Check-in, 12 kg Cabin"},

    # International: DEL <-> LHR
    {"from": "DEL", "to": "LHR", "carrier": "Air India", "code": "AI", "fl_num": "AI-161", "dep": "02:45", "dur": 570, "stops": 0, "base_price": 58000, "baggage": "2x23 kg Check-in, 8 kg Cabin"},
    {"from": "DEL", "to": "LHR", "carrier": "British Airways", "code": "BA", "fl_num": "BA-142", "dep": "10:15", "dur": 565, "stops": 0, "base_price": 64000, "baggage": "23 kg Check-in, 10 kg Cabin"},
    {"from": "DEL", "to": "LHR", "carrier": "Emirates", "code": "EK", "fl_num": "EK-511", "dep": "13:20", "dur": 690, "stops": 1, "stop_via": "1 stop via DXB (2h 10m layover)", "base_price": 54000, "baggage": "30 kg Check-in, 7 kg Cabin"},

    # International: BLR <-> SIN
    {"from": "BLR", "to": "SIN", "carrier": "Singapore Airlines", "code": "SQ", "fl_num": "SQ-503", "dep": "23:05", "dur": 285, "stops": 0, "base_price": 28500, "baggage": "25 kg Check-in, 7 kg Cabin"},
    {"from": "BLR", "to": "SIN", "carrier": "IndiGo", "code": "6E", "fl_num": "6E-1007", "dep": "09:10", "dur": 290, "stops": 0, "base_price": 22000, "baggage": "20 kg Check-in, 7 kg Cabin"},

    # International: BOM <-> DXB
    {"from": "BOM", "to": "DXB", "carrier": "Emirates", "code": "EK", "fl_num": "EK-501", "dep": "04:30", "dur": 205, "stops": 0, "base_price": 24000, "baggage": "30 kg Check-in, 7 kg Cabin"},
    {"from": "BOM", "to": "DXB", "carrier": "Air India", "code": "AI", "fl_num": "AI-983", "dep": "20:00", "dur": 210, "stops": 0, "base_price": 19500, "baggage": "25 kg Check-in, 7 kg Cabin"},
]


class MockFlightProviderAdapter(FlightProviderAdapter):
    """
    Simulated flight provider generating authentic, predictable flight offers.
    All offers carry `data_source = 'mock_simulation'` and `is_simulation = True`.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def data_source_type(self) -> str:
        return "mock_simulation"

    async def search_offers(
        self,
        criteria: FlightSearchRequest
    ) -> List[FlightOfferSchema]:
        origin = criteria.origin.upper()
        dest = criteria.destination.upper()
        dep_date_str = criteria.departure_date

        # Look for predefined route matches
        matching_routes = [
            r for r in MOCK_AIRLINE_ROUTES
            if r["from"] == origin and r["to"] == dest
        ]

        # If no specific predefined route exists, synthesize realistic dynamic flights
        if not matching_routes:
            matching_routes = self._synthesize_generic_route(origin, dest)

        offers: List[FlightOfferSchema] = []

        for idx, route in enumerate(matching_routes):
            # Compute departure & arrival ISO timestamps
            dep_hour, dep_min = map(int, route["dep"].split(":"))
            dep_dt = datetime.strptime(dep_date_str, "%Y-%m-%d").replace(
                hour=dep_hour, minute=dep_min, tzinfo=timezone.utc
            )
            arr_dt = dep_dt + timedelta(minutes=route["dur"])

            # Class multiplier
            class_multiplier = 1.0
            if criteria.cabin_class == "premium_economy":
                class_multiplier = 1.45
            elif criteria.cabin_class == "business":
                class_multiplier = 2.6
            elif criteria.cabin_class == "first":
                class_multiplier = 4.2

            # Total price per passenger * passenger count
            total_price = round(route["base_price"] * class_multiplier * criteria.passengers, 2)

            # Deterministic provider offer ID for reproducible testing
            unique_hash = hashlib.md5(
                f"{route['fl_num']}_{dep_date_str}_{idx}_{criteria.cabin_class}".encode()
            ).hexdigest()[:12]
            offer_id = f"mock_off_{unique_hash}"

            offer = FlightOfferSchema(
                provider_offer_id=offer_id,
                airline_name=route["carrier"],
                airline_code=route["code"],
                flight_number=route["fl_num"],
                origin_iata=origin,
                destination_iata=dest,
                departure_time=dep_dt.isoformat(),
                arrival_time=arr_dt.isoformat(),
                duration_minutes=route["dur"],
                stops=route.get("stops", 0),
                stop_details=route.get("stop_via"),
                total_amount=total_price,
                currency="INR" if origin in ["BLR", "DEL", "BOM", "MAA", "HYD", "CCU", "COK", "GOI"] else "USD",
                cabin_class=criteria.cabin_class,
                baggage_included=route.get("baggage", "15 kg Check-in, 7 kg Cabin"),
                data_source=self.data_source_type,
                is_simulation=True,
                expires_at=dep_dt + timedelta(hours=2)
            )
            offers.append(offer)

        # Sort initially by price
        offers.sort(key=lambda x: x.total_amount)
        return offers

    async def get_offer_raw(
        self,
        provider_offer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Returns mock raw data payload for simulation state machine.
        """
        return {
            "provider": "mock",
            "offer_id": provider_offer_id,
            "data_source": self.data_source_type,
            "is_simulation": True,
            "status": "valid"
        }

    async def revalidate_offer(
        self,
        provider_offer_id: str,
        expected_amount: Optional[float] = None,
        currency: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Revalidates a simulated flight offer.
        Supports deterministic testing flags in provider_offer_id:
        - Contains 'expired': simulates an expired offer.
        - Contains 'price_changed': simulates a price change (increases price by 500).
        - Contains 'unavailable': simulates an unavailable offer.
        """
        curr = currency or "INR"

        if "expired" in provider_offer_id.lower():
            return {
                "is_valid": False,
                "price_changed": False,
                "current_amount": expected_amount or 5400.0,
                "original_amount": expected_amount or 5400.0,
                "currency": curr,
                "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
                "data_source": self.data_source_type,
                "is_simulation": True,
                "message": "Flight offer has expired (Simulated).",
                "raw_offer": {
                    "provider": "mock",
                    "offer_id": provider_offer_id,
                    "data_source": self.data_source_type,
                    "is_simulation": True,
                    "status": "expired",
                },
            }

        if "unavailable" in provider_offer_id.lower():
            return {
                "is_valid": False,
                "price_changed": False,
                "current_amount": expected_amount or 5400.0,
                "original_amount": expected_amount or 5400.0,
                "currency": curr,
                "expires_at": None,
                "data_source": self.data_source_type,
                "is_simulation": True,
                "message": "Flight offer is no longer available (Simulated).",
                "raw_offer": None,
            }

        if "price_changed" in provider_offer_id.lower() and expected_amount is not None:
            current_amount = round(float(expected_amount) + 500.0, 2)
            price_changed = True
            message = (
                f"Price changed from {curr} {expected_amount:.2f} "
                f"to {curr} {current_amount:.2f} (Simulated)."
            )
        else:
            current_amount = float(expected_amount) if expected_amount is not None else 5400.0
            price_changed = False
            message = "Offer is valid and available (Simulated)."

        original_amount = float(expected_amount) if expected_amount is not None else current_amount
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

        return {
            "is_valid": True,
            "price_changed": price_changed,
            "current_amount": current_amount,
            "original_amount": original_amount,
            "currency": curr,
            "expires_at": expires_at,
            "data_source": self.data_source_type,
            "is_simulation": True,
            "message": message,
            "raw_offer": {
                "provider": "mock",
                "offer_id": provider_offer_id,
                "data_source": self.data_source_type,
                "is_simulation": True,
                "status": "valid",
                "total_amount": current_amount,
                "currency": curr,
            },
        }

    async def create_order(
        self,
        provider_offer_id: str,
        passengers: List[Dict[str, Any]],
        contact: Dict[str, str],
        total_amount: float,
        currency: str
    ) -> Dict[str, Any]:
        """
        Creates a deterministic simulated flight booking order.
        Strictly sets data_source='mock_simulation' and is_simulation=True.
        Supports simulation flags in provider_offer_id:
        - Contains 'fail_order': simulates order failure from provider.
        """
        if "timeout" in provider_offer_id.lower():
            return {
                "success": False,
                "provider_booking_id": "",
                "booking_reference": None,
                "status": "failed",
                "total_amount": total_amount,
                "currency": currency,
                "data_source": self.data_source_type,
                "is_simulation": True,
                "is_ambiguous": True,
                "error_code": "ambiguous_timeout",
                "raw_order": None,
                "error_message": "Gateway connection timed out after 25s.",
            }

        if "connection_reset" in provider_offer_id.lower():
            return {
                "success": False,
                "provider_booking_id": "",
                "booking_reference": None,
                "status": "failed",
                "total_amount": total_amount,
                "currency": currency,
                "data_source": self.data_source_type,
                "is_simulation": True,
                "is_ambiguous": True,
                "error_code": "ambiguous_connection_drop",
                "raw_order": None,
                "error_message": "Connection reset by peer after order submission.",
            }

        if any(x in provider_offer_id.lower() for x in ["server_500", "server_502", "server_503", "500", "502", "503"]):
            code = "500" if "500" in provider_offer_id else ("502" if "502" in provider_offer_id else "503")
            return {
                "success": False,
                "provider_booking_id": "",
                "booking_reference": None,
                "status": "failed",
                "total_amount": total_amount,
                "currency": currency,
                "data_source": self.data_source_type,
                "is_simulation": True,
                "is_ambiguous": True,
                "error_code": "ambiguous_server_error",
                "raw_order": None,
                "error_message": f"Provider returned HTTP {code} Server Error during order processing.",
            }

        if "fail_order" in provider_offer_id.lower():
            return {
                "success": False,
                "provider_booking_id": "",
                "booking_reference": None,
                "status": "failed",
                "total_amount": total_amount,
                "currency": currency,
                "data_source": self.data_source_type,
                "is_simulation": True,
                "is_ambiguous": False,
                "error_code": "provider_rejected",
                "raw_order": {
                    "provider": "mock",
                    "offer_id": provider_offer_id,
                    "status": "failed",
                    "reason": "Simulated provider failure",
                },
                "error_message": "Simulated provider booking failed (Test error).",
            }

        first_pax_name = passengers[0].get("last_name", "PAX") if passengers else "PAX"
        seed_str = f"{provider_offer_id}_{first_pax_name}_{total_amount}"
        ref_hash = hashlib.md5(seed_str.encode()).hexdigest()[:6].upper()
        booking_reference = f"MOCK-{ref_hash}"
        provider_booking_id = f"mock_ord_{ref_hash.lower()}"

        raw_order = {
            "provider": "mock",
            "id": provider_booking_id,
            "booking_reference": booking_reference,
            "status": "confirmed",
            "total_amount": f"{total_amount:.2f}",
            "currency": currency,
            "passenger_count": len(passengers),
            "contact_email": contact.get("email"),
            "contact_phone": contact.get("phone"),
            "data_source": self.data_source_type,
            "is_simulation": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "success": True,
            "provider_booking_id": provider_booking_id,
            "booking_reference": booking_reference,
            "status": "confirmed",
            "total_amount": total_amount,
            "currency": currency,
            "data_source": self.data_source_type,
            "is_simulation": True,
            "raw_order": raw_order,
            "error_message": None,
        }

    def _synthesize_generic_route(self, origin: str, dest: str) -> List[Dict[str, Any]]:
        """
        Generates realistic fallback flight records when arbitrary city pairs are requested.
        """
        return [
            {
                "from": origin, "to": dest, "carrier": "Air India", "code": "AI",
                "fl_num": f"AI-{abs(hash(origin + dest)) % 900 + 100}",
                "dep": "07:30", "dur": 180, "stops": 0, "base_price": 6500,
                "baggage": "25 kg Check-in, 7 kg Cabin"
            },
            {
                "from": origin, "to": dest, "carrier": "IndiGo", "code": "6E",
                "fl_num": f"6E-{abs(hash(dest + origin)) % 900 + 100}",
                "dep": "13:15", "dur": 175, "stops": 0, "base_price": 5400,
                "baggage": "15 kg Check-in, 7 kg Cabin"
            },
            {
                "from": origin, "to": dest, "carrier": "Star Air Connect", "code": "S5",
                "fl_num": f"S5-{abs(hash(origin)) % 900 + 100}",
                "dep": "18:40", "dur": 270, "stops": 1,
                "stop_via": "1 stop via Hub (1h 10m layover)",
                "base_price": 4800, "baggage": "15 kg Check-in, 7 kg Cabin"
            }
        ]
