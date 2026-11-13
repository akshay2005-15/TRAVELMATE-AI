"""
AgentState definition for LangGraph conversational orchestration.
Complies with SRS FR-006 to FR-015 and Phase 3 Step 4 specifications.
"""

from typing import List, Dict, Any, Optional, TypedDict


class AgentState(TypedDict):
    """
    State object passed between LangGraph nodes during conversational turns.
    Maintains dialogue history, current extracted slots, readiness flags, and provider results.
    """
    # Conversation thread history: [{"role": "user"|"assistant", "content": "..."}]
    messages: List[Dict[str, str]]
    
    # Latest user query
    user_message: str

    # Extracted user intent: 'search_flights', 'clarification_answer', 'greeting', 'general_inquiry', 'out_of_scope'
    intent: str

    # Accumulated travel criteria slots
    slots: Dict[str, Any]

    # Required fields not yet supplied: subset of ['origin', 'destination', 'departure_date']
    missing_fields: List[str]

    # Ready to execute flight provider tool
    search_ready: bool

    # Result payload from flight_service (FlightSearchResponse dict)
    flight_search_results: Optional[Dict[str, Any]]

    # Final assistant textual reply
    assistant_reply: str

    # Booking workflow state:
    # 'normal_chat', 'flight_selection_required', 'passenger_details_required',
    # 'booking_review_ready', 'booking_confirmation_required', 'booking_processing',
    # 'booking_confirmed', 'booking_uncertain', 'booking_failed',
    # 'price_change_requires_approval', 'authentication_required'
    booking_workflow_state: Optional[str]

    # Selected FlightOffer ID (internal database ID)
    selected_flight_offer_id: Optional[int]

    # Stored dictionary representation of the selected flight offer
    selected_offer: Optional[Dict[str, Any]]

    # Active PendingBookingConfirmation ID if in review/confirmation stage
    pending_confirmation_id: Optional[int]

    # Result payload upon booking execution (BookingResponse dict)
    booking_details: Optional[Dict[str, Any]]

    # Confirmed PNR or booking reference
    booking_reference: Optional[str]

    # Optional internal error message
    error: Optional[str]

