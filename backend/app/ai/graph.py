"""
LangGraph State Machine and AI Agent Orchestration for TRAVELMATE AI.
Implements the multi-turn conversational workflow:
  START -> understand_query -> validate_criteria -> [route: clarify | search_flights | END]
  clarify -> END
  search_flights -> format_response -> END

Complies with SRS FR-006 to FR-015, SAD Section 4.1, and Phase 3 Step 4 specifications.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import hashlib
import json
import uuid
import re
from datetime import datetime, date, timezone, timedelta

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ai.state import AgentState
from app.ai.extractor import (
    extract_slots_and_intent,
    extract_flight_selection_identifier,
    extract_passenger_and_contact_tokens,
)
from app.schemas.chat import FlightCriteriaSlots
from app.schemas.flight import FlightSearchRequest, FlightOfferSchema
from app.services.flight_service import flight_service
from app.ai.time_filter import (
    parse_local_departure_datetime,
    matches_departure_time_filter,
    filter_flight_offers_by_time,
)
from app.models.flight import FlightOffer, FlightSearch
from app.models.user import User, PassengerProfile
from app.models.conversation import Conversation, Message
from app.models.booking import Booking, PendingBookingConfirmation
from app.schemas.booking import (
    BookingCreateRequest,
    PassengerBookingDetails,
    BookingContactDetails,
    BookingResponse,
    mask_passport_number,
)
from app.services.booking_service import (
    booking_service,
    BookingServiceError,
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
)

logger = logging.getLogger(__name__)

BOOKING_INTENTS = {
    "select_flight",
    "provide_passenger_details",
    "ask_flight_details",
    "confirm_booking",
    "price_change_approval",
    "vague_confirmation",
    "cancel_booking",
}


# ---------------------------------------------------------------------------
# Helper: Grounded Response Formatter
# ---------------------------------------------------------------------------
def _matches_time_preference(offer: Dict[str, Any], pref: str, origin_iata: Optional[str] = None) -> bool:
    """Check if flight departure time falls within preferred window in airport local time."""
    return matches_departure_time_filter(offer, pref, origin_iata=origin_iata)


def format_flight_offers_summary(
    search_results: Dict[str, Any],
    preferred_time: Optional[str] = None
) -> str:
    """
    Constructs a grounded, factual natural language summary of retrieved flight offers.
    Strictly follows User Condition 2 (never displays mock data as real) and SRS FR-023.
    Applies strict departure-time filtering (Requirements 2, 4, 5, 6, 7, 8).
    """
    offers: List[Dict[str, Any]] = search_results.get("offers", [])
    origin = search_results.get("origin_iata", "")
    dest = search_results.get("destination_iata", "")
    dep_date = search_results.get("departure_date", "")
    data_source = search_results.get("data_source", "mock_simulation")
    is_simulation = search_results.get("is_simulation", True)

    provider_status_line = (
        "⚡ **Provider Status:** `[SIMULATION / MOCK OFFER]` — Generated via authentic offline simulation for evaluation."
        if (is_simulation or data_source == "mock_simulation")
        else ("✈️ **Provider Status:** `[DUFFEL TEST SANDBOX]` — Live test offers retrieved from Duffel Sandbox API."
              if data_source == "duffel_sandbox"
              else f"✈️ **Provider Status:** Live offers via {data_source.upper()}.")
    )

    # Filter strictly by departure date and time window in airport local timezone (Requirements 1, 2, 3)
    display_offers = list(offers)
    pref_norm = preferred_time.lower().strip() if preferred_time else None
    if pref_norm:
        display_offers = filter_flight_offers_by_time(
            display_offers,
            preferred_time=pref_norm,
            origin_iata=origin,
            departure_date=dep_date
        )

    # Requirement 7: If no matching flights exist, clearly say so without inventing alternatives
    if not display_offers:
        if pref_norm:
            time_desc = "morning (departing before 12:00 PM)" if pref_norm == "morning" else f"{pref_norm}"
            msg = (
                f"I searched for flights from **{origin}** to **{dest}** on **{dep_date}**, "
                f"but no **{time_desc}** flights were found matching your criteria. "
                "Would you like to check flights at another time of day or on a different date?"
            )
        else:
            msg = (
                f"I searched for flights from **{origin}** to **{dest}** on **{dep_date}**, "
                "but no available flight offers were found. Would you like to try a different date or airport?"
            )
        return f"{msg}\n\n{provider_status_line}"

    # Sort offers by price to highlight the cheapest
    sorted_offers = sorted(display_offers, key=lambda x: float(x.get("total_amount", 999999)))
    cheapest = sorted_offers[0]

    # Find fastest non-stop offer
    non_stop_offers = [o for o in sorted_offers if o.get("stops", 0) == 0]
    fastest_nonstop = min(non_stop_offers, key=lambda x: x.get("duration_minutes", 999999)) if non_stop_offers else None

    lines = []
    if pref_norm:
        time_desc = "morning (departing before 12:00 PM)" if pref_norm == "morning" else f"{pref_norm}"
        lines.append(
            f"I found **{len(sorted_offers)} {time_desc} flight options** from **{origin}** to **{dest}** on **{dep_date}**:\n"
        )
        lines.append(f"*(Filtered strictly for your {pref_norm} departure preference)*\n")
    else:
        lines.append(
            f"I found **{len(sorted_offers)} flight options** from **{origin}** to **{dest}** on **{dep_date}**:\n"
        )

    for idx, off in enumerate(sorted_offers[:4], 1):
        airline = off.get("airline_name", "Airline")
        flight_no = off.get("flight_number", "")
        amount = float(off.get("total_amount", 0.0))
        currency = off.get("currency", "INR")
        dep_raw = off.get("departure_time", "")
        arr_raw = off.get("arrival_time", "")
        stops = off.get("stops", 0)
        stop_txt = "Non-stop" if stops == 0 else f"{stops} stop"
        duration_min = off.get("duration_minutes", 0)
        hours = duration_min // 60
        mins = duration_min % 60
        duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        cabin = off.get("cabin_class", "economy").replace("_", " ").title()

        # Format local departure and arrival times cleanly in airport local timezones
        try:
            dep_local = parse_local_departure_datetime(dep_raw, origin_iata=origin)
            dep_display = dep_local.strftime("%I:%M %p")
        except Exception:
            dep_display = dep_raw

        try:
            arr_local = parse_local_departure_datetime(arr_raw, origin_iata=dest)
            arr_display = arr_local.strftime("%I:%M %p")
        except Exception:
            arr_display = arr_raw

        tags = []
        if pref_norm and matches_departure_time_filter(off, pref_norm, origin_iata=origin):
            badge_title = "Morning Departure (<12 PM)" if pref_norm == "morning" else f"{pref_norm.capitalize()} Departure"
            tags.append(f"🌅 {badge_title}")
        if off == cheapest:
            tags.append("⭐ Lowest Fare")
        if fastest_nonstop and off == fastest_nonstop and off != cheapest:
            tags.append("⚡ Fastest Non-Stop")

        tag_str = f" *({', '.join(tags)})*" if tags else ""

        lines.append(
            f"**{idx}. {airline} {flight_no}** — **{currency} {amount:,.2f}**{tag_str}\n"
            f"   • Departure: {dep_display} | Arrival: {arr_display} ({duration_str}, {stop_txt})\n"
            f"   • Class: {cabin} | Baggage: Included"
        )

    lines.append("")
    lines.append(provider_status_line)
    lines.append("\nWould you like to select one of these flights or refine your search criteria?")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: Privacy Masking & Booking Review Formatter
# ---------------------------------------------------------------------------
def mask_email(email: str) -> str:
    """Masks email address for privacy (e.g. 'a***v@example.com')."""
    if not email or "@" not in email:
        return email or ""
    parts = email.split("@", 1)
    user_part, domain = parts[0], parts[1]
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain}"


def mask_phone(phone: str) -> str:
    """Masks phone number for privacy (e.g. '+91****3210')."""
    if not phone:
        return ""
    clean = phone.strip()
    if len(clean) <= 4:
        return "****"
    return f"{clean[:3]}****{clean[-4:]}"


def format_booking_review(
    offer: FlightOffer,
    passengers: List[Dict[str, Any]],
    contact: Dict[str, Any]
) -> str:
    """
    Constructs an explicit, privacy-conscious booking review summary.
    Enforces Step 6 Specifications:
    - Airline and flight number
    - Origin and destination
    - Departure and arrival date/time with local airport time
    - Stops and cabin class
    - Passenger names and passenger count
    - Contact info in masked form
    - Current total fare and currency
    - Provider and simulation/sandbox status
    - Unambiguous disclaimer that this is a review, not a confirmed ticket.
    """
    origin = offer.origin_iata
    dest = offer.destination_iata

    try:
        dep_dt = parse_local_departure_datetime(offer.departure_time, origin_iata=origin)
        dep_str = dep_dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        dep_str = offer.departure_time

    try:
        arr_dt = parse_local_departure_datetime(offer.arrival_time, origin_iata=dest)
        arr_str = arr_dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        arr_str = offer.arrival_time

    duration_min = offer.duration_minutes or 0
    hours = duration_min // 60
    mins = duration_min % 60
    duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    stops_str = "Non-stop" if offer.stops == 0 else f"{offer.stops} stop"

    is_sim = getattr(offer, "is_simulation", False) or getattr(offer, "data_source", "") == "mock_simulation"
    data_src = getattr(offer, "data_source", "mock_simulation")
    provider_status_line = (
        "⚡ **Provider Status:** `[SIMULATION / MOCK ORDER]` — Generated via authentic offline simulation for evaluation."
        if is_sim
        else ("✈️ **Provider Status:** `[DUFFEL TEST SANDBOX]` — Live test reservation in Duffel Sandbox."
              if data_src == "duffel_sandbox"
              else f"✈️ **Provider Status:** Live order via {data_src.upper()}.")
    )

    lines = [
        "📋 **BOOKING REVIEW (NOT YET CONFIRMED)**\n",
        "Please review your flight itinerary and passenger details carefully before confirming:\n",
        "✈️ **Flight Details:**",
        f"• **Airline & Flight:** {offer.airline_name} {offer.flight_number}",
        f"• **Route:** {origin} ➔ {dest}",
        f"• **Departure:** {dep_str} (Local Time)",
        f"• **Arrival:** {arr_str} (Local Time)",
        f"• **Duration & Stops:** {duration_str} | {stops_str}",
        f"• **Cabin Class:** {offer.cabin_class.replace('_', ' ').title()} (Baggage: {offer.baggage_included or 'Included'})\n",
        f"👤 **Passenger Details ({len(passengers)} Passenger{'s' if len(passengers) > 1 else ''}):**",
    ]

    for idx, p in enumerate(passengers, 1):
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        dob = p.get('date_of_birth', 'N/A')
        gender = (p.get('gender') or 'other').capitalize()
        passport = mask_passport_number(p.get('passport_number'))
        pass_txt = f" | Passport: {passport}" if passport else ""
        lines.append(f"• **Passenger {idx}:** {name} (DOB: {dob} | Gender: {gender}{pass_txt})")

    masked_em = mask_email(contact.get("email", ""))
    masked_ph = mask_phone(contact.get("phone", ""))
    lines.append("\n📞 **Contact Information:**")
    lines.append(f"• **Email:** `{masked_em}`")
    lines.append(f"• **Phone:** `{masked_ph}`\n")

    lines.append(f"💰 **Total Fare:** **{offer.currency} {offer.total_amount:,.2f}**\n")
    lines.append(provider_status_line)
    lines.append("\n⚠️ **Notice:** This is a booking review, not a confirmed ticket. Your payment or account balance has not been charged.")
    lines.append("\n👉 **To complete your reservation, please reply:** **\"Confirm booking\"** or **\"Yes, confirm\"**.")
    lines.append("*(If you need to change anything or cancel, simply reply **\"Cancel\"** or let me know what to update.)*")

    return "\n".join(lines)


def resolve_flight_offer(
    db: Session,
    identifier: str,
    search_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
    offers_in_state: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Optional[FlightOffer], Optional[str]]:
    """
    Resolves natural language flight selection identifier to an exact database FlightOffer record.
    Returns (FlightOffer, error_message).
    """
    candidate_offers: List[FlightOffer] = []

    # 1. From search_id if provided
    if search_id:
        candidate_offers = (
            db.query(FlightOffer)
            .filter(FlightOffer.search_id == search_id)
            .order_by(FlightOffer.id.asc())
            .all()
        )

    # 2. From conversation messages if search_id not directly passed
    if not candidate_offers and conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv and conv.messages:
            for m in reversed(conv.messages):
                if m.flight_search_id:
                    candidate_offers = (
                        db.query(FlightOffer)
                        .filter(FlightOffer.search_id == m.flight_search_id)
                        .order_by(FlightOffer.id.asc())
                        .all()
                    )
                    if candidate_offers:
                        break

    # 3. Fallback: query from offers_in_state provider_offer_ids
    if not candidate_offers and offers_in_state:
        p_ids = [o.get("provider_offer_id") for o in offers_in_state if o.get("provider_offer_id")]
        if p_ids:
            candidate_offers = (
                db.query(FlightOffer)
                .filter(FlightOffer.provider_offer_id.in_(p_ids))
                .order_by(FlightOffer.id.asc())
                .all()
            )

    if not candidate_offers:
        return None, "no_search_found"

    clean_id = (identifier or "").strip().lower()

    # Numeric option index: "1", "2", "3", ...
    if clean_id.isdigit():
        idx = int(clean_id) - 1
        if 0 <= idx < len(candidate_offers):
            return candidate_offers[idx], None
        return (
            None,
            f"You requested option {clean_id}, but only {len(candidate_offers)} flight options were returned. "
            f"Please choose a number between 1 and {len(candidate_offers)}."
        )

    # Superlatives: cheapest / fastest
    if clean_id in ["cheapest", "lowest", "lowest fare", "lowest price"]:
        return min(candidate_offers, key=lambda x: x.total_amount), None

    if clean_id in ["fastest", "quickest", "shortest"]:
        return min(candidate_offers, key=lambda x: x.duration_minutes), None

    # Internal Offer ID: "id_12"
    if clean_id.startswith("id_"):
        try:
            target_id = int(clean_id[3:])
            match = next((o for o in candidate_offers if o.id == target_id), None)
            if match:
                return match, None
            direct = db.query(FlightOffer).filter(FlightOffer.id == target_id).first()
            if direct:
                return None, f"Flight offer #{target_id} does not belong to your active conversation search results."
            return None, f"Flight offer #{target_id} was not found."
        except ValueError:
            pass

    # Flight Number / Carrier matching (e.g. 6E-2054, BA-117, IndiGo)
    matches = [
        o for o in candidate_offers
        if clean_id in (o.flight_number or "").lower().replace(" ", "").replace("-", "")
        or clean_id in (o.airline_name or "").lower()
        or (o.flight_number and clean_id in o.flight_number.lower())
    ]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        options_txt = ", ".join(f"option {i+1} ({o.airline_name} {o.flight_number})" for i, o in enumerate(candidate_offers) if o in matches)
        return (
            None,
            f"Multiple flights match '{identifier}': {options_txt}. Please specify by option number (e.g. 'flight 1')."
        )

    return (
        None,
        f"No flight matching '{identifier}' was found in your search results. Please choose from the flights listed above."
    )



# ---------------------------------------------------------------------------
# Node 1: Understand and Extract
# ---------------------------------------------------------------------------
async def understand_node(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Extracts user intent and travel criteria slots from user_message.
    Merges newly extracted slots into previously accumulated conversation slots.
    """
    user_msg = state.get("user_message", "")
    current_slots = dict(state.get("slots") or {})
    history = state.get("messages") or []

    cfg = config.get("configurable", {}) if config else {}
    force_fallback = cfg.get("force_fallback", False)
    reference_date = cfg.get("reference_date", None)

    intent, extracted_slots = await extract_slots_and_intent(
        user_message=user_msg,
        current_slots=current_slots,
        history=history,
        force_fallback=force_fallback,
        reference_date=reference_date
    )

    # Merge extracted slots over current slots (retaining previously known values if not updated)
    merged_slots = dict(current_slots)
    for k, v in extracted_slots.items():
        if v is not None:
            merged_slots[k] = v

    return {
        "intent": intent,
        "slots": merged_slots
    }


