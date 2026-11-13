"""
Re-export of bookings router from app.api.v1.endpoints.bookings for architectural consistency.
"""

from app.api.v1.endpoints.bookings import router

__all__ = ["router"]

