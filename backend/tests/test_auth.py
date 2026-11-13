"""
Unit and integration tests for Authentication and User Management.
Validates compliance with SRS FR-001 through FR-005.
"""

def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "TRAVELMATE AI Backend"


def test_register_user_success(client):
    payload = {
        "email": "student@travelmate.ai",
        "password": "Password123!",
        "full_name": "Test Student"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "student@travelmate.ai"
    assert data["user"]["full_name"] == "Test Student"
    assert data["user"]["role"] == "user"


def test_register_duplicate_email_fails(client):
    payload = {
        "email": "duplicate@travelmate.ai",
        "password": "Password123!",
        "full_name": "First User"
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second attempt with same email
    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_register_short_password_fails(client):
    payload = {
        "email": "short@travelmate.ai",
        "password": "short",  # Less than 8 chars
        "full_name": "Short Password"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_login_success(client):
    # Register first
    client.post("/api/v1/auth/register", json={
        "email": "login_user@travelmate.ai",
        "password": "SecurePassword99",
        "full_name": "Login User"
    })

    # Perform login
    login_res = client.post("/api/v1/auth/login", json={
        "email": "login_user@travelmate.ai",
        "password": "SecurePassword99"
    })
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login_user@travelmate.ai"


def test_login_wrong_password_fails(client):
    client.post("/api/v1/auth/register", json={
        "email": "user_wrong@travelmate.ai",
        "password": "CorrectPassword123",
        "full_name": "Wrong Test"
    })

    login_res = client.post("/api/v1/auth/login", json={
        "email": "user_wrong@travelmate.ai",
        "password": "IncorrectPassword"
    })
    assert login_res.status_code == 401
    assert "Invalid email or password" in login_res.json()["detail"]


def test_get_current_user_profile(client):
    # Register and get token
    reg_res = client.post("/api/v1/auth/register", json={
        "email": "me_profile@travelmate.ai",
        "password": "ValidPassword123",
        "full_name": "Profile Owner"
    })
    token = reg_res.json()["access_token"]

    # Access protected /me route
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["email"] == "me_profile@travelmate.ai"
    assert data["full_name"] == "Profile Owner"


def test_get_profile_unauthorized(client):
    # Attempt without token
    res1 = client.get("/api/v1/auth/me")
    assert res1.status_code == 401

    # Attempt with invalid token
    res2 = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_fake_token"})
    assert res2.status_code == 401


def test_logout(client):
    reg_res = client.post("/api/v1/auth/register", json={
        "email": "logout_test@travelmate.ai",
        "password": "ValidPassword123",
        "full_name": "Logout Tester"
    })
    token = reg_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "success"


def test_passenger_profile_creation_and_listing(client):
    # Register user
    reg_res = client.post("/api/v1/auth/register", json={
        "email": "passenger_owner@travelmate.ai",
        "password": "Password12345",
        "full_name": "Passenger Booker"
    })
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add passenger profile
    passenger_payload = {
        "first_name": "Aarav",
        "last_name": "Sharma",
        "date_of_birth": "1998-05-15",
        "gender": "male",
        "passport_number": "Z1234567"
    }
    create_res = client.post("/api/v1/auth/passengers", json=passenger_payload, headers=headers)
    assert create_res.status_code == 201
    created_passenger = create_res.json()
    assert created_passenger["first_name"] == "Aarav"
    assert created_passenger["last_name"] == "Sharma"

    # List passenger profiles
    list_res = client.get("/api/v1/auth/passengers", headers=headers)
    assert list_res.status_code == 200
    passengers = list_res.json()
    assert len(passengers) == 1
    assert passengers[0]["first_name"] == "Aarav"

