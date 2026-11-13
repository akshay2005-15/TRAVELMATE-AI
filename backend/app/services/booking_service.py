"""
Centralized Flight Booking Orchestration Service.
Coordinates flight offer revalidation, price-change protection, passenger validation,
order creation through provider adapters, and secure database persistence.
Complies with SRS Section 6, FR-022 to FR-027, User Condition 2, and Phase 4 Step 4 specifications.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.booking import Booking
from app.models.flight import FlightOffer
from app.schemas.booking import (
    BookingCreateRequest,
    BookingResponse,
    BookingSummaryResponse,
    OfferRevalidationResponse,
    PassengerBookingDetails,
    BookingContactDetails,
)
from app.adapters.base import FlightProviderAdapter
from app.adapters.duffel_adapter import DuffelFlightProviderAdapter
from app.adapters.mock_adapter import MockFlightProviderAdapter

logger = logging.getLogger(__name__)


# ===========================================================================
# Structured Exceptions for Booking Operations
# ===========================================================================

class BookingServiceError(Exception):
    """Base exception for all booking service operations."""
    def __init__(self, message: str, code: str = "booking_error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class BookingNotFoundError(BookingServiceError):
    def __init__(self, message: str = "Booking not found.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="booking_not_found", details=details)


class BookingOfferNotFoundError(BookingServiceError):
    def __init__(self, message: str = "Flight offer not found.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="offer_not_found", details=details)


class BookingOfferExpiredError(BookingServiceError):
    def __init__(self, message: str = "Flight offer has expired.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="offer_expired", details=details)


class BookingOfferUnavailableError(BookingServiceError):
    def __init__(self, message: str = "Flight offer is no longer available from the provider.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="offer_unavailable", details=details)


class BookingPriceChangedError(BookingServiceError):
    """
    Raised when live provider price differs from the quoted or user-authorized amount.
    Enforces Step 4: Stale consent rejection and fresh user confirmation requirement.
    """
    def __init__(
        self,
        message: str,
        original_amount: float,
        current_amount: float,
        currency: str,
        details: Optional[Dict[str, Any]] = None
    ):
        d = details or {}
        d.update({
            "original_amount": original_amount,
            "current_amount": current_amount,
            "currency": currency,
            "price_changed": True,
        })
        super().__init__(message, code="price_changed", details=d)
        self.original_amount = original_amount
        self.current_amount = current_amount
        self.currency = currency


class BookingCurrencyMismatchError(BookingServiceError):
    def __init__(self, message: str, expected_currency: str, current_currency: str, details: Optional[Dict[str, Any]] = None):
        d = details or {}
        d.update({"expected_currency": expected_currency, "current_currency": current_currency})
        super().__init__(message, code="currency_mismatch", details=d)
        self.expected_currency = expected_currency
        self.current_currency = current_currency


class BookingMissingConsentError(BookingServiceError):
    def __init__(self, message: str = "Explicit user confirmation is mandatory to authorize flight booking.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="missing_consent", details=details)


class BookingStaleConsentError(BookingServiceError):
    def __init__(self, message: str = "User consent is stale or does not match revalidated price/itinerary.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="stale_consent", details=details)


class BookingInvalidPassengerError(BookingServiceError):
    def __init__(self, message: str = "Invalid passenger or contact details provided.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="invalid_passenger", details=details)


class BookingDuplicateError(BookingServiceError):
    def __init__(self, message: str = "An active booking for these passengers on this flight already exists.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="duplicate_booking", details=details)


class BookingProviderError(BookingServiceError):
    def __init__(self, message: str = "Flight provider order creation failed.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="provider_error", details=details)


class BookingProviderAmbiguousError(BookingServiceError):
    """
    Raised when provider order creation outcome is ambiguous:
    Timeouts, connection drops/resets, read failures, HTTP 500, 502, 503.
    Requires idempotency status='uncertain' and strictly prohibits blind retries.
    """
    def __init__(self, message: str = "Provider order creation outcome is uncertain. Blind retry prohibited.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="provider_uncertain", details=details)


class BookingProviderTimeoutError(BookingProviderAmbiguousError):
    def __init__(self, message: str = "Provider order creation timed out. Status uncertain; blind retry prohibited.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)
        self.code = "provider_timeout"


class BookingDatabaseError(BookingServiceError):
    def __init__(self, message: str = "Database transaction error occurred while persisting booking.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="database_error", details=details)


class BookingAccessDeniedError(BookingServiceError):
    def __init__(self, message: str = "Access to this booking is denied.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="access_denied", details=details)


# ===========================================================================
# BookingService Implementation
# ===========================================================================

class BookingService:
    """
    Coordinates end-to-end flight booking operations:
    - Pre-booking live offer revalidation
    - Explicit price-change detection and protection
    - Passenger profile and contact validation
    - Provider order creation (sandbox or mock simulation)
    - Privacy-compliant database persistence and history retrieval
    """

    def __init__(
        self,
        duffel_adapter: Optional[FlightProviderAdapter] = None,
        mock_adapter: Optional[FlightProviderAdapter] = None,
    ):
        self.duffel = duffel_adapter or DuffelFlightProviderAdapter()
        self.mock = mock_adapter or MockFlightProviderAdapter()

    def _resolve_adapter(self, offer: FlightOffer) -> FlightProviderAdapter:
        """
        Determines the appropriate provider adapter for an offer.
        Duffel offers are identified by 'duffel' in data_source or provider_offer_id prefix 'off_'.
        """
        if offer.data_source and offer.data_source.startswith("duffel"):
            return self.duffel
        if offer.provider_offer_id and offer.provider_offer_id.startswith("off_"):
            return self.duffel
        return self.mock

    async def revalidate_flight_offer(
        self,
        db: Session,
        flight_offer_id: int
    ) -> OfferRevalidationResponse:
        """
        Retrieves a stored flight offer and revalidates availability and pricing with the provider.
        """
        offer = db.query(FlightOffer).filter(FlightOffer.id == flight_offer_id).first()
        if not offer:
            raise BookingOfferNotFoundError(f"Flight offer with ID {flight_offer_id} not found.")

        adapter = self._resolve_adapter(offer)
        reval_result = await adapter.revalidate_offer(
            provider_offer_id=offer.provider_offer_id,
            expected_amount=offer.total_amount,
            currency=offer.currency
        )

        return OfferRevalidationResponse(
            flight_offer_id=offer.id,
            provider_offer_id=offer.provider_offer_id,
            is_valid=reval_result.get("is_valid", False),
            price_changed=reval_result.get("price_changed", False),
            current_amount=reval_result.get("current_amount", offer.total_amount),
            original_amount=reval_result.get("original_amount", offer.total_amount),
            currency=reval_result.get("currency", offer.currency),
            data_source=reval_result.get("data_source", offer.data_source),
            is_simulation=reval_result.get("is_simulation", False),
            expires_at=reval_result.get("expires_at"),
            message=reval_result.get("message")
        )

    def validate_booking_request(self, request: BookingCreateRequest) -> None:
        """
        Validates passenger and contact integrity before order submission.
        """
        if not request.confirmed_by_user:
            raise BookingMissingConsentError("Explicit user confirmation is mandatory to authorize flight booking.")

        if not request.passengers or len(request.passengers) < 1 or len(request.passengers) > 9:
            raise BookingInvalidPassengerError("A booking must contain between 1 and 9 passengers.")

        # Passenger name and identity check
        seen_passengers = set()
        for idx, p in enumerate(request.passengers):
            first = p.first_name.strip()
            last = p.last_name.strip()
            if not first or not last:
                raise BookingInvalidPassengerError(f"Passenger #{idx+1} has an empty first or last name.")
            key = (first.lower(), last.lower(), p.date_of_birth)
            if key in seen_passengers:
                raise BookingInvalidPassengerError(f"Duplicate passenger detected: {first} {last} ({p.date_of_birth}).")
            seen_passengers.add(key)

        # Contact validation
        if not request.contact.email or "@" not in request.contact.email:
            raise BookingInvalidPassengerError("A valid contact email is required.")
        if not request.contact.phone or len(request.contact.phone.strip()) < 7:
            raise BookingInvalidPassengerError("A valid contact phone number is required.")

    async def create_booking(
        self,
        db: Session,
        request: BookingCreateRequest,
        user_id: Optional[int] = None
    ) -> BookingResponse:
        """
        Executes the mandatory 13-step booking sequence:
        1. Receive selected flight offer ID.
        2. Retrieve offer from database.
        3. Confirm offer exists and belongs to expected provider.
        4. Revalidate offer with provider.
        5. Check expiry and availability.
        6. Compare live amount and currency against selected offer.
        7. If price changed without fresh approval, STOP.
        8. If offer is invalid or unavailable, STOP.
        9. Validate passenger and contact information.
        10. Require explicit confirmation for exact itinerary and amount.
        11. Create provider order only after all safety checks pass.
        12. Save actual provider response and booking status in database.
        13. Return structured booking response.
        """
        # Step 1 & 2: Retrieve offer from database
        offer = db.query(FlightOffer).filter(FlightOffer.id == request.flight_offer_id).first()
        if not offer:
            raise BookingOfferNotFoundError(f"Flight offer with ID {request.flight_offer_id} not found.")

        # Step 3: Resolve provider adapter
        adapter = self._resolve_adapter(offer)

        # Step 4: Retrieve latest offer from provider (revalidation)
        reval = await adapter.revalidate_offer(
            provider_offer_id=offer.provider_offer_id,
            expected_amount=offer.total_amount,
            currency=offer.currency
        )

        # Step 5 & 8: Check expiry and availability
        if not reval.get("is_valid", False):
            msg = reval.get("message") or "Flight offer is no longer available."
            if "expired" in msg.lower():
                raise BookingOfferExpiredError(msg)
            raise BookingOfferUnavailableError(msg)

        # Step 6 & 7: Check currency and price consistency
        current_amount = float(reval.get("current_amount", offer.total_amount))
        current_currency = reval.get("currency", offer.currency)

        # Currency mismatch check
        if current_currency.upper() != offer.currency.upper():
            raise BookingCurrencyMismatchError(
                f"Provider currency changed from {offer.currency} to {current_currency}.",
                expected_currency=offer.currency,
                current_currency=current_currency
            )

        # Price-change approval protection (Step 4 of specs)
        # Baseline expected amount is either user's explicitly passed expectation or the original offer total
        baseline_expected = request.expected_amount if request.expected_amount is not None else offer.total_amount
        price_changed = abs(current_amount - float(baseline_expected)) > 0.01

        if price_changed:
            # Check if user explicitly accepted the new price in this request
            can_proceed = (
                request.price_change_accepted is True
                and request.expected_amount is not None
                and abs(current_amount - request.expected_amount) <= 0.01
            )
            if not can_proceed:
                raise BookingPriceChangedError(
                    message=(
                        f"Flight price changed from {offer.currency} {baseline_expected:.2f} "
                        f"to {current_currency} {current_amount:.2f}. Fresh user confirmation required."
                    ),
                    original_amount=baseline_expected,
                    current_amount=current_amount,
                    currency=current_currency
                )

        # Step 9: Validate passenger and contact information
        self.validate_booking_request(request)

        # Step 10: Duplicate booking prevention
        # Check if an identical active booking already exists for this offer and contact
        existing_booking = db.query(Booking).filter(
            Booking.flight_offer_id == offer.id,
            Booking.status == "confirmed",
            Booking.contact_email == request.contact.email
        ).first()

        if existing_booking:
            existing_pax = existing_booking.passenger_details
            req_names = sorted([f"{p.first_name} {p.last_name}".lower() for p in request.passengers])
            ex_names = sorted([f"{p.get('first_name', '')} {p.get('last_name', '')}".lower() for p in existing_pax])
            if req_names == ex_names:
                raise BookingDuplicateError(
                    f"An active booking (Reference: {existing_booking.booking_reference}) "
                    f"already exists for these passengers on this flight offer."
                )

        # Step 11: Create provider order
        passengers_payload = [
            {
                "first_name": p.first_name,
                "last_name": p.last_name,
                "date_of_birth": p.date_of_birth,
                "gender": p.gender,
                "title": "mr" if p.gender == "male" else ("ms" if p.gender == "female" else "mr"),
                "passport_number": p.passport_number,
            }
            for p in request.passengers
        ]
        contact_payload = {
            "email": request.contact.email,
            "phone": request.contact.phone,
        }

        order_result = await adapter.create_order(
            provider_offer_id=offer.provider_offer_id,
            passengers=passengers_payload,
            contact=contact_payload,
            total_amount=current_amount,
            currency=current_currency
        )

        if not order_result.get("success", False):
            err_msg = order_result.get("error_message") or "Provider order creation failed."
            is_ambiguous = order_result.get("is_ambiguous", False)

            # 1. Timeout outcomes: Raise BookingProviderTimeoutError (inherits from BookingProviderAmbiguousError)
            if "timeout" in err_msg.lower() or "timed out" in err_msg.lower() or order_result.get("error_code") == "ambiguous_timeout":
                logger.error(f"Provider timed out while creating order for offer {offer.id}: {err_msg}")
                raise BookingProviderTimeoutError(
                    f"Flight provider timed out during order creation. Booking status is uncertain. Blind retry prohibited.",
                    details={"error_message": err_msg, "flight_offer_id": offer.id, "is_ambiguous": True}
                )

            # 2. Other ambiguous outcomes (connection drops, resets, 5xx server errors)
            if (
                is_ambiguous
                or "reset" in err_msg.lower()
                or "connection drop" in err_msg.lower()
                or "500" in err_msg
                or "502" in err_msg
                or "503" in err_msg
                or "504" in err_msg
            ):
                logger.error(f"Ambiguous provider outcome for offer {offer.id}: {err_msg}")
                raise BookingProviderAmbiguousError(
                    f"Flight provider returned an ambiguous outcome during order creation ({err_msg}). "
                    f"Booking status is uncertain. Blind retry prohibited.",
                    details={"error_message": err_msg, "flight_offer_id": offer.id, "is_ambiguous": True}
                )

            # 3. Definitive provider rejections (4xx client errors, invalid parameters)
            logger.error(f"Provider definitively rejected order creation for offer {offer.id}: {err_msg}")
            raise BookingProviderError(f"Provider order creation failed: {err_msg}", details=order_result)

        # Step 12: Save actual provider response and booking record in database
        provider_id = order_result.get("provider_booking_id")
        booking_record = Booking(
            user_id=user_id,
            flight_offer_id=offer.id,
            provider_booking_id=provider_id if provider_id else None,
            booking_reference=order_result.get("booking_reference"),
            provider_used=adapter.provider_name,
            data_source=order_result.get("data_source", adapter.data_source_type),
            is_simulation=order_result.get("is_simulation", False),
            status=order_result.get("status", "confirmed"),
            total_amount=order_result.get("total_amount", current_amount),
            currency=order_result.get("currency", current_currency),
            contact_email=request.contact.email,
            contact_phone=request.contact.phone,
            passenger_details_json=json.dumps([p.model_dump() for p in request.passengers]),
            raw_provider_order_json=json.dumps(order_result.get("raw_order") or {}),
            user_confirmed=True,
            confirmed_at=datetime.now(timezone.utc),
        )

        try:
            db.add(booking_record)
            db.commit()
            db.refresh(booking_record)
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.error(f"Failed to persist booking to database: {str(db_err)}")
            raise BookingDatabaseError(f"Database error while saving booking: {str(db_err)}")

        # Step 13: Return structured booking response
        return BookingResponse.model_validate(booking_record)

    def get_booking_by_id(
        self,
        db: Session,
        booking_id: int,
        user_id: Optional[int] = None
    ) -> BookingResponse:
        """
        Retrieves a booking by ID with ownership enforcement.
        Authenticated users can only access their own bookings.
        """
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise BookingNotFoundError(f"Booking with ID {booking_id} not found.")

        # Require authenticated user
        if user_id is None:
            raise BookingAccessDeniedError("Authentication is required to view booking details.")

        # Ownership check: User can only access their own bookings.
        # Guest bookings without user_id cannot be claimed or retrieved.
        if booking.user_id is None or booking.user_id != user_id:
            raise BookingAccessDeniedError("Access to this booking is forbidden.")

        return BookingResponse.model_validate(booking)

    def get_user_bookings(
        self,
        db: Session,
        user_id: int
    ) -> List[BookingSummaryResponse]:
        """
        Retrieves booking history for an authenticated user.
        STRICT PRIVACY GUARANTEE: Never exposes passport numbers, birth dates, or contact phones.
        Only returns high-level summary cards with passenger names and itinerary info.
        """
        bookings = (
            db.query(Booking)
            .filter(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
            .all()
        )
        return [BookingSummaryResponse.model_validate(b) for b in bookings]


# Service singleton instance
booking_service = BookingService()

