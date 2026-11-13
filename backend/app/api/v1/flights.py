"""
Flight search and discovery API endpoints.
Complies with SRS FR-022 to FR-027 and User Condition 2.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.flight import (
    FlightSearchRequest,
    FlightSearchResponse,
    AirportInfo
)
from app.services.flight_service import flight_service
from app.adapters.airports import search_airports
from app.api.deps import get_optional_current_user

router = APIRouter(prefix="/flights", tags=["Flights"])


@router.post(
    "/search",
    response_model=FlightSearchResponse,
    summary="Search flight offers (FR-022, FR-023)"
)
async def search_flights(
    criteria: FlightSearchRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Submits flight search criteria to configured flight provider (Duffel API or Mock fallback).
    Condition 2: Every returned offer is explicitly labeled with data_source and is_simulation.
    """
    user_id = current_user.id if current_user else None
    return await flight_service.execute_search(db, criteria, user_id=user_id)


@router.get(
    "/searches/{search_id}",
    response_model=FlightSearchResponse,
    summary="Retrieve previously stored flight search results"
)
def get_flight_search(
    search_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Retrieves stored search results and flight offers.
    """
    user_id = current_user.id if current_user else None
    result = flight_service.get_search_by_id(db, search_id, user_id=user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight search record with ID {search_id} was not found."
        )
    return result


@router.get(
    "/airports",
    response_model=List[AirportInfo],
    summary="Search airports and cities for autocomplete"
)
def get_airports(
    q: str = Query("", description="Search term for city, airport name, or IATA code")
):
    """
    Returns matching airports for dropdown autocomplete.
    """
    return search_airports(q, limit=12)


@router.get(
    "/provider-status",
    summary="Get active flight provider configuration status"
)
def get_provider_status():
    """
    Returns provider configuration and active data source.
    """
    return {
        "configured_provider": settings.FLIGHT_PROVIDER,
        "duffel_available": flight_service.duffel.is_configured,
        "duffel_environment": flight_service.duffel.data_source_type,
        "mock_fallback_enabled": True
    }
