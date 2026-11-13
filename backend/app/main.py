"""
TRAVELMATE AI - Backend Application Entrypoint
FastAPI server configuration, CORS middleware, lifespan table creation, and API routing.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.core.migrations import apply_schema_migrations
from app.models import User, PassengerProfile, FlightSearch, FlightOffer, Conversation, Message, Booking, PendingBookingConfirmation, IdempotencyRecord, BookingIntentReservation
from app.api.v1.auth import router as auth_router
from app.api.v1.flights import router as flights_router
from app.api.v1.chat import router as chat_router
from app.api.v1.endpoints.bookings import router as bookings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager:
    Ensures database tables are created on startup and applies schema migrations idempotently.
    """
    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    # Apply schema migrations for newly added model columns
    apply_schema_migrations(engine)
    yield


app = FastAPI(
    title="TRAVELMATE AI API",
    description="Backend API for AI-Powered Autonomous Flight Booking Assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(flights_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(bookings_router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["Health"])
def health_check():
    """
    Health check endpoint verifying API service status.
    """
    return {
        "status": "healthy",
        "service": "TRAVELMATE AI Backend",
        "environment": settings.ENVIRONMENT,
        "flight_provider": settings.FLIGHT_PROVIDER
    }

