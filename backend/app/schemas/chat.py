"""
Pydantic schemas for Conversational AI Assistant dialogue, slot filling, and conversation history.
Complies with SRS FR-006 to FR-015, SAD Section 4.1, and Phase 3 Step 3 specifications.
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator, ValidationInfo

from app.schemas.flight import (
    FlightSearchRequest,
    FlightOfferSchema,
    FlightSearchResponse,
)

SUPPORTED_CABIN_CLASSES = {"economy", "premium_economy", "business", "first"}
SUPPORTED_TIME_PREFERENCES = {"morning", "afternoon", "evening", "night"}


class ChatMessageRequest(BaseModel):
    """
    User query submitted to the conversational assistant.
    Supports authenticated users and guest sessions.
    """
    conversation_id: Optional[int] = Field(None, description="Optional existing conversation ID")
    message: str = Field(..., max_length=2000, description="User's travel request or response")

    @field_validator("message", mode="before")
    @classmethod
    def validate_non_empty_message(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Message cannot be empty or contain only whitespace.")
        return v.strip()


class FlightCriteriaSlots(BaseModel):
    """
    Structured slot model maintaining travel criteria accumulated across dialogue turns.
    """
    origin: Optional[str] = Field(None, description="3-letter IATA origin airport code (e.g. BLR)")
    destination: Optional[str] = Field(None, description="3-letter IATA destination airport code (e.g. DEL)")
    departure_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Departure date (YYYY-MM-DD)")
    return_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Optional return date (YYYY-MM-DD)")
    passengers: int = Field(1, description="Number of passengers (1-9)")
    cabin_class: str = Field("economy", description="Travel class (economy, premium_economy, business, first)")
    preferred_time: Optional[str] = Field(None, description="Preferred departure time window (morning, afternoon, evening, night)")
    selected_flight_offer_id: Optional[int] = Field(None, description="Selected flight offer database ID")
    passenger_name: Optional[str] = Field(None, description="Passenger full name for booking")
    passenger_dob: Optional[str] = Field(None, description="Passenger birth date (YYYY-MM-DD)")
    passenger_gender: Optional[str] = Field(None, description="Passenger gender (male, female, other)")
    contact_email: Optional[str] = Field(None, description="Contact email for e-ticket delivery")
    contact_phone: Optional[str] = Field(None, description="Contact phone for booking alerts")
    use_saved_profile: Optional[bool] = Field(None, description="Whether user requested to use saved profile")

    @field_validator("preferred_time")
    @classmethod
    def validate_preferred_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        norm = v.strip().lower()
        if norm not in SUPPORTED_TIME_PREFERENCES:
            return None
        return norm

    @field_validator("origin", "destination")
    @classmethod
    def uppercase_and_validate_iata(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError(f"Invalid airport code '{v}'. Expected 3-letter IATA code (e.g. BLR, DEL, LHR).")
        return cleaned

    @field_validator("departure_date")
    @classmethod
    def check_departure_date_not_past(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is None:
            return None
        try:
            dep = datetime.strptime(v, "%Y-%m-%d").date()
            ref = (info.context.get("reference_date") if info and info.context else None) or date.today()
            if dep < ref:
                raise ValueError("Departure date cannot be in the past.")
        except ValueError as e:
            if "past" in str(e):
                raise e
            raise ValueError("Invalid date format. Expected YYYY-MM-DD.")
        return v

    @field_validator("passengers")
    @classmethod
    def validate_passenger_count(cls, v: int) -> int:
        if v < 1 or v > 9:
            raise ValueError("Passenger count must be between 1 and 9.")
        return v

    @field_validator("cabin_class")
    @classmethod
    def validate_cabin_class(cls, v: str) -> str:
        norm = v.strip().lower()
        if norm not in SUPPORTED_CABIN_CLASSES:
            supported = ", ".join(sorted(SUPPORTED_CABIN_CLASSES))
            raise ValueError(f"Unsupported cabin class '{v}'. Supported classes: {supported}.")
        return norm

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "FlightCriteriaSlots":
        """
        Ensures origin and destination are distinct and return date is not earlier than departure.
        """
        if self.origin and self.destination:
            if self.origin.strip().upper() == self.destination.strip().upper():
                raise ValueError("Origin and destination airports must be different.")

        if self.departure_date and self.return_date:
            try:
                dep = datetime.strptime(self.departure_date, "%Y-%m-%d").date()
                ret = datetime.strptime(self.return_date, "%Y-%m-%d").date()
                if ret < dep:
                    raise ValueError("Return date cannot be earlier than departure date.")
            except ValueError as e:
                raise e

        return self

    @property
    def missing_mandatory_fields(self) -> List[str]:
        """
        Returns list of mandatory slots required before a flight search can be executed.
        """
        missing: List[str] = []
        if not self.origin:
            missing.append("origin")
        if not self.destination:
            missing.append("destination")
        if not self.departure_date:
            missing.append("departure_date")
        return missing

    @property
    def is_complete(self) -> bool:
        """
        Returns True when origin, destination, and departure_date are all validly populated.
        """
        return len(self.missing_mandatory_fields) == 0

    def to_flight_search_request(self, reference_date: Optional[date] = None) -> FlightSearchRequest:
        """
        Converts validated slots into an executable FlightSearchRequest.
        Guarantees that mandatory fields cannot be missing.
        """
        if not self.is_complete:
            missing_str = ", ".join(self.missing_mandatory_fields)
            raise ValueError(f"Cannot create flight search request: missing mandatory fields ({missing_str}).")

        return FlightSearchRequest.model_validate(
            {
                "origin": self.origin,
                "destination": self.destination,
                "departure_date": self.departure_date,
                "return_date": self.return_date,
                "passengers": self.passengers,
                "cabin_class": self.cabin_class,
            },
            context={"reference_date": reference_date}
        )


class ChatMessageResponse(BaseModel):
    """
    Response returned by the assistant to the user.
    Includes natural language message, extracted slots, and flight offers when search executes.
    """
    conversation_id: int
    assistant_message: str
    slots: FlightCriteriaSlots = Field(default_factory=FlightCriteriaSlots)
    missing_fields: List[str] = Field(default_factory=list)
    search_status: str = Field("collecting_information", description="'collecting_information', 'search_executed', or 'clarification_needed'")
    flight_offers: Optional[List[FlightOfferSchema]] = None
    search_metadata: Optional[FlightSearchResponse] = None
    booking_workflow_state: str = Field("normal_chat", description="Current booking workflow state")
    selected_offer: Optional[FlightOfferSchema] = None
    booking_details: Optional[dict] = None
    booking_reference: Optional[str] = None


class MessageResponse(BaseModel):
    """
    Individual message response schema for conversation history.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    slots_json: Optional[str] = None
    flight_search_id: Optional[int] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    """
    Full conversation details including complete chronological message history.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = Field(default_factory=list)


class ConversationSummaryResponse(BaseModel):
    """
    Summary item for conversation sidebar drawer.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
