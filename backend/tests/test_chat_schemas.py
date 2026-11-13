"""
Unit test suite for Conversational AI Pydantic Schemas.
Tests request validation, slot filling, boundary rules, and ORM serialization.
"""

from datetime import datetime, date, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.schemas.chat import (
    ChatMessageRequest,
    FlightCriteriaSlots,
    ChatMessageResponse,
    MessageResponse,
    ConversationResponse,
    ConversationSummaryResponse,
)
from app.schemas.flight import FlightOfferSchema, FlightSearchRequest
from app.models.conversation import Conversation, Message


def test_valid_chat_request():
    # New conversation (no conversation_id)
    req1 = ChatMessageRequest(message="Book a flight from Bangalore to Delhi next Tuesday")
    assert req1.conversation_id is None
    assert req1.message == "Book a flight from Bangalore to Delhi next Tuesday"

    # Existing conversation
    req2 = ChatMessageRequest(conversation_id=42, message="Show cheapest only")
    assert req2.conversation_id == 42
    assert req2.message == "Show cheapest only"


def test_empty_or_whitespace_message_rejected():
    # Empty string
    with pytest.raises(ValidationError) as exc1:
        ChatMessageRequest(message="")
    assert "Message cannot be empty" in str(exc1.value)

    # Whitespace only
    with pytest.raises(ValidationError) as exc2:
        ChatMessageRequest(message="   \n\t  ")
    assert "Message cannot be empty" in str(exc2.value)


def test_flight_criteria_slots_valid():
    future_dep = (date.today() + timedelta(days=7)).isoformat()
    future_ret = (date.today() + timedelta(days=14)).isoformat()

    slots = FlightCriteriaSlots(
        origin="blr",  # test auto-uppercase
        destination="del",
        departure_date=future_dep,
        return_date=future_ret,
        passengers=2,
        cabin_class="business"
    )

    assert slots.origin == "BLR"
    assert slots.destination == "DEL"
    assert slots.departure_date == future_dep
    assert slots.return_date == future_ret
    assert slots.passengers == 2
    assert slots.cabin_class == "business"
    assert slots.is_complete is True
    assert slots.missing_mandatory_fields == []


def test_slots_missing_mandatory_fields():
    # Completely empty slots
    empty_slots = FlightCriteriaSlots()
    assert empty_slots.is_complete is False
    assert set(empty_slots.missing_mandatory_fields) == {"origin", "destination", "departure_date"}

    # Origin only
    partial_slots = FlightCriteriaSlots(origin="BLR")
    assert partial_slots.is_complete is False
    assert set(partial_slots.missing_mandatory_fields) == {"destination", "departure_date"}

    # Origin and Destination, but no date
    route_only = FlightCriteriaSlots(origin="BLR", destination="DEL")
    assert route_only.is_complete is False
    assert route_only.missing_mandatory_fields == ["departure_date"]


def test_slots_same_origin_and_destination_rejected():
    future_date = (date.today() + timedelta(days=5)).isoformat()

    # Identical uppercase
    with pytest.raises(ValidationError) as exc1:
        FlightCriteriaSlots(origin="BLR", destination="BLR", departure_date=future_date)
    assert "Origin and destination airports must be different" in str(exc1.value)

    # Identical mixed-case
    with pytest.raises(ValidationError) as exc2:
        FlightCriteriaSlots(origin="blr", destination="BLR", departure_date=future_date)
    assert "Origin and destination airports must be different" in str(exc2.value)


def test_slots_invalid_airport_code():
    with pytest.raises(ValidationError) as exc1:
        FlightCriteriaSlots(origin="BANGALORE")
    assert "Invalid airport code" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        FlightCriteriaSlots(destination="12")
    assert "Invalid airport code" in str(exc2.value)


def test_slots_invalid_dates():
    # Past departure date
    past_date = (date.today() - timedelta(days=2)).isoformat()
    with pytest.raises(ValidationError) as exc1:
        FlightCriteriaSlots(origin="BLR", destination="DEL", departure_date=past_date)
    assert "past" in str(exc1.value).lower()

    # Return date earlier than departure date
    future_dep = (date.today() + timedelta(days=10)).isoformat()
    earlier_ret = (date.today() + timedelta(days=5)).isoformat()
    with pytest.raises(ValidationError) as exc2:
        FlightCriteriaSlots(
            origin="BLR",
            destination="DEL",
            departure_date=future_dep,
            return_date=earlier_ret
        )
    assert "Return date cannot be earlier" in str(exc2.value)


