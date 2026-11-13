"""
Flight Search Orchestration Service.
Coordinates provider adapter selection, search persistence, and offer normalization.
Complies with SRS FR-022 to FR-027, SAD Section 3 & 4.1, and User Conditions 1, 2, 3.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import json

from app.core.config import settings
from app.models.flight import FlightSearch, FlightOffer
from app.schemas.flight import (
    FlightSearchRequest,
    FlightSearchResponse,
    FlightOfferSchema,
    AirportInfo
)
from app.adapters.base import FlightProviderAdapter
from app.adapters.duffel_adapter import DuffelFlightProviderAdapter
from app.adapters.mock_adapter import MockFlightProviderAdapter
from app.adapters.airports import search_airports, resolve_iata


class FlightService:
    def __init__(
        self,
        duffel_adapter: Optional[FlightProviderAdapter] = None,
        mock_adapter: Optional[FlightProviderAdapter] = None
    ):
        self.duffel = duffel_adapter or DuffelFlightProviderAdapter()
        self.mock = mock_adapter or MockFlightProviderAdapter()

    async def execute_search(
        self,
        db: Session,
        criteria: FlightSearchRequest,
        user_id: Optional[int] = None
    ) -> FlightSearchResponse:
        """
        Executes a flight search against the configured provider with automatic mock fallback.
        Persists search parameters and normalized offers to the database.
        """
        chosen_adapter: FlightProviderAdapter
        offers: List[FlightOfferSchema] = []

        # Determine provider based on override or system configuration
        if criteria.force_provider == "mock":
            chosen_adapter = self.mock
            offers = await self.mock.search_offers(criteria)
        elif criteria.force_provider == "duffel":
            chosen_adapter = self.duffel
            offers = await self.duffel.search_offers(criteria)
        else:
            # Main objective (Condition 1): Try Duffel first if configured
            if settings.FLIGHT_PROVIDER == "duffel" and self.duffel.is_configured:
                chosen_adapter = self.duffel
                offers = await self.duffel.search_offers(criteria)
                # Fallback to mock only if Duffel returns no offers (Condition 3)
                if not offers:
                    chosen_adapter = self.mock
                    offers = await self.mock.search_offers(criteria)
            else:
                chosen_adapter = self.mock
                offers = await self.mock.search_offers(criteria)

        # Create persistent search record
        search_record = FlightSearch(
            user_id=user_id,
            origin_iata=criteria.origin,
            destination_iata=criteria.destination,
            departure_date=criteria.departure_date,
            return_date=criteria.return_date,
            passenger_count=criteria.passengers,
            cabin_class=criteria.cabin_class,
            provider_used=chosen_adapter.provider_name,
            data_source=chosen_adapter.data_source_type
        )
        db.add(search_record)
        db.flush()  # obtain search_record.id

        # Persist normalized offers
        offer_schemas_with_ids: List[FlightOfferSchema] = []

        for off in offers:
            offer_record = FlightOffer(
                search_id=search_record.id,
                provider_offer_id=off.provider_offer_id,
                airline_name=off.airline_name,
                airline_code=off.airline_code,
                flight_number=off.flight_number,
                origin_iata=off.origin_iata,
                destination_iata=off.destination_iata,
                departure_time=off.departure_time,
                arrival_time=off.arrival_time,
                duration_minutes=off.duration_minutes,
                stops=off.stops,
                stop_details=off.stop_details,
                total_amount=off.total_amount,
                currency=off.currency,
                cabin_class=off.cabin_class,
                baggage_included=off.baggage_included,
                data_source=off.data_source,
                raw_offer_json=json.dumps({"provider_offer_id": off.provider_offer_id, "data_source": off.data_source}),
                expires_at=off.expires_at
            )
            db.add(offer_record)
            db.flush()

            # Copy ID to returned schema
            off_dict = off.model_dump()
            off_dict["id"] = offer_record.id
            offer_schemas_with_ids.append(FlightOfferSchema(**off_dict))

        db.commit()

        return FlightSearchResponse(
            search_id=search_record.id,
            origin_iata=search_record.origin_iata,
            destination_iata=search_record.destination_iata,
            departure_date=search_record.departure_date,
            return_date=search_record.return_date,
            passenger_count=search_record.passenger_count,
            cabin_class=search_record.cabin_class,
            provider_used=search_record.provider_used,
            data_source=search_record.data_source,
            is_simulation=chosen_adapter.data_source_type == "mock_simulation",
            total_offers=len(offer_schemas_with_ids),
            offers=offer_schemas_with_ids
        )

    @staticmethod
    def get_search_by_id(
        db: Session,
        search_id: int,
        user_id: Optional[int] = None
    ) -> Optional[FlightSearchResponse]:
        """
        Retrieves saved search results and associated offers by search ID.
        """
        query = db.query(FlightSearch).filter(FlightSearch.id == search_id)
        if user_id:
            query = query.filter((FlightSearch.user_id == user_id) | (FlightSearch.user_id.is_(None)))

        search = query.first()
        if not search:
            return None

        offer_schemas = [
            FlightOfferSchema(
                id=o.id,
                provider_offer_id=o.provider_offer_id,
                airline_name=o.airline_name,
                airline_code=o.airline_code,
                flight_number=o.flight_number,
                origin_iata=o.origin_iata,
                destination_iata=o.destination_iata,
                departure_time=o.departure_time,
                arrival_time=o.arrival_time,
                duration_minutes=o.duration_minutes,
                stops=o.stops,
                stop_details=o.stop_details,
                total_amount=o.total_amount,
                currency=o.currency,
                cabin_class=o.cabin_class,
                baggage_included=o.baggage_included,
                data_source=o.data_source,
                is_simulation=o.data_source == "mock_simulation",
                expires_at=o.expires_at
            )
            for o in search.offers
        ]

        return FlightSearchResponse(
            search_id=search.id,
            origin_iata=search.origin_iata,
            destination_iata=search.destination_iata,
            departure_date=search.departure_date,
            return_date=search.return_date,
            passenger_count=search.passenger_count,
            cabin_class=search.cabin_class,
            provider_used=search.provider_used,
            data_source=search.data_source,
            is_simulation=search.data_source == "mock_simulation",
            total_offers=len(offer_schemas),
            offers=offer_schemas
        )


flight_service = FlightService()
