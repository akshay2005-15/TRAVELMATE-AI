"""
Conversational AI Engine package for TRAVELMATE AI.
Provides LangGraph state machine, intent & slot extractor, and flight search orchestration.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from sqlalchemy.orm import Session

from app.ai.state import AgentState
from app.ai.graph import flight_agent_graph, format_flight_offers_summary
from app.ai.extractor import (
    extract_slots_and_intent,
    rule_based_extract,
    parse_relative_date,
    parse_date_expression,
    extract_time_preference,
    extract_flight_selection_identifier,
    extract_passenger_and_contact_tokens
)
from app.ai.time_filter import (
    parse_local_departure_datetime,
    matches_departure_time_filter,
    filter_flight_offers_by_time
)


async def run_flight_agent(
    user_message: str,
    current_slots: Optional[Dict[str, Any]] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
    force_fallback: bool = False,
    reference_date: Optional[date] = None
) -> AgentState:
    """
    Public execution entry point for the TRAVELMATE AI Conversational Agent.
    Runs the LangGraph state machine workflow across conversational turns.
    """
    initial_state: AgentState = {
        "messages": list(messages or []),
        "user_message": user_message.strip(),
        "intent": "unknown",
        "slots": dict(current_slots or {}),
        "missing_fields": [],
        "search_ready": False,
        "flight_search_results": None,
        "assistant_reply": "",
        "booking_workflow_state": "normal_chat",
        "selected_flight_offer_id": current_slots.get("selected_flight_offer_id") if current_slots else None,
        "selected_offer": None,
        "pending_confirmation_id": None,
        "booking_details": None,
        "booking_reference": None,
        "error": None
    }

    config = {
        "configurable": {
            "db": db,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "force_fallback": force_fallback,
            "reference_date": reference_date
        }
    }

    final_state = await flight_agent_graph.ainvoke(initial_state, config=config)
    return final_state


__all__ = [
    "AgentState",
    "flight_agent_graph",
    "run_flight_agent",
    "format_flight_offers_summary",
    "extract_slots_and_intent",
    "rule_based_extract",
    "parse_relative_date",
    "parse_date_expression",
    "extract_time_preference",
    "parse_local_departure_datetime",
    "matches_departure_time_filter",
    "filter_flight_offers_by_time"
]

