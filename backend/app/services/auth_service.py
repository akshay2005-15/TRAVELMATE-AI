"""
Authentication service implementing core business logic for user management.
Complies with SRS FR-001, FR-002, FR-003, FR-004.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, PassengerProfile, UserRole
from app.schemas.auth import UserRegisterRequest, PassengerProfileCreate
from app.core.security import hash_password, verify_password


class AuthService:
    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        normalized_email = email.strip().lower()
        return db.query(User).filter(User.email == normalized_email).first()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def register_user(
        db: Session,
        req: UserRegisterRequest,
        role: UserRole = UserRole.USER
    ) -> User:
        normalized_email = req.email.strip().lower()

        # FR-001: Check for existing account
        existing_user = AuthService.get_by_email(db, normalized_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists."
            )

        # FR-003: Store password hashes using bcrypt
        hashed_pwd = hash_password(req.password)

        new_user = User(
            email=normalized_email,
            hashed_password=hashed_pwd,
            full_name=req.full_name.strip(),
            role=role,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def authenticate_user(
        db: Session,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Verify credentials. Returns authenticated User or None.
        """
        user = AuthService.get_by_email(db, email)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def add_passenger_profile(
        db: Session,
        user_id: int,
        req: PassengerProfileCreate
    ) -> PassengerProfile:
        profile = PassengerProfile(
            user_id=user_id,
            first_name=req.first_name.strip(),
            last_name=req.last_name.strip(),
            date_of_birth=req.date_of_birth,
            gender=req.gender,
            passport_number=req.passport_number.strip() if req.passport_number else None
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def get_passenger_profiles(
        db: Session,
        user_id: int
    ) -> List[PassengerProfile]:
        return db.query(PassengerProfile).filter(PassengerProfile.user_id == user_id).all()

