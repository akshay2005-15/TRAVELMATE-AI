import api from './api.js';

/**
 * Service for Flight Bookings, Offer Revalidation, Passenger Manifests,
 * and Idempotency Key Management.
 * Communicates with Phase 4 Step 5 FastAPI endpoints.
 */

/**
 * Masks an email address for privacy in read representations (e.g. 'r***l@example.com').
 */
export const maskEmail = (email) => {
  if (!email || typeof email !== 'string' || !email.includes('@')) {
    return email || '';
  }
  const [userPart, domain] = email.split('@');
  if (userPart.length <= 2) {
    return `${userPart[0]}***@${domain}`;
  }
  return `${userPart[0]}***${userPart[userPart.length - 1]}@${domain}`;
};

/**
 * Masks a phone number for privacy in read representations (e.g. '+91****3210').
 */
export const maskPhone = (phone) => {
  if (!phone || typeof phone !== 'string') return '';
  const clean = phone.trim();
  if (clean.length <= 4) return '****';
  return `${clean.slice(0, 3)}****${clean.slice(-4)}`;
};

/**
 * Masks a passport number for privacy (e.g. '****5678').
 */
export const maskPassport = (passport) => {
  if (!passport || typeof passport !== 'string') return '';
  const clean = passport.trim();
  if (clean.length <= 4) return '****';
  return `****${clean.slice(-4)}`;
};

/**
 * Formats a date string into human-readable format (e.g. "Wed, Nov 18, 2026").
 * Guaranteed never to return "Invalid Date", "NaN", or "undefined".
 */
export const formatDate = (val) => {
  if (!val) return 'Date unavailable';
  try {
    const dt = new Date(val);
    if (isNaN(dt.getTime())) {
      if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}/.test(val)) {
        const [y, m, d] = val.split('T')[0].split('-');
        const parsed = new Date(Number(y), Number(m) - 1, Number(d));
        if (!isNaN(parsed.getTime())) {
          return parsed.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
        }
      }
      return 'Date unavailable';
    }
    return dt.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return 'Date unavailable';
  }
};

/**
 * Formats a date/time string into readable 12-hour format (e.g. "02:45 PM").
 * Guaranteed never to return "Invalid Date", "NaN", or "undefined".
 */
export const formatTime = (val) => {
  if (!val) return '--:--';
  try {
    const dt = new Date(val);
    if (isNaN(dt.getTime())) {
      if (typeof val === 'string' && /\d{2}:\d{2}/.test(val)) {
        const match = val.match(/(\d{2}):(\d{2})/);
        if (match) {
          const h = parseInt(match[1], 10);
          const m = match[2];
          const ampm = h >= 12 ? 'PM' : 'AM';
          const h12 = h % 12 || 12;
          return `${h12}:${m} ${ampm}`;
        }
      }
      return '--:--';
    }
    return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
  } catch {
    return '--:--';
  }
};

/**
 * Formats flight stops (e.g. "Non-stop", "1 stop", "2 stops").
 * Guaranteed never to return "undefined stop" or NaN.
 */
export const formatStops = (stops) => {
  if (stops === 0 || stops === '0') return 'Non-stop';
  if (stops === 1 || stops === '1') return '1 stop';
  if (typeof stops === 'number' && stops > 1) return `${stops} stops`;
  if (typeof stops === 'string') {
    const parsed = parseInt(stops, 10);
    if (!isNaN(parsed) && parsed > 1) return `${parsed} stops`;
    if (parsed === 0) return 'Non-stop';
    if (parsed === 1) return '1 stop';
  }
  return 'Direct flight';
};

/**
 * Formats monetary amounts with currency symbol.
 * Guaranteed never to return NaN.
 */
export const formatCurrency = (amount, currency = 'INR') => {
  const num = Number(amount);
  const symbol = currency === 'INR' ? '₹' : (currency === 'EUR' ? '€' : '$');
  if (isNaN(num)) return `${symbol}0.00`;
  return `${symbol}${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

/**
 * Minimizes personal information exposure by displaying only the birth year.
 */
export const maskDobYear = (dob) => {
  if (!dob || typeof dob !== 'string') return '';
  const match = dob.match(/\b(\d{4})\b/);
  return match ? `Birth Year: ${match[1]}` : 'Adult';
};

/**
 * Generates a client-side idempotency key for booking orders.
 */
export const generateIdempotencyKey = (userId = 'guest', offerId = 0) => {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 10);
  return `web_${userId}_${offerId}_${timestamp}_${random}`;
};

export const bookingService = {
  /**
   * Revalidate live offer availability and price before booking.
   * Accessible without authentication (POST /api/v1/bookings/revalidate).
   * @param {number} flightOfferId
   * @returns {Promise<{ is_valid: boolean, current_amount: number, currency: string, price_changed: boolean, message?: string }>}
   */
  revalidateOffer: async (flightOfferId) => {
    const response = await api.post('/bookings/revalidate', {
      flight_offer_id: Number(flightOfferId),
    });
    return response.data;
  },

  /**
   * Create a flight booking order with explicit consent and database idempotency.
   * Requires authentication (POST /api/v1/bookings).
   * @param {object} bookingPayload
   * @param {string} idempotencyKey
   * @returns {Promise<object>}
   */
  createBooking: async (bookingPayload, idempotencyKey = null) => {
    const key = idempotencyKey || generateIdempotencyKey('user', bookingPayload.flight_offer_id);
    const response = await api.post('/bookings', bookingPayload, {
      headers: {
        'Idempotency-Key': key,
      },
    });
    return response.data;
  },

  /**
   * Retrieve authenticated user booking history.
   * Requires authentication (GET /api/v1/bookings).
   * @returns {Promise<Array<object>>}
   */
  getBookingHistory: async () => {
    const response = await api.get('/bookings');
    return response.data;
  },

  /**
   * Retrieve single booking details with strict ownership verification.
   * Requires authentication (GET /api/v1/bookings/{booking_id}).
   * @param {number} bookingId
   * @returns {Promise<object>}
   */
  getBookingDetail: async (bookingId) => {
    const response = await api.get(`/bookings/${bookingId}`);
    return response.data;
  },

  /**
   * Retrieve saved passenger profiles for the current user.
   * Requires authentication (GET /api/v1/auth/passengers).
   * @returns {Promise<Array<object>>}
   */
  getSavedPassengers: async () => {
    const response = await api.get('/auth/passengers');
    return response.data;
  },

  /**
   * Save a passenger profile for quick checkout.
   * Requires authentication (POST /api/v1/auth/passengers).
   * @param {object} passengerData
   * @returns {Promise<object>}
   */
  savePassengerProfile: async (passengerData) => {
    const response = await api.post('/auth/passengers', passengerData);
    return response.data;
  },
};

export default bookingService;
