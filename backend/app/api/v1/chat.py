"""
Conversational AI Chat Endpoints for TRAVELMATE AI.
Implements message exchange, conversation lifecycle, session management, and flight results routing.
Complies with SRS FR-006 to FR-015, SAD Section 4.1, and Phase 3 Step 5 specifications.
"""

from typing import List, Optional
from datetime import datetime, timezone
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    MessageResponse,
    FlightCriteriaSlots,
)
from app.schemas.flight import FlightOfferSchema, FlightSearchResponse
from app.api.deps import get_optional_current_user
from app.ai import run_flight_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Send a message to the conversational assistant (FR-006 - FR-015)"
)
async def send_chat_message(
    req: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Submits a user query to the LangGraph AI State Machine.
    - Manages conversation persistence and ownership checks.
    - Maintains conversational travel criteria across turns.
    - Executes flight search when all mandatory criteria are present.
    - Persists user and assistant messages to database.
    """
    conversation: Conversation

    # 1. Conversation Lookup or Creation
    if req.conversation_id is not None:
        conversation = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation with ID {req.conversation_id} not found."
            )

        # Enforce conversation ownership
        if current_user:
            if conversation.user_id is not None and conversation.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You do not own this conversation."
                )
            # Associate anonymous/guest conversation with logged-in user if previously unclaimed
            if conversation.user_id is None:
                conversation.user_id = current_user.id
        else:
            # Guest cannot access registered user's conversation
            if conversation.user_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. This conversation belongs to a registered user."
                )
    else:
        # Create new conversation
        title_summary = req.message[:50].strip() or "Flight Search Assistant"
        conversation = Conversation(
            title=title_summary,
            user_id=current_user.id if current_user else None
        )
        db.add(conversation)
        db.flush()

    # 2. Reconstruct Conversation Context and Accumulated Slots
    current_slots = {}
    for m in reversed(conversation.messages):
        if m.slots_json:
            try:
                current_slots = json.loads(m.slots_json)
                break
            except Exception:
                pass

    history_messages = [
        {"role": m.role, "content": m.content}
        for m in conversation.messages[-10:]
    ]

    # 3. Execute LangGraph AI Agent
    user_id = current_user.id if current_user else None
    try:
        final_state = await run_flight_agent(
            user_message=req.message,
            current_slots=current_slots,
            messages=history_messages,
            db=db,
            user_id=user_id,
            conversation_id=conversation.id
        )
    except Exception as e:
        logger.error(f"Error executing AI flight agent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The AI assistant encountered an unexpected error processing your request. Please try again."
        )

    # 4. Extract Results and Determine Search & Booking Status
    slots_dict = final_state.get("slots") or {}
    search_results = final_state.get("flight_search_results")
    search_id = search_results.get("search_id") if search_results else None
    missing_fields = final_state.get("missing_fields") or []
    booking_workflow_state = final_state.get("booking_workflow_state") or "normal_chat"
    booking_details = final_state.get("booking_details")
    booking_reference = final_state.get("booking_reference")

    if search_results:
        search_status = "search_executed"
    elif missing_fields:
        search_status = "clarification_needed"
    else:
        search_status = "collecting_information"

    # 5. Persist Messages to Database
    slots_json_str = json.dumps(slots_dict) if slots_dict else None

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=req.message
    )
    db.add(user_msg)

    confirmed_booking_id = None
    if booking_details and isinstance(booking_details, dict) and booking_details.get("id"):
        confirmed_booking_id = booking_details.get("id")

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=final_state.get("assistant_reply", ""),
        slots_json=slots_json_str,
        flight_search_id=search_id,
        booking_id=confirmed_booking_id
    )
    db.add(assistant_msg)

    # Update conversation timestamp & title if more descriptive
    conversation.updated_at = datetime.now(timezone.utc)
    if conversation.title == "Flight Search Assistant" or len(conversation.title) < 10:
        orig = slots_dict.get("origin")
        dest = slots_dict.get("destination")
        if orig and dest:
            conversation.title = f"Flights from {orig} to {dest}"
        elif dest:
            conversation.title = f"Flights to {dest}"

    db.commit()
    db.refresh(conversation)

    # 6. Build ChatMessageResponse
    try:
        slots_schema = FlightCriteriaSlots(**slots_dict)
    except Exception:
        safe_slots = {}
        for key in ["origin", "destination", "departure_date", "return_date", "passengers", "cabin_class", "selected_flight_offer_id"]:
            if key in slots_dict and slots_dict[key] is not None:
                safe_slots[key] = slots_dict[key]
        try:
            slots_schema = FlightCriteriaSlots(**safe_slots)
        except Exception:
            slots_schema = FlightCriteriaSlots()

    flight_offers = None
    if search_results and "offers" in search_results:
        flight_offers = [FlightOfferSchema(**o) for o in search_results["offers"]]

    search_metadata = None
    if search_results:
        search_metadata = FlightSearchResponse(**search_results)

    selected_offer_data = final_state.get("selected_offer")
    selected_offer_schema = None
    if selected_offer_data:
        try:
            selected_offer_schema = FlightOfferSchema(**selected_offer_data)
        except Exception:
            pass

    return ChatMessageResponse(
        conversation_id=conversation.id,
        assistant_message=final_state.get("assistant_reply", ""),
        slots=slots_schema,
        missing_fields=missing_fields,
        search_status=search_status,
        flight_offers=flight_offers,
        search_metadata=search_metadata,
        booking_workflow_state=booking_workflow_state,
        selected_offer=selected_offer_schema,
        booking_details=booking_details,
        booking_reference=booking_reference
    )


@router.get(
    "/conversations",
    response_model=List[ConversationSummaryResponse],
    summary="List all conversations for authenticated user (FR-006)"
)
def list_conversations(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Returns summaries of all conversations belonging to the authenticated user.
    Returns empty list for guests who do not have persistent saved history.
    """
    if not current_user:
        return []

    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [ConversationSummaryResponse.model_validate(c) for c in conversations]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Retrieve conversation details and message history (FR-006)"
)
def get_conversation_history(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Retrieves full message history for a given conversation in chronological order.
    Enforces user ownership.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found."
        )

    # Enforce ownership
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not own this conversation."
            )
    else:
        if conversation.user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. This conversation belongs to a registered user."
            )

    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    summary="Delete a conversation and its messages (FR-006)"
)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Deletes a conversation and all its dialogue turns.
    Enforces ownership permissions.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found."
        )

    # Enforce ownership
    if current_user:
        if conversation.user_id is not None and conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not own this conversation."
            )
    else:
        if conversation.user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. This conversation belongs to a registered user."
            )

    db.delete(conversation)
    db.commit()

    return {
        "status": "success",
        "message": f"Conversation {conversation_id} deleted successfully."
    }

