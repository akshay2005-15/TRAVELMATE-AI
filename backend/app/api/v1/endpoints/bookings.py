"""
FastAPI Endpoints for Flight Bookings and Offer Revalidation.
Exposes secure routes for:
- Live offer revalidation (POST /api/v1/bookings/revalidate)
- Flight booking creation with durable database idempotency & intent reservation (POST /api/v1/bookings)
- Authenticated user booking history (GET /api/v1/bookings)
- Booking detail retrieval with strict ownership enforcement (GET /api/v1/bookings/{booking_id})

Complies with Phase 4 Step 5 Final Hardening:
- Guest booking creation & retrieval disabled (401 Unauthorized for unauthenticated requests)
- Masked passport numbers in read representations
- Persistent database-backed idempotency via IdempotencyRecord
- Multi-worker concurrent intent reservation via BookingIntentReservation (UniqueConstraint on intent_key)
- Ambiguous error protection (timeouts, connection resets, HTTP 500/502/503) permanently locked as 'uncertain' (504)
- Zero blind retries for ambiguous outcomes
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.user import User
from app.models.idempotency import IdempotencyRecord, BookingIntentReservation
from app.schemas.booking import (
    BookingCreateRequest,
    BookingResponse,
    BookingSummaryResponse,
    OfferRevalidationRequest,
    OfferRevalidationResponse,
)
from app.services.booking_service import (
    booking_service,
    BookingServiceError,
    BookingNotFoundError,
    BookingOfferNotFoundError,
    BookingOfferExpiredError,
    BookingOfferUnavailableError,
    BookingPriceChangedError,
    BookingCurrencyMismatchError,
    BookingMissingConsentError,
    BookingStaleConsentError,
    BookingInvalidPassengerError,
    BookingDuplicateError,
    BookingProviderError,
    BookingProviderAmbiguousError,
    BookingProviderTimeoutError,
    BookingDatabaseError,
    BookingAccessDeniedError,
)
from app.api.deps import get_current_user, get_optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _compute_request_hash(req: BookingCreateRequest) -> str:
    """Computes a deterministic SHA-256 hash of the booking payload excluding client idempotency key."""
    payload_dict = req.model_dump(exclude={"idempotency_key"})
    canonical_json = json.dumps(payload_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _compute_intent_key(user_id: int, flight_offer_id: int, req: BookingCreateRequest) -> str:
    """
    Computes a normalized intent signature for the same user, flight offer, and passenger set.
    Prevents duplicate bookings and concurrent double-execution even across different idempotency keys.
    """
    pax_tokens = sorted([f"{p.first_name.lower().strip()}:{p.last_name.lower().strip()}:{p.date_of_birth}" for p in req.passengers])
    pax_hash = hashlib.sha256("|".join(pax_tokens).encode("utf-8")).hexdigest()
    return f"{user_id}_{flight_offer_id}_{pax_hash}"


def _resolve_idempotency_key(
    req: BookingCreateRequest,
    user_id: int,
    header_key: Optional[str] = None
) -> str:
    """Resolves client idempotency key from headers, body, or generates a deterministic auto-key."""
    if header_key and header_key.strip():
        return header_key.strip()
    if req.idempotency_key and req.idempotency_key.strip():
        return req.idempotency_key.strip()
    # Fallback deterministic key scoped per user and offer
    pax_tokens = sorted([f"{p.first_name.lower()}:{p.last_name.lower()}:{p.date_of_birth}" for p in req.passengers])
    pax_hash = hashlib.sha256("|".join(pax_tokens).encode()).hexdigest()[:16]
    return f"auto_{user_id}_{req.flight_offer_id}_{pax_hash}"


# ===========================================================================
# 1. Offer Revalidation Endpoint (Accessible without authentication)
# ===========================================================================

@router.post(
    "/revalidate",
    response_model=OfferRevalidationResponse,
    summary="Revalidate flight offer price and availability before booking"
)
async def revalidate_flight_offer(
    payload: OfferRevalidationRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Checks live offer availability, expiration, and pricing with the provider.
    Returns whether the price has changed or if the offer is no longer bookable.
    Never creates a booking from this endpoint.
    """
    try:
        return await booking_service.revalidate_flight_offer(db, payload.flight_offer_id)
    except BookingOfferNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except BookingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)


# ===========================================================================
# 2. Create Booking Endpoint (Strictly requires authentication & intent lock)
# ===========================================================================