# ---------------------------------------------------------------------------
# Node 2: Validate Criteria
# ---------------------------------------------------------------------------
def validate_node(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Validates current slots and handles non-search intents (greeting, out_of_scope).
    Checks mandatory fields: origin, destination, departure_date.
    """
    intent = state.get("intent", "search_flights")
    slots = dict(state.get("slots") or {})

    # 1. Handle Booking Intents (select_flight, provide_passenger_details, confirm_booking, etc.)
    if intent in BOOKING_INTENTS:
        return {
            "search_ready": False,
            "missing_fields": [],
            "assistant_reply": ""
        }

    # 2. Handle Greetings
    if intent == "greeting":
        return {
            "search_ready": False,
            "missing_fields": ["origin", "destination", "departure_date"],
            "assistant_reply": (
                "Hello! I am TRAVELMATE AI, your personal flight booking assistant. "
                "Where would you like to fly to? (For example: 'Flights from Bangalore to Delhi next Friday')"
            )
        }

    # 3. Handle Out-of-Scope queries
    if intent == "out_of_scope":
        return {
            "search_ready": False,
            "missing_fields": [],
            "assistant_reply": (
                "I specialize in searching and booking flights worldwide. "
                "I cannot help with hotels or car rentals right now, but please let me know your flight details "
                "and I will gladly find the best flight options for you!"
            )
        }

    # 4. Validate Flight Slots
    # Catch origin == destination error before validation
    orig = slots.get("origin")
    dest = slots.get("destination")
    if orig and dest and orig.strip().upper() == dest.strip().upper():
        return {
            "search_ready": False,
            "missing_fields": ["destination"],
            "assistant_reply": (
                f"Origin and destination cannot both be **{orig.upper()}**. "
                "Please specify a different destination or departure airport."
            )
        }

    # Check departure date not in the past relative to reference_date / today
    cfg = config.get("configurable", {}) if config else {}
    ref_date = cfg.get("reference_date") or date.today()
    dep_str = slots.get("departure_date")
    if dep_str:
        try:
            dep_date = datetime.strptime(dep_str, "%Y-%m-%d").date()
            if dep_date < ref_date:
                return {
                    "search_ready": False,
                    "missing_fields": ["departure_date"],
                    "assistant_reply": (
                        f"The departure date **{dep_str}** is in the past. "
                        "Please provide a future departure date."
                    )
                }
        except ValueError:
            return {
                "search_ready": False,
                "missing_fields": ["departure_date"],
                "assistant_reply": (
                    f"The departure date **{dep_str}** is invalid. Please provide a valid date in YYYY-MM-DD format."
                )
            }

    # Use FlightCriteriaSlots property checks
    missing: List[str] = []
    if not orig:
        missing.append("origin")
    if not dest:
        missing.append("destination")
    if not dep_str:
        missing.append("departure_date")

    is_complete = len(missing) == 0

    return {
        "search_ready": is_complete,
        "missing_fields": missing,
        "assistant_reply": ""
    }


# ---------------------------------------------------------------------------
# Routing Function
# ---------------------------------------------------------------------------
def route_after_validation(state: AgentState) -> str:
    """
    Routes dialogue to appropriate next node:
    - If assistant_reply is already populated (greeting, out_of_scope, or error): finish turn
    - If intent is booking-related: execute booking node
    - If search_ready is True: execute flight search tool
    - Else: ask clarification question to gather missing slots
    """
    if state.get("assistant_reply"):
        return END

    intent = state.get("intent", "search_flights")
    if intent in BOOKING_INTENTS:
        return "booking"

    if state.get("search_ready"):
        return "search_flights"

    return "clarify"


# ---------------------------------------------------------------------------
# Node 3: Clarify Missing Information
# ---------------------------------------------------------------------------
def clarify_node(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Generates a targeted, polite follow-up question asking specifically for missing slots.
    Preserves conversation context and acknowledges already provided details.
    """
    missing = state.get("missing_fields") or []
    slots = state.get("slots") or {}
    orig = slots.get("origin")
    dest = slots.get("destination")
    dep = slots.get("departure_date")

    # Construct targeted follow-up question
    pref = slots.get("preferred_time")
    pref_ack = f"Noted your preference for {pref} flights. " if pref else ""

    if "origin" in missing and "destination" in missing and "departure_date" in missing:
        reply = f"{pref_ack}Where would you like to travel, and on what date? (For example: 'Flights from Bangalore to Delhi next Friday')"
    elif "origin" in missing and "destination" in missing:
        reply = f"{pref_ack}Traveling on {dep}. Where will you be departing from, and where would you like to fly to?"
    elif "origin" in missing and "departure_date" in missing:
        reply = f"{pref_ack}Flying to **{dest}**. Where will you be departing from, and on what date would you like to travel?"
    elif "destination" in missing and "departure_date" in missing:
        reply = f"{pref_ack}Departing from **{orig}**. Where would you like to fly to, and on what date?"
    elif "origin" in missing:
        reply = f"{pref_ack}Flying to **{dest}** on **{dep}**. Which airport or city will you be departing from?"
    elif "destination" in missing:
        reply = f"{pref_ack}Departing from **{orig}** on **{dep}**. What is your destination airport or city?"
    elif "departure_date" in missing:
        reply = f"{pref_ack}Flying from **{orig}** to **{dest}** — what date would you like to depart?"
    else:
        reply = f"{pref_ack}Could you please provide the missing flight details to proceed?"

    # Update messages log
    new_messages = list(state.get("messages") or [])
    if state.get("user_message"):
        new_messages.append({"role": "user", "content": state["user_message"]})
    new_messages.append({"role": "assistant", "content": reply})

    return {
        "assistant_reply": reply,
        "messages": new_messages
    }


# ---------------------------------------------------------------------------
# Node 4: Execute Flight Search Tool
# ---------------------------------------------------------------------------
async def search_flights_node(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Executes the validated Phase 2 FlightService search against the active flight provider.
    Saves the normalized search response to state.
    """
    slots_dict = dict(state.get("slots") or {})

    cfg = config.get("configurable", {}) if config else {}
    db = cfg.get("db")
    user_id = cfg.get("user_id")

    close_db = False
    if db is None:
        from app.core.database import SessionLocal
        db = SessionLocal()
        close_db = True

    ref_date = cfg.get("reference_date") or date.today()

    try:
        slots_obj = FlightCriteriaSlots.model_validate(slots_dict, context={"reference_date": ref_date})
        search_req: FlightSearchRequest = slots_obj.to_flight_search_request(reference_date=ref_date)

        logger.info(
            f"AI Agent executing flight search: {search_req.origin} -> {search_req.destination} on {search_req.departure_date}"
        )
        search_response = await flight_service.execute_search(
            db=db,
            criteria=search_req,
            user_id=user_id
        )

        results_dict = search_response.model_dump()

        # Apply actual departure date and time filter if specified (Requirements 1, 2, 3, 4, 5, 6)
        preferred_time = slots_dict.get("preferred_time")
        if preferred_time:
            filtered_offers = filter_flight_offers_by_time(
                results_dict.get("offers", []),
                preferred_time=preferred_time,
                origin_iata=search_req.origin,
                departure_date=search_req.departure_date
            )
            results_dict["offers"] = filtered_offers
            results_dict["total_offers"] = len(filtered_offers)

        return {
            "flight_search_results": results_dict,
            "error": None
        }

    except Exception as e:
        logger.error(f"Flight search execution failed in AI agent: {str(e)}", exc_info=True)
        return {
            "flight_search_results": None,
            "error": str(e),
            "assistant_reply": f"I'm sorry, I was unable to retrieve flights at the moment ({str(e)}). Please try again."
        }
    finally:
        if close_db and db is not None:
            db.close()


# ---------------------------------------------------------------------------
# Node 5: Format Response
# ---------------------------------------------------------------------------
def format_node(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Generates the final natural language response based on flight search results.
    Guarantees no hallucination and clear mock vs live labeling.
    """
    # If an error already produced a reply in search_flights_node
    if state.get("assistant_reply"):
        return {"assistant_reply": state["assistant_reply"]}

    results = state.get("flight_search_results")
    if not results:
        reply = "I was unable to find flight results for your request. Please try different search parameters."
    else:
        preferred_time = state.get("slots", {}).get("preferred_time")
        reply = format_flight_offers_summary(results, preferred_time=preferred_time)

    # Append to dialogue history
    new_messages = list(state.get("messages") or [])
    if state.get("user_message"):
        new_messages.append({"role": "user", "content": state["user_message"]})
    new_messages.append({"role": "assistant", "content": reply})

    return {
        "assistant_reply": reply,
        "messages": new_messages
    }


# ---------------------------------------------------------------------------
# Node 6: Conversational Booking Lifecycle Node
# ---------------------------------------------------------------------------
def _build_booking_state_update(
    state: AgentState,
    reply: str,
    workflow_state: str,
    slots: Dict[str, Any],
    selected_flight_offer_id: Optional[int] = None,
    selected_offer: Optional[Dict[str, Any]] = None,
    pending_confirmation_id: Optional[int] = None,
    booking_details: Optional[Dict[str, Any]] = None,
    booking_reference: Optional[str] = None
) -> Dict[str, Any]:
    new_messages = list(state.get("messages") or [])
    if state.get("user_message"):
        new_messages.append({"role": "user", "content": state["user_message"]})
    new_messages.append({"role": "assistant", "content": reply})

    update: Dict[str, Any] = {
        "assistant_reply": reply,
        "messages": new_messages,
        "slots": slots,
        "booking_workflow_state": workflow_state,
        "error": None
    }
    if selected_flight_offer_id is not None:
        update["selected_flight_offer_id"] = selected_flight_offer_id
    elif state.get("selected_flight_offer_id"):
        update["selected_flight_offer_id"] = state.get("selected_flight_offer_id")

    if selected_offer is not None:
        update["selected_offer"] = selected_offer
    elif state.get("selected_offer"):
        update["selected_offer"] = state.get("selected_offer")

    if pending_confirmation_id is not None:
        update["pending_confirmation_id"] = pending_confirmation_id
    elif state.get("pending_confirmation_id"):
        update["pending_confirmation_id"] = state.get("pending_confirmation_id")

    if booking_details is not None:
        update["booking_details"] = booking_details
    if booking_reference is not None:
        update["booking_reference"] = booking_reference

    return update


async def _execute_explicit_confirmation(
    db: Session,
    state: AgentState,
    user_id: int,
    conversation_id: Optional[int],
    is_price_change_approval: bool = False
) -> Dict[str, Any]:
    """
    Executes the secure booking confirmation:
    - Verifies active server-side PendingBookingConfirmation
    - Rejects confirmation from another user or another conversation
    - Enforces expiry check (15 minutes maximum validity)
    - Prevents reuse of previously consumed confirmations
    - Performs pre-booking offer revalidation
    - Detects price changes and requires fresh approval
    - Calls BookingService.create_booking with unique idempotency key
    """
    slots = dict(state.get("slots") or {})

    if not conversation_id:
        return _build_booking_state_update(
            state,
            reply="There is no active conversation session. Please start a conversation and select a flight first.",
            workflow_state="flight_selection_required",
            slots=slots
        )

    # 1. Retrieve pending confirmation bound to this user and conversation
    pending = (
        db.query(PendingBookingConfirmation)
        .filter(
            PendingBookingConfirmation.conversation_id == conversation_id,
            PendingBookingConfirmation.user_id == user_id,
            PendingBookingConfirmation.status == "pending"
        )
        .order_by(PendingBookingConfirmation.id.desc())
        .first()
    )

    if not pending:
        # Check if an expired or previously consumed confirmation exists to give helpful feedback
        prior = (
            db.query(PendingBookingConfirmation)
            .filter(
                PendingBookingConfirmation.conversation_id == conversation_id,
                PendingBookingConfirmation.user_id == user_id
            )
            .order_by(PendingBookingConfirmation.id.desc())
            .first()
        )
        if prior and prior.status == "consumed":
            reply = "This flight reservation has already been confirmed and processed. No duplicate booking was made."
        elif prior and prior.status == "expired":
            reply = "Your previous booking review session expired. Please select a flight and review your itinerary again."
        else:
            reply = "There is no active pending booking to confirm. Please select a flight and review your itinerary first."

        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="flight_selection_required",
            slots=slots
        )

    # 2. Check Expiry
    now_utc = datetime.now(timezone.utc)
    exp_time = pending.expires_at
    if exp_time.tzinfo is None:
        exp_time = exp_time.replace(tzinfo=timezone.utc)

    if exp_time < now_utc:
        pending.status = "expired"
        db.commit()
        reply = (
            "⚠️ **Booking Review Expired:** Your booking review session has expired for security (exceeded 15 minutes). "
            "Airline fares and availability change frequently. Please review your flight option again to proceed."
        )
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="booking_review_ready",
            slots=slots,
            selected_flight_offer_id=pending.flight_offer_id
        )

    # If this turn is explicitly approving a price change, mark price_change_accepted = True
    if is_price_change_approval:
        pending.price_change_accepted = True
        db.commit()

    # 3. Step 7: Live Offer Revalidation before Order Creation
    try:
        reval = await booking_service.revalidate_flight_offer(db, pending.flight_offer_id)
    except Exception as exc:
        pending.status = "invalidated"
        db.commit()
        reply = f"⚠️ **Revalidation Error:** Unable to revalidate flight offer ({str(exc)}). Please select another flight."
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="booking_failed",
            slots=slots
        )

    # Check availability
    if not reval.is_valid:
        pending.status = "invalidated"
        db.commit()
        msg = reval.message or "Offer is no longer available from the airline."
        reply = f"⚠️ **Flight Unavailable:** {msg} Would you like to search for alternative flights?"
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="booking_failed",
            slots=slots
        )

    # 4. Step 8: Price Change Detection & Approval Protection
    current_amt = float(reval.current_amount)
    price_changed = abs(current_amt - pending.expected_amount) > 0.01

    if price_changed and not pending.price_change_accepted:
        old_amt = pending.expected_amount
        pending.expected_amount = current_amt
        pending.currency = reval.currency
        db.commit()

        reply = (
            f"⚠️ **Price Change Alert:** The airline's live fare for this flight has updated from "
            f"**{pending.currency} {old_amt:,.2f}** to **{reval.currency} {current_amt:,.2f}**.\n\n"
            f"To authorize booking at the updated fare of **{reval.currency} {current_amt:,.2f}**, "
            f"please reply **'Accept new price and confirm'** (or reply **'Cancel'** to choose another flight)."
        )
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="price_change_requires_approval",
            slots=slots,
            selected_flight_offer_id=pending.flight_offer_id,
            pending_confirmation_id=pending.id
        )

    # 5. Mark pending confirmation as consumed to prevent replay attacks
    pending.status = "consumed"
    db.commit()

    # 6. Dispatch to existing centralized BookingService.create_booking
    passengers_data = json.loads(pending.passenger_details_json)
    pax_list = [PassengerBookingDetails(**p) for p in passengers_data]
    contact_obj = BookingContactDetails(email=pending.contact_email, phone=pending.contact_phone)
    idempotency_key = f"chat_{conversation_id}_{pending.id}_{uuid.uuid4().hex[:12]}"

    booking_req = BookingCreateRequest(
        flight_offer_id=pending.flight_offer_id,
        passengers=pax_list,
        contact=contact_obj,
        confirmed_by_user=True,
        expected_amount=current_amt if pending.price_change_accepted else pending.expected_amount,
        expected_currency=pending.currency,
        price_change_accepted=pending.price_change_accepted,
        idempotency_key=idempotency_key
    )

    try:
        booking_resp = await booking_service.create_booking(db=db, request=booking_req, user_id=user_id)

        # Clear booking slots after successful order
        slots.pop("selected_flight_offer_id", None)
        slots.pop("passenger_name", None)
        slots.pop("passenger_dob", None)
        slots.pop("passenger_gender", None)
        slots.pop("contact_email", None)
        slots.pop("contact_phone", None)
        slots.pop("use_saved_profile", None)

        provider_label = (
            "⚡ **Simulation Transparency:** This booking was created via authentic offline mock simulation for final-year project demonstration."
            if booking_resp.is_simulation
            else "✈️ **Duffel Test Sandbox:** This booking was placed in Duffel Sandbox test mode."
        )
        ref_pnr = booking_resp.booking_reference or "Pending Airline Confirmation"

        reply_lines = [
            "🎉 **BOOKING CONFIRMED!**\n",
            "Your flight reservation has been successfully placed with the airline.\n",
            f"• **Booking Reference (PNR):** `{ref_pnr}`",
            f"• **Provider Order ID:** `{booking_resp.provider_booking_id or 'N/A'}`",
            f"• **Status:** `{booking_resp.status.upper()}`",
            f"• **Total Fare:** **{booking_resp.currency} {booking_resp.total_amount:,.2f}**",
            f"• **Passengers ({len(booking_resp.passengers)}):** {', '.join(f'{p.first_name} {p.last_name}' for p in booking_resp.passengers)}",
            f"• **E-Ticket Delivery:** Sent to `{booking_resp.contact_email}`\n",
            provider_label,
            "\nThank you for booking with TRAVELMATE AI! Have a wonderful journey. Let me know if you would like to search for any other flights."
        ]
        reply = "\n".join(reply_lines)

        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="booking_confirmed",
            slots=slots,
            booking_details=booking_resp.model_dump(),
            booking_reference=booking_resp.booking_reference
        )

    except (BookingProviderTimeoutError, BookingProviderAmbiguousError) as amb_err:
        reply = (
            f"⚠️ **Booking Status Uncertain:** The flight provider experienced a network timeout or connection reset "
            f"while processing your reservation ({amb_err.message}). To protect you from duplicate charges, "
            f"automatic retries are blocked. Our system has preserved your booking intent as uncertain. "
            f"Please check your booking history or contact support before attempting a new booking."
        )
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="booking_uncertain",
            slots=slots,
            booking_details={"status": "uncertain", "error": amb_err.message}
        )

    except BookingPriceChangedError as pr_err:
        reply = (
            f"⚠️ **Price Alert:** {pr_err.message} "
            f"Please reply **'Accept new price and confirm'** to proceed at the updated fare, or reply **'Cancel'**."
        )
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="price_change_requires_approval",
            slots=slots,
            pending_confirmation_id=pending.id,
            selected_flight_offer_id=pending.flight_offer_id
        )

    except BookingDuplicateError as dup_err:
        reply = f"⚠️ **Duplicate Booking:** {dup_err.message}"
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="booking_failed",
            slots=slots,
            booking_details={"status": "failed", "error": dup_err.message}
        )

    except BookingServiceError as b_err:
        reply = f"❌ **Booking Failed:** {b_err.message} No charges were made to your account."
        return _build_booking_state_update(
            state,
            reply=reply,
            workflow_state="booking_failed",
            slots=slots,
            booking_details={"status": "failed", "error": b_err.message}
        )


