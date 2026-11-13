"""
Abstract Base Class for Flight Provider Adapters.
Complies with SAD Section 5.2 External Provider Adapter Contract.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.schemas.flight import FlightSearchRequest, FlightOfferSchema


class FlightProviderAdapter(ABC):
    """
    Abstract interface decoupling external flight distribution systems (Duffel, Amadeus, Mock)
    from core domain logic.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier of the provider (e.g. 'duffel', 'mock')"""
        pass

    @property
    @abstractmethod
    def data_source_type(self) -> str:
        """
        Compliance with Condition 2:
        Returns 'duffel_sandbox', 'duffel_production', or 'mock_simulation'
        """
        pass

    @abstractmethod
    async def search_offers(
        self,
        criteria: FlightSearchRequest
    ) -> List[FlightOfferSchema]:
        """
        Queries flight offers matching criteria and returns normalized internal schemas.
        """
        pass

    @abstractmethod
    async def get_offer_raw(
        self,
        provider_offer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves raw provider payload for revalidation or order creation.
        """
        pass

    @abstractmethod
    async def revalidate_offer(
        self,
        provider_offer_id: str,
        expected_amount: Optional[float] = None,
        currency: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Revalidates live offer availability, expiration, and pricing with the provider.
        
        Returns standardized dict:
        {
            'is_valid': bool,
            'price_changed': bool,
            'current_amount': float,
            'original_amount': float,
            'currency': str,
            'expires_at': Optional[datetime],
            'data_source': str,
            'is_simulation': bool,
            'message': str,
            'raw_offer': Optional[Dict[str, Any]]
        }
        """
        pass

    @abstractmethod
    async def create_order(
        self,
        provider_offer_id: str,
        passengers: List[Dict[str, Any]],
        contact: Dict[str, str],
        total_amount: float,
        currency: str
    ) -> Dict[str, Any]:
        """
        Submits booking order to the provider.
        
        Returns standardized dict:
        {
            'success': bool,
            'provider_booking_id': str,
            'booking_reference': Optional[str],
            'status': str,
            'total_amount': float,
            'currency': str,
            'data_source': str,
            'is_simulation': bool,
            'raw_order': Optional[Dict[str, Any]],
            'error_message': Optional[str]
        }
        """
        pass