@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a flight booking order with explicit consent and safety checks"
)
async def create_booking(
    req: BookingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_header: Optional[str] = Header(None, alias="X-Idempotency-Key")
):
    """
    Executes the 13-step booking sequence with complete idempotency and intent reservation:
    1. Authenticates current user (401 Unauthorized for guests).
    2. Enforces durable database idempotency per key (409 for in-progress, 422 for payload mismatch).
    3. Enforces durable intent reservation across different keys (409 for concurrent or duplicate bookings).
    4. Validates selected flight offer.
    5. Revalidates with provider for latest price/expiry.
    6. Blocks execution if price changed without fresh explicit approval.
    7. Validates passenger identities and disallows duplicates.
    8. Confirms explicit user consent.
    9. Dispatches order creation to provider (test sandbox or mock simulation).
    10. Persists confirmed booking with masked passport numbers and releases intent lock.
    """
    user_id = current_user.id
    chosen_header_key = idempotency_header or x_idempotency_header
    key = _resolve_idempotency_key(req, user_id, chosen_header_key)
    request_hash = _compute_request_hash(req)
    intent_key = _compute_intent_key(user_id, req.flight_offer_id, req)

    # -----------------------------------------------------------------------
    # Step A: Check Client Idempotency Record (Same-Key Protection)
    # -----------------------------------------------------------------------
    record = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.idempotency_key == key
        )
        .first()
    )

    if record:
        # Check for payload mismatch under identical key
        if record.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Idempotency key payload mismatch: This idempotency key was previously used with different request parameters."
            )

        if record.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A booking attempt with this idempotency key is currently processing. Please wait."
            )

        if record.status == "uncertain":
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "error_code": "provider_uncertain",
                    "message": (
                        "Previous booking attempt timed out or had an ambiguous outcome. "
                        "Status is uncertain; automatic retry prohibited. Please verify booking status or contact support."
                    )
                }
            )

        if record.status == "completed":
            # Replay cached booking response
            if record.booking_id:
                try:
                    return booking_service.get_booking_by_id(db, record.booking_id, user_id=user_id)
                except Exception:
                    pass
            if record.response_json:
                try:
                    return BookingResponse.model_validate(json.loads(record.response_json))
                except Exception:
                    pass

        if record.status == "failed":
            # Allow clean retry: reset to processing
            record.status = "processing"
            record.updated_at = datetime.now(timezone.utc)
            db.commit()
    else:
        # Create fresh idempotency record
        record = IdempotencyRecord(
            user_id=user_id,
            idempotency_key=key,
            request_hash=request_hash,
            status="processing"
        )
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
        except IntegrityError:
            db.rollback()
            record = (
                db.query(IdempotencyRecord)
                .filter(
                    IdempotencyRecord.user_id == user_id,
                    IdempotencyRecord.idempotency_key == key
                )
                .first()
            )
            if record and record.status == "processing":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A booking attempt with this idempotency key is currently processing. Please wait."
                )

    # -----------------------------------------------------------------------
    # Step B: Check Booking Intent Reservation (Cross-Key & Multi-Worker Lock)
    # -----------------------------------------------------------------------
    reservation = (
        db.query(BookingIntentReservation)
        .filter(BookingIntentReservation.intent_key == intent_key)
        .first()
    )

    if reservation:
        if reservation.status == "completed":
            _fail_lifecycle(db, record, None)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "duplicate_booking",
                    "message": "An active booking already exists for these passengers on this flight offer."
                }
            )

        if reservation.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "booking_in_progress",
                    "message": "A booking attempt for these passengers on this flight offer is currently processing. Please wait."
                }
            )

        if reservation.status == "uncertain":
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "error_code": "provider_uncertain",
                    "message": (
                        "A previous booking attempt for these passengers resulted in an uncertain provider outcome. "
                        "Automatic retry is prohibited to prevent duplicate ticketing. Please verify booking status or contact support."
                    )
                }
            )

        if reservation.status == "failed":
            # Previous attempt failed definitively; reclaim reservation for this attempt
            reservation.status = "processing"
            reservation.idempotency_key = key
            reservation.updated_at = datetime.now(timezone.utc)
            db.commit()
    else:
        # Create fresh intent reservation (UniqueConstraint on intent_key protects concurrent workers)
        pax_tokens = sorted([f"{p.first_name.lower().strip()}:{p.last_name.lower().strip()}:{p.date_of_birth}" for p in req.passengers])
        pax_hash = hashlib.sha256("|".join(pax_tokens).encode("utf-8")).hexdigest()
        reservation = BookingIntentReservation(
            user_id=user_id,
            flight_offer_id=req.flight_offer_id,
            passenger_hash=pax_hash,
            intent_key=intent_key,
            idempotency_key=key,
            status="processing"
        )
        db.add(reservation)
        try:
            db.commit()
            db.refresh(reservation)
        except IntegrityError:
            db.rollback()
            # Concurrent race condition: another application worker claimed intent_key in parallel!
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "booking_in_progress",
                    "message": "A booking attempt for these passengers on this flight offer is currently processing. Please wait."
                }
            )

    # -----------------------------------------------------------------------
    # Step C: Execute Booking through BookingService (No open DB locks held)
    # -----------------------------------------------------------------------
    try:
        booking = await booking_service.create_booking(db, req, user_id=user_id)

        # Mark both idempotency and intent reservation as completed
        try:
            if reservation:
                reservation.status = "completed"
                reservation.booking_id = booking.id
                reservation.updated_at = datetime.now(timezone.utc)
            if record:
                record.status = "completed"
                record.booking_id = booking.id
                record.response_json = booking.model_dump_json()
                record.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to finalize idempotency and reservation records for {key}: {e}")
            db.rollback()

        return booking

    except BookingOfferNotFoundError as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)

    except BookingOfferExpiredError as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error_code": "offer_expired", "message": exc.message}
        )

    except BookingOfferUnavailableError as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "offer_unavailable", "message": exc.message}
        )

    except BookingPriceChangedError as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "price_changed",
                "message": exc.message,
                "original_amount": exc.original_amount,
                "current_amount": exc.current_amount,
                "currency": exc.currency,
                "price_changed": True,
                "requires_fresh_confirmation": True
            }
        )

    except BookingCurrencyMismatchError as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "currency_mismatch",
                "message": exc.message,
                "expected_currency": exc.expected_currency,
                "current_currency": exc.current_currency
            }
        )

    except (BookingMissingConsentError, BookingStaleConsentError) as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": exc.code, "message": exc.message}
        )

    except BookingInvalidPassengerError as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "invalid_passenger", "message": exc.message}
        )

    except BookingDuplicateError as exc:
        # A confirmed booking already exists in database: set reservation to completed
        try:
            if reservation:
                reservation.status = "completed"
                reservation.updated_at = datetime.now(timezone.utc)
            if record:
                record.status = "failed"
                record.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "duplicate_booking", "message": exc.message}
        )

    except (BookingProviderTimeoutError, BookingProviderAmbiguousError) as exc:
        # Ambiguous provider outcomes (timeout, connection drop, 500/502/503):
        # Store 'uncertain' status on BOTH idempotency and intent reservation to prohibit blind retry
        _uncertain_lifecycle(db, record, reservation)
        logger.error(f"Ambiguous provider outcome during booking creation: {exc.message}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error_code": "provider_uncertain",
                "message": (
                    "Flight provider outcome is uncertain (connection drop, timeout, or server error). "
                    "Automated retry is prohibited for your safety to prevent duplicate ticketing or double-charging. "
                    "Please verify your booking status or contact support."
                ),
                "details": exc.details
            }
        )

    except BookingProviderError as exc:
        # Definitive provider rejections: Safe to mark failed and permit fresh attempt
        _fail_lifecycle(db, record, reservation)
        logger.error(f"Provider definitive rejection during booking creation: {exc.message}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "provider_error", "message": exc.message}
        )

    except BookingDatabaseError as exc:
        _fail_lifecycle(db, record, reservation)
        logger.error(f"Database error during booking creation: {exc.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "database_error", "message": "Failed to save booking. Please contact support."}
        )

    except BookingAccessDeniedError as exc:
        _fail_lifecycle(db, record, reservation)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "access_denied", "message": exc.message}
        )

    except BookingServiceError as exc:
        _fail_lifecycle(db, record, reservation)
        logger.error(f"Booking service error: {exc.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": exc.code, "message": exc.message}
        )