def test_slots_invalid_passenger_count():
    # Zero passengers
    with pytest.raises(ValidationError) as exc1:
        FlightCriteriaSlots(passengers=0)
    assert "Passenger count must be between 1 and 9" in str(exc1.value)

    # More than 9 passengers
    with pytest.raises(ValidationError) as exc2:
        FlightCriteriaSlots(passengers=12)
    assert "Passenger count must be between 1 and 9" in str(exc2.value)


def test_slots_invalid_cabin_class():
    with pytest.raises(ValidationError) as exc:
        FlightCriteriaSlots(cabin_class="ultra_luxury")
    assert "Unsupported cabin class" in str(exc.value)


def test_to_flight_search_request_conversion():
    future_dep = (date.today() + timedelta(days=6)).isoformat()
    slots = FlightCriteriaSlots(
        origin="BLR",
        destination="BOM",
        departure_date=future_dep,
        passengers=1,
        cabin_class="economy"
    )

    # Conversion succeeds when complete
    search_req = slots.to_flight_search_request()
    assert isinstance(search_req, FlightSearchRequest)
    assert search_req.origin == "BLR"
    assert search_req.destination == "BOM"
    assert search_req.departure_date == future_dep
    assert search_req.passengers == 1
    assert search_req.cabin_class == "economy"

    # Conversion fails when mandatory slots are missing
    incomplete_slots = FlightCriteriaSlots(origin="BLR")
    with pytest.raises(ValueError) as exc:
        incomplete_slots.to_flight_search_request()
    assert "missing mandatory fields" in str(exc.value)


def test_chat_response_serialization():
    # Response without flight offers (clarification phase)
    res1 = ChatMessageResponse(
        conversation_id=10,
        assistant_message="Which city would you like to depart from?",
        slots=FlightCriteriaSlots(destination="DEL"),
        missing_fields=["origin", "departure_date"],
        search_status="clarification_needed"
    )
    assert res1.conversation_id == 10
    assert res1.flight_offers is None
    assert res1.missing_fields == ["origin", "departure_date"]

    # Response with flight offers (search executed phase)
    sample_offer = FlightOfferSchema(
        provider_offer_id="mock_off_sample1",
        airline_name="IndiGo",
        airline_code="6E",
        flight_number="6E-2054",
        origin_iata="BLR",
        destination_iata="DEL",
        departure_time="2026-11-20T06:00:00+00:00",
        arrival_time="2026-11-20T08:45:00+00:00",
        duration_minutes=165,
        stops=0,
        total_amount=5400.0,
        currency="INR",
        cabin_class="economy",
        data_source="mock_simulation",
        is_simulation=True
    )

    res2 = ChatMessageResponse(
        conversation_id=10,
        assistant_message="Here are the available flights from BLR to DEL:",
        slots=FlightCriteriaSlots(
            origin="BLR",
            destination="DEL",
            departure_date=(date.today() + timedelta(days=5)).isoformat()
        ),
        missing_fields=[],
        search_status="search_executed",
        flight_offers=[sample_offer]
    )
    assert res2.conversation_id == 10
    assert len(res2.flight_offers) == 1
    assert res2.flight_offers[0].airline_name == "IndiGo"
    assert res2.flight_offers[0].is_simulation is True


def test_conversation_and_message_orm_serialization():
    # Instantiate ORM objects
    now = datetime.now(timezone.utc)
    conv = Conversation(
        id=1,
        user_id=5,
        title="Flights to Mumbai",
        created_at=now,
        updated_at=now
    )

    msg = Message(
        id=101,
        conversation_id=1,
        role="user",
        content="Find flights from BLR to BOM",
        slots_json='{"origin": "BLR", "destination": "BOM"}',
        flight_search_id=None,
        created_at=now
    )
    conv.messages = [msg]

    # Test MessageResponse serialization from ORM
    msg_dto = MessageResponse.model_validate(msg)
    assert msg_dto.id == 101
    assert msg_dto.role == "user"
    assert msg_dto.content == "Find flights from BLR to BOM"

    # Test ConversationResponse serialization from ORM
    conv_dto = ConversationResponse.model_validate(conv)
    assert conv_dto.id == 1
    assert conv_dto.user_id == 5
    assert len(conv_dto.messages) == 1
    assert conv_dto.messages[0].id == 101

    # Test ConversationSummaryResponse
    summary_dto = ConversationSummaryResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages)
    )
    assert summary_dto.id == 1
    assert summary_dto.message_count == 1

