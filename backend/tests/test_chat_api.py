"""
Automated Integration Tests for Phase 3 Step 5: Chat API Endpoints (/api/v1/chat).
Validates message exchange, conversation lifecycle, multi-turn context retention,
ownership authorization, guest sessions, and flight tool execution via API.
"""

import pytest
from datetime import date, timedelta


def register_and_get_token(client, email: str, name: str = "Test User") -> str:
    """Helper function to register a test user and return a Bearer JWT token."""
    res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": name
    })
    assert res.status_code == 201
    return res.json()["access_token"]


# ===========================================================================
# 1. First Message and Conversation Creation
# ===========================================================================

def test_send_first_message_creates_conversation(client):
    """Verify that posting a message without conversation_id creates a new session."""
    payload = {"message": "Hello TRAVELMATE"}
    res = client.post("/api/v1/chat/message", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert data["conversation_id"] > 0
    assert "TRAVELMATE AI" in data["assistant_message"]
    assert data["search_status"] in ("collecting_information", "clarification_needed")
    assert data["flight_offers"] is None


# ===========================================================================
# 2. Multi-Turn Dialogue and Context Retention
# ===========================================================================

def test_multi_turn_context_retention_and_search_trigger(client):
    """
    Simulate a 3-turn flight discovery flow:
    Turn 1: User provides destination ("Delhi")
    Turn 2: User provides origin ("Bangalore")
    Turn 3: User provides departure date ("Tomorrow")
    Verify that slots are preserved and flight search triggers.
    """
    # Turn 1: Destination
    t1_res = client.post("/api/v1/chat/message", json={"message": "I want to fly to Delhi"})
    assert t1_res.status_code == 200
    t1_data = t1_res.json()
    conv_id = t1_data["conversation_id"]

    assert t1_data["slots"]["destination"] == "DEL"
    assert "origin" in t1_data["missing_fields"]
    assert t1_data["search_status"] == "clarification_needed"
    assert t1_data["flight_offers"] is None

    # Turn 2: Origin
    t2_res = client.post("/api/v1/chat/message", json={
        "conversation_id": conv_id,
        "message": "Departing from Bangalore"
    })
    assert t2_res.status_code == 200
    t2_data = t2_res.json()

    assert t2_data["conversation_id"] == conv_id
    # Destination must be retained from Turn 1!
    assert t2_data["slots"]["destination"] == "DEL"
    assert t2_data["slots"]["origin"] == "BLR"
    assert t2_data["missing_fields"] == ["departure_date"]
    assert t2_data["search_status"] == "clarification_needed"

    # Turn 3: Departure Date (Triggers Flight Search)
    t3_res = client.post("/api/v1/chat/message", json={
        "conversation_id": conv_id,
        "message": "Tomorrow"
    })
    assert t3_res.status_code == 200
    t3_data = t3_res.json()

    assert t3_data["conversation_id"] == conv_id
    assert t3_data["slots"]["origin"] == "BLR"
    assert t3_data["slots"]["destination"] == "DEL"
    assert t3_data["slots"]["departure_date"] is not None
    assert t3_data["search_status"] == "search_executed"
    assert t3_data["flight_offers"] is not None
    assert len(t3_data["flight_offers"]) > 0
    assert t3_data["search_metadata"]["total_offers"] > 0
    assert "Lowest Fare" in t3_data["assistant_message"] or "Provider Status" in t3_data["assistant_message"]


# ===========================================================================
# 3. Conversation Listing and History Retrieval
# ===========================================================================

def test_list_and_retrieve_user_conversations(client):
    """Verify listing conversations and retrieving chronological message history."""
    token = register_and_get_token(client, "alice@travelmate.ai", "Alice")
    headers = {"Authorization": f"Bearer {token}"}

    # Alice creates conversation 1
    c1_res = client.post("/api/v1/chat/message", json={"message": "Flights to Delhi"}, headers=headers)
    assert c1_res.status_code == 200
    conv1_id = c1_res.json()["conversation_id"]

    # Alice creates conversation 2
    c2_res = client.post("/api/v1/chat/message", json={"message": "Flights to Mumbai"}, headers=headers)
    assert c2_res.status_code == 200
    conv2_id = c2_res.json()["conversation_id"]

    # List conversations
    list_res = client.get("/api/v1/chat/conversations", headers=headers)
    assert list_res.status_code == 200
    conversations = list_res.json()
    assert len(conversations) == 2
    conv_ids = [c["id"] for c in conversations]
    assert conv1_id in conv_ids
    assert conv2_id in conv_ids

    # Retrieve history for conversation 1
    history_res = client.get(f"/api/v1/chat/conversations/{conv1_id}", headers=headers)
    assert history_res.status_code == 200
    history = history_res.json()
    assert history["id"] == conv1_id
    assert len(history["messages"]) >= 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"


def test_guest_conversation_listing_returns_empty(client):
    """Verify that unauthenticated guests receive an empty conversation list."""
    res = client.get("/api/v1/chat/conversations")
    assert res.status_code == 200
    assert res.json() == []


# ===========================================================================
# 4. Security & Ownership Authorization
# ===========================================================================

def test_prevent_cross_user_conversation_access(client):
    """Verify that User B cannot view, message, or delete User A's conversation."""
    token_a = register_and_get_token(client, "usera@travelmate.ai", "User A")
    token_b = register_and_get_token(client, "userb@travelmate.ai", "User B")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a conversation
    create_res = client.post("/api/v1/chat/message", json={"message": "Trip to London"}, headers=headers_a)
    assert create_res.status_code == 200
    conv_a_id = create_res.json()["conversation_id"]

    # User B attempts to view history -> 403 Forbidden
    get_res = client.get(f"/api/v1/chat/conversations/{conv_a_id}", headers=headers_b)
    assert get_res.status_code == 403
    assert "Access denied" in get_res.json()["detail"]

    # User B attempts to append a message -> 403 Forbidden
    post_res = client.post(
        "/api/v1/chat/message",
        json={"conversation_id": conv_a_id, "message": "Hi from hacker"},
        headers=headers_b
    )
    assert post_res.status_code == 403

    # User B attempts to delete conversation -> 403 Forbidden
    del_res = client.delete(f"/api/v1/chat/conversations/{conv_a_id}", headers=headers_b)
    assert del_res.status_code == 403


def test_guest_cannot_access_registered_user_conversation(client):
    """Verify that an unauthenticated guest cannot access a registered user's conversation."""
    token = register_and_get_token(client, "member@travelmate.ai", "Member")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/chat/message", json={"message": "Private trip"}, headers=headers)
    conv_id = create_res.json()["conversation_id"]

    # Guest tries to access
    get_res = client.get(f"/api/v1/chat/conversations/{conv_id}")
    assert get_res.status_code == 403

    post_res = client.post("/api/v1/chat/message", json={"conversation_id": conv_id, "message": "Guest breach"})
    assert post_res.status_code == 403

    del_res = client.delete(f"/api/v1/chat/conversations/{conv_id}")
    assert del_res.status_code == 403


# ===========================================================================
# 5. Delete Conversation
# ===========================================================================

def test_delete_conversation_success(client):
    """Verify that the owner can delete their conversation."""
    token = register_and_get_token(client, "delete_user@travelmate.ai", "Deleter")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/chat/message", json={"message": "Delete me"}, headers=headers)
    conv_id = create_res.json()["conversation_id"]

    # Delete conversation
    del_res = client.delete(f"/api/v1/chat/conversations/{conv_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Confirm it is gone
    get_res = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=headers)
    assert get_res.status_code == 404


# ===========================================================================
# 6. Validation and Error Handling
# ===========================================================================

def test_chat_empty_and_whitespace_messages_rejected(client):
    """Verify that empty or whitespace-only messages produce HTTP 422."""
    res_empty = client.post("/api/v1/chat/message", json={"message": ""})
    assert res_empty.status_code == 422

    res_whitespace = client.post("/api/v1/chat/message", json={"message": "    "})
    assert res_whitespace.status_code == 422


def test_chat_nonexistent_conversation_id_returns_404(client):
    """Verify that providing an unknown conversation_id returns HTTP 404."""
    res = client.post("/api/v1/chat/message", json={"conversation_id": 999999, "message": "Hello"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_chat_out_of_scope_message(client):
    """Verify out-of-scope messages (hotels, cabs) receive a polite flight-redirection reply."""
    res = client.post("/api/v1/chat/message", json={"message": "Can you book a hotel room in Paris?"})
    assert res.status_code == 200
    data = res.json()
    assert "flights" in data["assistant_message"].lower()
    assert data["flight_offers"] is None
    assert data["search_status"] == "collecting_information"

