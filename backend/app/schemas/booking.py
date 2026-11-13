"""
Pydantic schemas for Flight Booking workflows, passenger validation, and offer revalidation.
Complies with SRS Section 6 Data Requirements and Phase 4 Step 2 specifications.
"""

from datetime import datetime, date
import re
import json
from typing import Optional, List, Any
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    field_validator,
    model_validator
)

from app.schemas.flight import FlightOfferSchema


def mask_passport_number(val: Optional[str]) -> Optional[str]:
    """
    Masks a passport number for privacy in serialized read representations.
    Shows only the final four characters (e.g. '****5678' or '****' if 4 or fewer characters).
    Returns None if val is None or empty.
    """
    if val is None:
        return None
    clean = str(val).strip()
    if not clean:
        return None
    if len(clean) <= 4:
        return "****"
    return f"****{clean[-4:]}"


class PassengerBookingDetails(BaseModel):
    """
    Validated passenger profile details required to ticket a flight.
    Passport is optional unless required by international carriers.
    Strictly forbids storing payment cards or financial credentials.
    """
    model_config = ConfigDict(from_attributes=True)

    first_name: str = Field(..., min_length=1, max_length=100, description="Passenger given name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Passenger family name")
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date of birth (YYYY-MM-DD)")
    gender: Optional[str] = Field("other", description="'male', 'female', or 'other'")
    passport_number: Optional[str] = Field(None, max_length=50, description="Optional passport number for international flights")

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Name cannot be empty or blank.")
        if len(clean) < 1:
            raise ValueError("Name must have at least 1 character.")
        return clean

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        try:
            dob = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid date of birth format. Expected YYYY-MM-DD.")
        today = date.today()
        if dob >= today:
            raise ValueError("Date of birth must be in the past.")
        if (today.year - dob.year) > 125:
            raise ValueError("Date of birth indicates an age over 125 years.")
        return v

    @field_validator("gender")
    @classmethod
    def normalize_gender(cls, v: Optional[str]) -> str:
        if not v:
            return "other"
        clean = v.strip().lower()
        if clean not in ["male", "female", "other"]:
            raise ValueError("Gender must be 'male', 'female', or 'other'.")
        return clean

    @field_validator("passport_number")
    @classmethod
    def clean_passport(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().upper()
            return clean or None
        return None


class BookingContactDetails(BaseModel):
    """
    Primary contact information for booking confirmations and e-ticket delivery.
    """
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr = Field(..., description="Contact email address for booking updates and e-ticket delivery")
    phone: str = Field(..., min_length=7, max_length=20, description="Contact phone number with country code")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean = v.strip()
        if not re.match(r"^\+?[\d\s\-()]{7,20}$", clean):
            raise ValueError("Invalid phone number format. Must contain 7-20 digits.")
        digits_only = re.sub(r"\D", "", clean)
        if len(digits_only) < 7:
            raise ValueError("Phone number must contain at least 7 digits.")
        return clean


class BookingCreateRequest(BaseModel):
    """
    Client booking request payload.
    Enforces explicit user authorization/consent before any booking can be initiated.
    Strictly forbids payment-card credentials.
    """
    flight_offer_id: int = Field(..., gt=0, description="Internal ID of the selected FlightOffer")
    passengers: List[PassengerBookingDetails] = Field(..., min_length=1, max_length=9, description="List of 1 to 9 passengers")
    contact: BookingContactDetails = Field(..., description="Primary contact details")
    confirmed_by_user: bool = Field(..., description="Mandatory explicit user consent to book this itinerary")
    expected_amount: Optional[float] = Field(None, description="Expected total amount confirmed by user for price protection")
    expected_currency: Optional[str] = Field(None, description="Expected currency confirmed by user")
    price_change_accepted: bool = Field(False, description="Flag explicitly confirming acceptance of a previously notified price change")
    idempotency_key: Optional[str] = Field(None, max_length=100, description="Optional client idempotency key to prevent duplicate booking attempts")

    @field_validator("confirmed_by_user")
    @classmethod
    def require_user_consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Explicit user consent and confirmation are required to authorize flight booking.")
        return v

    @model_validator(mode="after")
    def validate_passenger_uniqueness(self) -> "BookingCreateRequest":
        # Disallow duplicate passenger identities on the same flight booking
        seen = set()
        for p in self.passengers:
            key = (p.first_name.lower(), p.last_name.lower(), p.date_of_birth)
            if key in seen:
                raise ValueError(f"Duplicate passenger detected: {p.first_name} {p.last_name} ({p.date_of_birth}).")
            seen.add(key)
        return self


class BookingResponse(BaseModel):
    """
    Full confirmed booking details returned upon successful creation or retrieval.
    Includes itinerary, ticket reference, and passenger details.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_reference: Optional[str] = None  # PNR code, only when supplied by provider
    provider_booking_id: Optional[str] = None
    provider_used: str
    data_source: str  # 'duffel_sandbox', 'mock_simulation'
    is_simulation: bool
    status: str  # 'confirmed', 'pending_confirmation', 'cancelled', 'failed'
    total_amount: float
    currency: str = "INR"
    contact_email: str
    contact_phone: str
    passengers: List[PassengerBookingDetails]
    flight_offer: Optional[FlightOfferSchema] = None
    airline_name: Optional[str] = None
    airline_code: Optional[str] = None
    flight_number: Optional[str] = None
    origin_iata: Optional[str] = None
    destination_iata: Optional[str] = None
    departure_time: Optional[str] = None
    departure_date: Optional[str] = None
    arrival_time: Optional[str] = None
    stops: Optional[int] = 0
    cabin_class: Optional[str] = None
    baggage_included: Optional[str] = None
    user_confirmed: bool
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_passengers_from_orm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "passenger_details_json" in data and "passengers" not in data:
                try:
                    p_json = data["passenger_details_json"]
                    data["passengers"] = json.loads(p_json) if isinstance(p_json, str) else p_json
                except Exception:
                    data["passengers"] = []
            offer_dict = data.get("flight_offer")
            if isinstance(offer_dict, dict):
                data.setdefault("airline_name", offer_dict.get("airline_name"))
                data.setdefault("airline_code", offer_dict.get("airline_code"))
                data.setdefault("flight_number", offer_dict.get("flight_number"))
                data.setdefault("origin_iata", offer_dict.get("origin_iata"))
                data.setdefault("destination_iata", offer_dict.get("destination_iata"))
                dep_t = offer_dict.get("departure_time")
                data.setdefault("departure_time", dep_t)
                if dep_t and "departure_date" not in data:
                    data["departure_date"] = dep_t.split("T")[0] if "T" in str(dep_t) else str(dep_t)
                data.setdefault("arrival_time", offer_dict.get("arrival_time"))
                data.setdefault("stops", offer_dict.get("stops", 0))
                data.setdefault("cabin_class", offer_dict.get("cabin_class"))
                data.setdefault("baggage_included", offer_dict.get("baggage_included"))
            return data

        if hasattr(data, "passenger_details_json"):
            # SQLAlchemy ORM object
            p_json = getattr(data, "passenger_details_json", None)
            passengers = []
            if p_json:
                try:
                    passengers = json.loads(p_json)
                except Exception:
                    passengers = []
            
            offer = getattr(data, "flight_offer", None)
            offer_schema = None
            if offer:
                try:
                    offer_schema = FlightOfferSchema.model_validate(offer)
                except Exception:
                    pass

            dep_time = offer.departure_time if offer else None
            arr_time = offer.arrival_time if offer else None
            dep_date = None
            if dep_time:
                dep_date = dep_time.split("T")[0] if "T" in str(dep_time) else str(dep_time)

            return {
                "id": data.id,
                "booking_reference": data.booking_reference,
                "provider_booking_id": data.provider_booking_id,
                "provider_used": data.provider_used,
                "data_source": data.data_source,
                "is_simulation": data.is_simulation,
                "status": data.status,
                "total_amount": data.total_amount,
                "currency": data.currency,
                "contact_email": data.contact_email,
                "contact_phone": data.contact_phone,
                "passengers": passengers,
                "flight_offer": offer_schema,
                "airline_name": offer.airline_name if offer else None,
                "airline_code": offer.airline_code if offer else None,
                "flight_number": offer.flight_number if offer else None,
                "origin_iata": offer.origin_iata if offer else None,
                "destination_iata": offer.destination_iata if offer else None,
                "departure_time": dep_time,
                "departure_date": dep_date,
                "arrival_time": arr_time,
                "stops": offer.stops if offer else 0,
                "cabin_class": offer.cabin_class if offer else None,
                "baggage_included": offer.baggage_included if offer else None,
                "user_confirmed": data.user_confirmed,
                "confirmed_at": data.confirmed_at,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data

    @field_validator("passengers", mode="after")
    @classmethod
    def mask_passports_in_passengers(cls, v: List[PassengerBookingDetails]) -> List[PassengerBookingDetails]:
        """Ensures passport numbers are masked in read representations."""
        masked_list = []
        for p in v:
            if p.passport_number:
                # Copy or update with masked passport
                masked_p = p.model_copy(update={"passport_number": mask_passport_number(p.passport_number)})
                masked_list.append(masked_p)
            else:
                masked_list.append(p)
        return masked_list


class BookingSummaryResponse(BaseModel):
    """
    Ordinary booking history response.
    STRICT SECURITY REQUIREMENT: Never exposes passport numbers, birth dates, or phone numbers.
    Only shows safe trip summaries and passenger names.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_reference: Optional[str] = None
    status: str
    airline_name: Optional[str] = None
    airline_code: Optional[str] = None
    flight_number: Optional[str] = None
    origin_iata: Optional[str] = None
    destination_iata: Optional[str] = None
    departure_time: Optional[str] = None
    departure_date: Optional[str] = None
    arrival_time: Optional[str] = None
    stops: Optional[int] = 0
    passenger_count: int
    passenger_names: List[str]  # Name only (e.g. ["John Doe", "Jane Doe"])
    total_amount: float
    currency: str = "INR"
    data_source: str
    is_simulation: bool
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_summary_from_orm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "passenger_details_json" in data and ("passenger_names" not in data or "passenger_count" not in data):
                p_json = data.get("passenger_details_json")
                names = []
                if p_json:
                    try:
                        parsed = json.loads(p_json) if isinstance(p_json, str) else p_json
                        for p in parsed:
                            first = p.get("first_name", "").strip()
                            last = p.get("last_name", "").strip()
                            name = f"{first} {last}".strip()
                            if name:
                                names.append(name)
                    except Exception:
                        pass
                data["passenger_names"] = names
                data["passenger_count"] = len(names) or 1
            dep_t = data.get("departure_time")
            if dep_t and "departure_date" not in data:
                data["departure_date"] = dep_t.split("T")[0] if "T" in str(dep_t) else str(dep_t)
            return data

        if hasattr(data, "passenger_details_json"):
            # SQLAlchemy ORM object
            p_json = getattr(data, "passenger_details_json", None)
            names = []
            if p_json:
                try:
                    parsed = json.loads(p_json)
                    for p in parsed:
                        first = p.get("first_name", "").strip()
                        last = p.get("last_name", "").strip()
                        name = f"{first} {last}".strip()
                        if name:
                            names.append(name)
                except Exception:
                    pass

            offer = getattr(data, "flight_offer", None)
            dep_time = offer.departure_time if offer else None
            arr_time = offer.arrival_time if offer else None
            dep_date = None
            if dep_time:
                dep_date = dep_time.split("T")[0] if "T" in str(dep_time) else str(dep_time)

            return {
                "id": data.id,
                "booking_reference": data.booking_reference,
                "status": data.status,
                "airline_name": offer.airline_name if offer else None,
                "airline_code": offer.airline_code if offer else None,
                "flight_number": offer.flight_number if offer else None,
                "origin_iata": offer.origin_iata if offer else None,
                "destination_iata": offer.destination_iata if offer else None,
                "departure_time": dep_time,
                "departure_date": dep_date,
                "arrival_time": arr_time,
                "stops": offer.stops if offer else 0,
                "passenger_count": len(names) or 1,
                "passenger_names": names,
                "total_amount": data.total_amount,
                "currency": data.currency,
                "data_source": data.data_source,
                "is_simulation": data.is_simulation,
                "created_at": data.created_at,
            }
        return data


class OfferRevalidationRequest(BaseModel):
    """
    Request to verify live offer price and availability before booking.
    """
    flight_offer_id: int = Field(..., gt=0, description="Internal ID of the FlightOffer to revalidate")


class OfferRevalidationResponse(BaseModel):
    """
    Results of flight offer revalidation.
    Alerts client if price changed or offer expired before booking authorization.
    """
    flight_offer_id: int
    provider_offer_id: str
    is_valid: bool
    price_changed: bool = False
    current_amount: float
    original_amount: float
    currency: str = "INR"
    data_source: str
    is_simulation: bool = False
    expires_at: Optional[datetime] = None
    message: Optional[str] = None
