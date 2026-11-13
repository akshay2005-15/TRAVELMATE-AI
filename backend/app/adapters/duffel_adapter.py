"""
Real Flight Provider Adapter for Duffel API.
Connects to Duffel's REST API (v2) for live offer requests and order workflows.
Strictly complies with SRS FR-022 to FR-027 and User Condition 1.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
import logging

from app.core.config import settings
from app.adapters.base import FlightProviderAdapter
from app.schemas.flight import FlightSearchRequest, FlightOfferSchema

logger = logging.getLogger(__name__)


class DuffelFlightProviderAdapter(FlightProviderAdapter):
    """
    Adapter implementing communication with the official Duffel Flight Distribution API.
    """

    DUFFEL_API_URL = "https://api.duffel.com/air/offer_requests?return_offers=true"
    OFFER_DETAILS_URL = "https://api.duffel.com/air/offers/{offer_id}"
    ORDERS_URL = "https://api.duffel.com/air/orders"

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or settings.DUFFEL_API_TOKEN

    @property
    def provider_name(self) -> str:
        return "duffel"

    @property
    def data_source_type(self) -> str:
        """
        Distinguishes Duffel sandbox vs production based on API token prefix.
        """
        if self.api_token and self.api_token.startswith("duffel_test_"):
            return "duffel_sandbox"
        return "duffel_production"

    @property
    def is_configured(self) -> bool:
        """Checks if a valid-looking Duffel token is set."""
        return bool(self.api_token and len(self.api_token) > 15 and not self.api_token.endswith("your_token_here"))

    async def search_offers(
        self,
        criteria: FlightSearchRequest
    ) -> List[FlightOfferSchema]:
        """
        Submits offer request to Duffel API and normalizes returned flight offers.
        """
        if not self.is_configured:
            logger.warning("Duffel API token not configured or using placeholder.")
            return []

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Build Duffel slice structure
        slices = [
            {
                "origin": criteria.origin.upper(),
                "destination": criteria.destination.upper(),
                "departure_date": criteria.departure_date,
            }
        ]

        if criteria.return_date:
            slices.append({
                "origin": criteria.destination.upper(),
                "destination": criteria.origin.upper(),
                "departure_date": criteria.return_date,
            })

        # Passengers payload
        passengers = [{"type": "adult"} for _ in range(criteria.passengers)]

        # Cabin class mapping for Duffel
        cabin_mapping = {
            "economy": "economy",
            "premium_economy": "premium_economy",
            "business": "business",
            "first": "first",
        }
        cabin = cabin_mapping.get(criteria.cabin_class, "economy")

        payload = {
            "data": {
                "slices": slices,
                "passengers": passengers,
                "cabin_class": cabin,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(self.DUFFEL_API_URL, headers=headers, json=payload)

                if response.status_code != 201:
                    logger.error(
                        f"Duffel API error [{response.status_code}]: {response.text}"
                    )
                    return []

                data = response.json().get("data", {})
                offers_raw = data.get("offers", [])

                return self._normalize_duffel_offers(offers_raw, criteria)

        except Exception as e:
            logger.error(f"Duffel API request exception: {str(e)}")
            return []

    async def get_offer_raw(
        self,
        provider_offer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves complete offer payload directly from Duffel.
        """
        if not self.is_configured:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
        }

        url = self.OFFER_DETAILS_URL.format(offer_id=provider_offer_id)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json().get("data")
        except Exception as e:
            logger.error(f"Duffel fetch offer error: {str(e)}")

        return None

    async def revalidate_offer(
        self,
        provider_offer_id: str,
        expected_amount: Optional[float] = None,
        currency: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Revalidates live offer availability, expiration, and pricing with Duffel API.
        Calls GET https://api.duffel.com/air/offers/{offer_id}.
        """
        if not self.is_configured:
            return {
                "is_valid": False,
                "price_changed": False,
                "current_amount": expected_amount or 0.0,
                "original_amount": expected_amount or 0.0,
                "currency": currency or "GBP",
                "expires_at": None,
                "data_source": self.data_source_type,
                "is_simulation": False,
                "message": "Duffel API is not configured.",
                "raw_offer": None,
            }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
        }
        url = self.OFFER_DETAILS_URL.format(offer_id=provider_offer_id)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    logger.warning(
                        f"Duffel offer revalidation failed [{response.status_code}]: {response.text}"
                    )
                    return {
                        "is_valid": False,
                        "price_changed": False,
                        "current_amount": expected_amount or 0.0,
                        "original_amount": expected_amount or 0.0,
                        "currency": currency or "GBP",
                        "expires_at": None,
                        "data_source": self.data_source_type,
                        "is_simulation": False,
                        "message": "Flight offer is no longer available or has expired.",
                        "raw_offer": None,
                    }

                offer_data = response.json().get("data", {})
                current_amount = float(offer_data.get("total_amount", 0.0))
                offer_currency = offer_data.get("total_currency", currency or "GBP")

                # Parse expiration timestamp
                expires_at_str = offer_data.get("expires_at")
                expires_at = None
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                # Check if offer is expired
                now = datetime.now(timezone.utc)
                if expires_at and expires_at < now:
                    return {
                        "is_valid": False,
                        "price_changed": False,
                        "current_amount": current_amount,
                        "original_amount": expected_amount if expected_amount is not None else current_amount,
                        "currency": offer_currency,
                        "expires_at": expires_at,
                        "data_source": self.data_source_type,
                        "is_simulation": False,
                        "message": "Flight offer has expired.",
                        "raw_offer": offer_data,
                    }

                # Check if price changed
                price_changed = False
                original_amount = expected_amount if expected_amount is not None else current_amount
                if expected_amount is not None and abs(current_amount - float(expected_amount)) > 0.01:
                    price_changed = True
                    message = (
                        f"Price changed from {currency or offer_currency} {expected_amount:.2f} "
                        f"to {offer_currency} {current_amount:.2f}."
                    )
                else:
                    message = "Offer is valid and available."

                return {
                    "is_valid": True,
                    "price_changed": price_changed,
                    "current_amount": current_amount,
                    "original_amount": original_amount,
                    "currency": offer_currency,
                    "expires_at": expires_at,
                    "data_source": self.data_source_type,
                    "is_simulation": False,
                    "message": message,
                    "raw_offer": offer_data,
                }

        except Exception as e:
            logger.error(f"Duffel revalidate offer error: {str(e)}")
            return {
                "is_valid": False,
                "price_changed": False,
                "current_amount": expected_amount or 0.0,
                "original_amount": expected_amount or 0.0,
                "currency": currency or "GBP",
                "expires_at": None,
                "data_source": self.data_source_type,
                "is_simulation": False,
                "message": f"Error revalidating offer with Duffel: {str(e)}",
                "raw_offer": None,
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
        Creates a flight order with Duffel API (Sandbox).
        Calls POST https://api.duffel.com/air/orders.
        Uses balance payment in test/sandbox environment.

        NOTE ON IDEMPOTENCY: Verified against official Duffel API v2 documentation.
        Duffel does NOT support client-defined request-level 'Idempotency-Key' HTTP headers
        on POST /air/orders. Downstream duplicate order prevention is strictly guaranteed
        by our local database-backed BookingIntentReservation and Duffel's single-use offer lifecycle.
        """
        # Definitive Pre-Request Failure: No request sent to Duffel
        if not self.is_configured:
            return {
                "success": False,
                "provider_booking_id": "",
                "booking_reference": None,
                "status": "failed",
                "total_amount": total_amount,
                "currency": currency,
                "data_source": self.data_source_type,
                "is_simulation": False,
                "raw_order": None,
                "is_ambiguous": False,
                "error_code": "pre_request_unconfigured",
                "error_message": "Duffel API is not configured.",
            }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Format passengers for Duffel
        duffel_passengers = []
        for p in passengers:
            pax_entry: Dict[str, Any] = {
                "type": "adult",
                "given_name": p.get("first_name", ""),
                "family_name": p.get("last_name", ""),
                "born_on": p.get("date_of_birth", ""),
                "title": p.get("title", "mr").lower(),
                "gender": "m" if p.get("gender") == "male" else ("f" if p.get("gender") == "female" else "m"),
            }
            if p.get("id"):
                pax_entry["id"] = p["id"]
            if contact.get("email"):
                pax_entry["email"] = contact["email"]
            if contact.get("phone"):
                pax_entry["phone_number"] = contact["phone"]
            duffel_passengers.append(pax_entry)

        payload = {
            "data": {
                "selected_offers": [provider_offer_id],
                "passengers": duffel_passengers,
                "payments": [
                    {
                        "type": "balance",
                        "currency": currency,
                        "amount": f"{total_amount:.2f}",
                    }
                ],
            }
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(self.ORDERS_URL, headers=headers, json=payload)

                if response.status_code == 201:
                    order_data = response.json().get("data", {})
                    return {
                        "success": True,
                        "provider_booking_id": order_data.get("id", ""),
                        "booking_reference": order_data.get("booking_reference"),
                        "status": "confirmed",
                        "total_amount": float(order_data.get("total_amount", total_amount)),
                        "currency": order_data.get("total_currency", currency),
                        "data_source": self.data_source_type,
                        "is_simulation": False,
                        "raw_order": order_data,
                        "is_ambiguous": False,
                        "error_message": None,
                    }

                # Parse error response body if available
                err_msg = f"Duffel order creation failed with status {response.status_code}"
                try:
                    err_json = response.json()
                    errors = err_json.get("errors", [])
                    if errors and "message" in errors[0]:
                        err_msg = errors[0]["message"]
                except Exception:
                    err_msg = response.text or err_msg

                # Categorize: Definitive 4xx client rejection vs. Ambiguous 5xx / 408 server errors
                is_ambiguous = (response.status_code >= 500) or (response.status_code == 408)
                error_code = "ambiguous_server_error" if is_ambiguous else "provider_rejected"

                logger.error(f"Duffel create order error [{response.status_code}] (ambiguous={is_ambiguous}): {err_msg}")
                raw_json = None
                try:
                    raw_json = response.json()
                except Exception:
                    pass

                return {
                    "success": False,
                    "provider_booking_id": "",
                    "booking_reference": None,
                    "status": "failed",
                    "total_amount": total_amount,
                    "currency": currency,
                    "data_source": self.data_source_type,
                    "is_simulation": False,
                    "raw_order": raw_json,
                    "is_ambiguous": is_ambiguous,
                    "error_code": error_code,
                    "error_message": err_msg,
                }

        except Exception as e:
            # Post-request network drops, connection resets, read timeouts: ALWAYS ambiguous
            logger.error(f"Duffel create order post-request network exception (ambiguous=True): {str(e)}")
            return {
                "success": False,
                "provider_booking_id": "",
                "booking_reference": None,
                "status": "failed",
                "total_amount": total_amount,
                "currency": currency,
                "data_source": self.data_source_type,
                "is_simulation": False,
                "raw_order": None,
                "is_ambiguous": True,
                "error_code": "ambiguous_network_error",
                "error_message": str(e),
            }

    def _normalize_duffel_offers(
        self,
        offers_raw: List[Dict[str, Any]],
        criteria: FlightSearchRequest
    ) -> List[FlightOfferSchema]:
        """
        Maps Duffel offer models to internal FlightOfferSchema.
        """
        normalized: List[FlightOfferSchema] = []

        for item in offers_raw:
            try:
                offer_id = item["id"]
                owner = item.get("owner", {})
                airline_name = owner.get("name", "Commercial Airline")
                airline_code = owner.get("iata_code", "XX")

                # Parse the outbound slice
                slices = item.get("slices", [])
                if not slices:
                    continue

                outbound_slice = slices[0]
                segments = outbound_slice.get("segments", [])
                if not segments:
                    continue

                first_seg = segments[0]
                last_seg = segments[-1]

                origin_iata = first_seg["origin"]["iata_code"]
                destination_iata = last_seg["destination"]["iata_code"]
                dep_time = first_seg["departing_at"]
                arr_time = last_seg["arriving_at"]
                flight_num = f"{first_seg.get('marketing_carrier', {}).get('iata_code', airline_code)}-{first_seg.get('marketing_carrier_flight_number', '101')}"

                # Calculate stops
                stops = len(segments) - 1
                stop_details = None
                if stops > 0:
                    layover_airport = segments[0]["destination"]["iata_code"]
                    stop_details = f"{stops} stop via {layover_airport}"

                # Duration in minutes
                duration_iso = outbound_slice.get("duration", "PT2H0M")
                duration_mins = self._parse_iso_duration(duration_iso)

                # Pricing
                total_amount = float(item["total_amount"])
                currency = item.get("total_currency", "GBP")

                # Baggage
                passengers = item.get("passengers", [])
                baggage_desc = "Standard Baggage Allowance"
                if passengers and "baggages" in passengers[0]:
                    bags = passengers[0]["baggages"]
                    if bags:
                        baggage_desc = f"{len(bags)} checked bag(s) included"

                # Expiration
                expires_at_str = item.get("expires_at")
                expires_at = None
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                offer = FlightOfferSchema(
                    provider_offer_id=offer_id,
                    airline_name=airline_name,
                    airline_code=airline_code,
                    flight_number=flight_num,
                    origin_iata=origin_iata,
                    destination_iata=destination_iata,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    duration_minutes=duration_mins,
                    stops=stops,
                    stop_details=stop_details,
                    total_amount=total_amount,
                    currency=currency,
                    cabin_class=criteria.cabin_class,
                    baggage_included=baggage_desc,
                    data_source=self.data_source_type,
                    is_simulation=False,  # Authentic Duffel data
                    expires_at=expires_at
                )
                normalized.append(offer)

            except Exception as parse_err:
                logger.warning(f"Failed to normalize single Duffel offer: {parse_err}")
                continue

        # Sort by price
        normalized.sort(key=lambda x: x.total_amount)
        return normalized

    def _parse_iso_duration(self, iso_duration: str) -> int:
        """Parses ISO 8601 duration (e.g. 'PT2H30M', 'PT45M') into total minutes."""
        try:
            s = iso_duration.replace("PT", "")
            hours = 0
            mins = 0
            if "H" in s:
                parts = s.split("H")
                hours = int(parts[0])
                s = parts[1]
            if "M" in s:
                mins = int(s.replace("M", ""))
            return (hours * 60) + mins
        except Exception:
            return 120