def _fail_lifecycle(
    db: Session,
    record: Optional[IdempotencyRecord],
    reservation: Optional[BookingIntentReservation]
) -> None:
    """Helper to mark both record and reservation as failed and allow clean subsequent attempts."""
    try:
        now = datetime.now(timezone.utc)
        if record:
            record.status = "failed"
            record.updated_at = now
        if reservation and reservation.status == "processing":
            reservation.status = "failed"
            reservation.updated_at = now
        db.commit()
    except Exception:
        db.rollback()


def _uncertain_lifecycle(
    db: Session,
    record: Optional[IdempotencyRecord],
    reservation: Optional[BookingIntentReservation]
) -> None:
    """Helper to lock both record and reservation in 'uncertain' status, permanently blocking blind retries."""
    try:
        now = datetime.now(timezone.utc)
        if record:
            record.status = "uncertain"
            record.updated_at = now
        if reservation:
            reservation.status = "uncertain"
            reservation.updated_at = now
        db.commit()
    except Exception:
        db.rollback()


# ===========================================================================
# 3. Booking History Endpoint (Strictly requires authentication)
# ===========================================================================

@router.get(
    "",
    response_model=List[BookingSummaryResponse],
    summary="Retrieve authenticated user booking history (Strict privacy enforced)"
)
def get_user_booking_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns chronological booking summaries for the currently authenticated user.
    Strict privacy requirement: Never exposes passport numbers, birth dates, or contact phone.
    """
    return booking_service.get_user_bookings(db, user_id=current_user.id)


# ===========================================================================
# 4. Booking Detail Endpoint (Strictly requires authentication)
# ===========================================================================

@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Retrieve single booking details with ownership verification"
)
def get_booking_detail(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves full booking details by ID.
    Enforces ownership:
    - Requires authenticated user (401 Unauthorized for guests).
    - An authenticated user cannot view another user's booking (403 Forbidden).
    - Legacy guest bookings cannot be retrieved (403 Forbidden).
    - Nonexistent bookings return 404 Not Found.
    - Passport numbers in response are masked (e.g. ****5678).
    """
    try:
        return booking_service.get_booking_by_id(db, booking_id, user_id=current_user.id)
    except BookingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message
        )
    except BookingAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this booking is forbidden."
        )
    except BookingServiceError as exc:
        if exc.code == "booking_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=exc.message
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
