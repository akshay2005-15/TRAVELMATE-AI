"""
Pydantic schemas for flight search, offers, and airport resolution.
Complies with SRS FR-022 to FR-027 and User Condition 2.
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator, ValidationInfo


class FlightSearchRequest(BaseModel):
    """
    Search parameters submitted by user or conversational AI agent.
    """
    origin: str = Field(..., min_length=3, max_length=3, description="3-letter IATA code, e.g. BLR, DEL, LHR")
    destination: str = Field(..., min_length=3, max_length=3, description="3-letter IATA code, e.g. BOM, JFK")
    departure_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Departure date (YYYY-MM-DD)")
    return_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Optional return date")
    passengers: int = Field(1, ge=1, le=9, description="Passenger count (1-9)")
    cabin_class: str = Field("economy", description="economy, premium_economy, business, or first")
    force_provider: Optional[str] = Field(None, description="Optional override: 'duffel' or 'mock'")

    @field_validator("origin", "destination")
    @classmethod
    def uppercase_iata(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("departure_date")
    @classmethod
    def check_departure_date_not_past(cls, v: str, info: ValidationInfo) -> str:
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

    @model_validator(mode="after")
    def validate_route_and_return_date(self) -> "FlightSearchRequest":
        """
        Cross-field validation:
        1. Ensures origin and destination are distinct (case-insensitive).
        2. Ensures return date is not before departure date.
        """
        if self.origin and self.destination:
            if self.origin.strip().upper() == self.destination.strip().upper():
                raise ValueError("Origin and destination airports must be different.")

        if self.return_date:
            try:
                dep = datetime.strptime(self.departure_date, "%Y-%m-%d").date()
                ret = datetime.strptime(self.return_date, "%Y-%m-%d").date()
                if ret < dep:
                    raise ValueError("Return date cannot be earlier than departure date.")
            except ValueError as e:
                raise e

        return self



class FlightOfferSchema(BaseModel):
    """
    Normalized representation of a flight offer returned from a provider or simulation.
    Condition 2: Explicitly tags `data_source` and `is_simulation`.
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    provider_offer_id: str
    airline_name: str
    airline_code: str
    flight_number: str
    origin_iata: str
    destination_iata: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    stops: int
    stop_details: Optional[str] = None
    total_amount: float
    currency: str = "INR"
    cabin_class: str = "economy"
    baggage_included: Optional[str] = None
    
    # Transparency & Condition 2 flags
    data_source: str  # 'duffel_sandbox', 'duffel_production', 'mock_simulation'
    is_simulation: bool = False
    expires_at: Optional[datetime] = None

    @property
    def duration_formatted(self) -> str:
        hours = self.duration_minutes // 60
        mins = self.duration_minutes % 60
        return f"{hours}h {mins}m"


class FlightSearchResponse(BaseModel):
    """
    Encapsulates flight search metadata and list of ranked offers.
    """
    search_id: int
    origin_iata: str
    destination_iata: str
    departure_date: str
    return_date: Optional[str] = None
    passenger_count: int
    cabin_class: str
    provider_used: str
    data_source: str
    is_simulation: bool
    total_offers: int
    offers: List[FlightOfferSchema]


class AirportInfo(BaseModel):
    """
    Airport directory entry for IATA code lookup and autocomplete.
    """
    iata_code: str
    city_name: str
    airport_name: str
    country: str