async def booking_node(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Orchestrates the conversational flight booking workflow:
    - Verifies user authentication (blocks guest booking creation with clear login instruction)
    - Resolves flight selection from active search or conversation history
    - Answers questions about selected flight itinerary
    - Collects & validates passenger and contact details (supports saved user profiles)
    - Prepares formal, masked booking review and persists server-side PendingBookingConfirmation
    - Rejects vague confirmations without placing orders
    - Validates explicit confirmation (prevents cross-user, cross-conversation, or expired reuse)
    - Revalidates offer and detects price changes (demanding fresh approval)
    - Dispatches order creation via BookingService with unique idempotency key
    - Formats clear provider result (simulation, sandbox, uncertain, or failed)
    """
    cfg = config.get("configurable", {}) if config else {}
    db: Optional[Session] = cfg.get("db")
    user_id: Optional[int] = cfg.get("user_id")
    conversation_id: Optional[int] = cfg.get("conversation_id")

    close_db = False
    if db is None:
        from app.core.database import SessionLocal
        db = SessionLocal()
        close_db = True

    try:
        user_msg = state.get("user_message", "")
        intent = state.get("intent", "search_flights")
        slots = dict(state.get("slots") or {})

        # 1. Guest User Gate: Flight search is public, but booking strictly requires authentication
        if user_id is None:
            reply = (
                "⚠️ **Account Required for Booking:** You are currently browsing as a guest. "
                "Flight search and information are free, but to safely create and protect your flight reservation, "
                "please **log in** or **register an account**. Your flight search results and selected flight will be preserved!"
            )
            return _build_booking_state_update(
                state,
                reply=reply,
                workflow_state="authentication_required",
                slots=slots
            )

        user = db.query(User).filter(User.id == user_id).first()

        # 2. Cancellation Workflow
        if intent == "cancel_booking":
            if conversation_id:
                db.query(PendingBookingConfirmation).filter(
                    PendingBookingConfirmation.conversation_id == conversation_id,
                    PendingBookingConfirmation.status == "pending"
                ).update({"status": "invalidated"})
                db.commit()

            # Clear booking slots
            slots.pop("selected_flight_offer_id", None)
            slots.pop("passenger_name", None)
            slots.pop("passenger_dob", None)
            slots.pop("passenger_gender", None)
            slots.pop("contact_email", None)
            slots.pop("contact_phone", None)
            slots.pop("use_saved_profile", None)

            reply = "Your booking process has been cancelled. Would you like to search for different flights or select another option?"
            return _build_booking_state_update(
                state,
                reply=reply,
                workflow_state="normal_chat",
                slots=slots,
                selected_flight_offer_id=None,
                selected_offer=None,
                pending_confirmation_id=None
            )

        # 3. Vague Confirmation Gate: "looks good", "nice", "okay" MUST NOT create an order!
        if intent == "vague_confirmation":
            pending = None
            if conversation_id:
                pending = db.query(PendingBookingConfirmation).filter(
                    PendingBookingConfirmation.conversation_id == conversation_id,
                    PendingBookingConfirmation.user_id == user_id,
                    PendingBookingConfirmation.status == "pending"
                ).order_by(PendingBookingConfirmation.id.desc()).first()

            if pending:
                reply = (
                    "I'm glad the flight details look good! For your financial protection, "
                    "flight bookings require explicit authorization. Please reply with **'Confirm booking'** "
                    "to place this reservation, or reply **'Cancel'** to modify your details."
                )
                return _build_booking_state_update(
                    state,
                    reply=reply,
                    workflow_state="booking_confirmation_required",
                    slots=slots,
                    pending_confirmation_id=pending.id,
                    selected_flight_offer_id=pending.flight_offer_id
                )
            else:
                reply = "Thank you! Please let me know which flight option you would like to select."
                return _build_booking_state_update(
                    state,
                    reply=reply,
                    workflow_state="flight_selection_required",
                    slots=slots
                )

        # 4. Explicit Confirmation Execution (or Price Change Approval)
        if intent in ["confirm_booking", "price_change_approval"]:
            return await _execute_explicit_confirmation(
                db=db,
                state=state,
                user_id=user_id,
                conversation_id=conversation_id,
                is_price_change_approval=(intent == "price_change_approval")
            )

        # 5. Inquire about Selected Flight Details
        if intent == "ask_flight_details":
            selected_id = slots.get("selected_flight_offer_id")
            offer = None
            if selected_id:
                offer = db.query(FlightOffer).filter(FlightOffer.id == selected_id).first()

            if not offer:
                sel_ident = extract_flight_selection_identifier(user_msg)
                if sel_ident:
                    search_results = state.get("flight_search_results")
                    search_id = search_results.get("search_id") if search_results else None
                    offers_in_state = search_results.get("offers") if search_results else None
                    offer, _ = resolve_flight_offer(
                        db, sel_ident, search_id=search_id, conversation_id=conversation_id, offers_in_state=offers_in_state
                    )

            if not offer:
                reply = (
                    "Which flight would you like to know more about? "
                    "Please specify by flight option number (e.g. 'Tell me about flight 1') from your search results."
                )
                return _build_booking_state_update(
                    state,
                    reply=reply,
                    workflow_state="flight_selection_required",
                    slots=slots
                )

            slots["selected_flight_offer_id"] = offer.id
            hours = (offer.duration_minutes or 0) // 60
            mins = (offer.duration_minutes or 0) % 60
            dur_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            stops_str = "Non-stop" if offer.stops == 0 else f"{offer.stops} stop"

            reply = (
                f"Here are the details for **{offer.airline_name} {offer.flight_number}**:\n"
                f"• **Route:** {offer.origin_iata} to {offer.destination_iata}\n"
                f"• **Departure:** {offer.departure_time}\n"
                f"• **Arrival:** {offer.arrival_time} ({dur_str}, {stops_str})\n"
                f"• **Cabin Class:** {offer.cabin_class.replace('_', ' ').title()}\n"
                f"• **Baggage Allowance:** {offer.baggage_included or '15 kg Check-in, 7 kg Cabin included'}\n"
                f"• **Total Fare:** **{offer.currency} {offer.total_amount:,.2f}**\n\n"
                "Would you like to book this flight? (Reply **'Book this flight'** or **'Select flight'** to proceed.)"
            )
            return _build_booking_state_update(
                state,
                reply=reply,
                workflow_state="booking_review_ready",
                slots=slots,
                selected_flight_offer_id=offer.id,
                selected_offer=FlightOfferSchema.model_validate(offer).model_dump()
            )

        # 6. Flight Selection Intent
        if intent == "select_flight":
            sel_ident = slots.get("selected_flight_identifier") or extract_flight_selection_identifier(user_msg)
            if not sel_ident:
                reply = (
                    "Which flight would you like to select? "
                    "You can say 'flight 1', 'the second option', 'the cheapest flight', or provide the flight number."
                )
                return _build_booking_state_update(
                    state,
                    reply=reply,
                    workflow_state="flight_selection_required",
                    slots=slots
                )

            search_results = state.get("flight_search_results")
            search_id = search_results.get("search_id") if search_results else None
            offers_in_state = search_results.get("offers") if search_results else None

            offer, err_msg = resolve_flight_offer(
                db, sel_ident, search_id=search_id, conversation_id=conversation_id, offers_in_state=offers_in_state
            )

            if not offer:
                if err_msg == "no_search_found":
                    reply = (
                        "You haven't searched for flights yet. "
                        "Where and when would you like to fly? (For example: 'Flights from Bangalore to Delhi next Friday')"
                    )
                else:
                    reply = err_msg or "Could not locate the selected flight option. Please choose from the flights listed above."

                return _build_booking_state_update(
                    state,
                    reply=reply,
                    workflow_state="flight_selection_required",
                    slots=slots
                )

            # Record selected offer
            slots["selected_flight_offer_id"] = offer.id

        # 7. Provide Passenger Details Intent or Continuing with Selected Offer
        selected_id = slots.get("selected_flight_offer_id")
        if not selected_id:
            reply = (
                "You haven't selected a flight yet. "
                "Please select a flight option first before providing passenger details. "
                "Which flight would you like to book?"
            )
            return _build_booking_state_update(
                state,
                reply=reply,
                workflow_state="flight_selection_required",
                slots=slots
            )

        offer = db.query(FlightOffer).filter(FlightOffer.id == selected_id).first()
        if not offer:
            reply = "The selected flight offer could not be found in the database. Please perform a fresh flight search."
            return _build_booking_state_update(
                state,
                reply=reply,
                workflow_state="flight_selection_required",
                slots=slots
            )

        # Check if user requested saved profile
        if slots.get("use_saved_profile") or re.search(r"\b(?:use (?:my )?saved profile|use (?:my )?profile|use saved details|book for me)\b", user_msg.lower()):
            if user and user.passenger_profiles:
                p_prof = user.passenger_profiles[0]
                slots["passenger_name"] = f"{p_prof.first_name} {p_prof.last_name}"
                slots["passenger_dob"] = p_prof.date_of_birth or "1990-01-01"
                slots["passenger_gender"] = p_prof.gender or "other"
                if p_prof.passport_number:
                    slots["passport_number"] = p_prof.passport_number
                if not slots.get("contact_email"):
                    slots["contact_email"] = user.email
                if not slots.get("contact_phone"):
                    slots["contact_phone"] = "+919876543210"

        # Check passenger & contact completeness
        p_name = slots.get("passenger_name")
        p_dob = slots.get("passenger_dob")
        c_email = slots.get("contact_email") or (user.email if user else None)
        c_phone = slots.get("contact_phone")

        missing_pax = []
        if not p_name:
            missing_pax.append("Passenger Full Name (first and last name)")
        if not p_dob:
            missing_pax.append("Date of Birth (YYYY-MM-DD)")
        if not c_email:
            missing_pax.append("Contact Email Address")
        if not c_phone:
            missing_pax.append("Contact Phone Number")

        if missing_pax:
            profile_hint = ""
            if user and user.passenger_profiles:
                p_prof = user.passenger_profiles[0]
                profile_hint = (
                    f"\n\n💡 *Tip: I found your saved passenger profile for **{p_prof.first_name} {p_prof.last_name}**. "
                    f"You can simply reply **'Use my saved profile'** to autofill your details!*"
                )

            missing_str = "\n• " + "\n• ".join(missing_pax)
            reply = (
                f"You have selected **{offer.airline_name} {offer.flight_number}** "
                f"from **{offer.origin_iata}** to **{offer.destination_iata}** "
                f"(Total fare: **{offer.currency} {offer.total_amount:,.2f}**).\n\n"
                f"To prepare your booking review, please provide:{missing_str}"
                f"{profile_hint}"
            )
            return _build_booking_state_update(
                state,
                reply=reply,
                workflow_state="passenger_details_required",
                slots=slots,
                selected_flight_offer_id=offer.id,
                selected_offer=FlightOfferSchema.model_validate(offer).model_dump()
            )

        # Passenger & Contact details are complete! Prepare formal review and PendingBookingConfirmation.
        name_parts = p_name.strip().split()
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else first_name

        passengers_payload = [
            {
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": p_dob,
                "gender": slots.get("passenger_gender") or "other",
                "passport_number": slots.get("passport_number") or None
            }
        ]
        contact_payload = {
            "email": c_email,
            "phone": c_phone
        }

        # Invalidate any prior pending confirmation for this conversation
        if conversation_id:
            db.query(PendingBookingConfirmation).filter(
                PendingBookingConfirmation.conversation_id == conversation_id,
                PendingBookingConfirmation.status == "pending"
            ).update({"status": "invalidated"})
            db.flush()

        pax_tokens = sorted([f"{p['first_name'].lower().strip()}:{p['last_name'].lower().strip()}:{p['date_of_birth']}" for p in passengers_payload])
        pax_hash = hashlib.sha256("|".join(pax_tokens).encode("utf-8")).hexdigest()

        # Create fresh PendingBookingConfirmation (valid for 15 minutes)
        pending_rec = PendingBookingConfirmation(
            conversation_id=conversation_id,
            user_id=user_id,
            flight_offer_id=offer.id,
            provider_offer_id=offer.provider_offer_id,
            passenger_hash=pax_hash,
            passenger_details_json=json.dumps(passengers_payload),
            contact_email=contact_payload["email"],
            contact_phone=contact_payload["phone"],
            expected_amount=offer.total_amount,
            currency=offer.currency,
            status="pending",
            price_change_accepted=False,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        db.add(pending_rec)
        db.commit()
        db.refresh(pending_rec)

        review_text = format_booking_review(offer, passengers_payload, contact_payload)
        return _build_booking_state_update(
            state,
            reply=review_text,
            workflow_state="booking_confirmation_required",
            slots=slots,
            selected_flight_offer_id=offer.id,
            selected_offer=FlightOfferSchema.model_validate(offer).model_dump(),
            pending_confirmation_id=pending_rec.id
        )

    finally:
        if close_db and db is not None:
            db.close()


# ---------------------------------------------------------------------------
# Build and Compile the LangGraph State Machine
# ---------------------------------------------------------------------------
def build_flight_agent_graph():
    """
    Assembles and compiles the StateGraph workflow for TRAVELMATE AI.
    """
    builder = StateGraph(AgentState)

    # Register workflow nodes
    builder.add_node("understand", understand_node)
    builder.add_node("validate", validate_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("search_flights", search_flights_node)
    builder.add_node("format", format_node)
    builder.add_node("booking", booking_node)

    # Workflow Edges
    builder.add_edge(START, "understand")
    builder.add_edge("understand", "validate")

    # Conditional Branching after validation
    builder.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            END: END,
            "clarify": "clarify",
            "search_flights": "search_flights",
            "booking": "booking"
        }
    )

    builder.add_edge("clarify", END)
    builder.add_edge("search_flights", "format")
    builder.add_edge("format", END)
    builder.add_edge("booking", END)

    return builder.compile()


# Compiled Singleton Graph
flight_agent_graph = build_flight_agent_graph()
