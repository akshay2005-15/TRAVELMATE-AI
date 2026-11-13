"""
Authentication and user profile API endpoints.
Complies with SRS FR-001 - FR-005.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    PassengerProfileCreate,
    PassengerProfileResponse,
)
from app.services.auth_service import AuthService
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account (FR-001, FR-003)"
)
def register(
    req: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Registers a new user, hashes their password with bcrypt,
    creates their session access token, and returns user details.
    """
    user = AuthService.register_user(db, req)
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and issue access token (FR-002, FR-005)"
)
def login(
    req: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticates registered user credentials and returns a signed JWT access token.
    """
    user = AuthService.authenticate_user(db, email=req.email, password=req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials."
        )

    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve authenticated user profile (FR-004)"
)
def get_current_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Returns the profile of the currently authenticated user.
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    summary="User logout (FR-005)"
)
def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Confirms session termination for the authenticated client.
    """
    return {
        "status": "success",
        "message": f"User {current_user.email} successfully logged out."
    }


@router.get(
    "/passengers",
    response_model=List[PassengerProfileResponse],
    summary="Get saved passenger profiles for current user"
)
def list_passengers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves passenger profiles saved under the authenticated user.
    """
    return AuthService.get_passenger_profiles(db, current_user.id)


@router.post(
    "/passengers",
    response_model=PassengerProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a passenger profile for quick booking"
)
def create_passenger(
    req: PassengerProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stores passenger profile details for future flight bookings.
    """
    return AuthService.add_passenger_profile(db, current_user.id, req)

