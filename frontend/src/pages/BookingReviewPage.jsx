import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import {
  Plane,
  Clock,
  Luggage,
  Users,
  Mail,
  Phone,
  ShieldCheck,
  FlaskConical,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Lock,
  Loader2,
  ArrowRight,
  ArrowLeft
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  bookingService,
  maskEmail,
  maskPhone,
  maskPassport,
  maskDobYear,
  formatDate,
  formatTime,
  formatStops,
  formatCurrency,
  generateIdempotencyKey
} from '../services/bookingService';

export default function BookingReviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated } = useAuth();

  // Retrieve draft from state or sessionStorage
  const [draft, setDraft] = useState(() => {
    if (location.state?.offer && location.state?.passengers) {
      return location.state;
    }
    const saved = sessionStorage.getItem('travelmate_booking_draft');
    return saved ? JSON.parse(saved) : null;
  });

  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  
  // Price Change Approval State (HTTP 409)
  const [priceChangeData, setPriceChangeData] = useState(null);

  // Mandatory explicit confirmation state
  const [disclaimerAccepted, setDisclaimerAccepted] = useState(false);
  const [priceChangeCheckbox, setPriceChangeCheckbox] = useState(false);

  // Requirement 1: Reset checkbox acceptance whenever ANY flight offer field, fare, or passenger details change
  useEffect(() => {
    setDisclaimerAccepted(false);
  }, [
    draft?.offer?.id,
    draft?.offer?.origin_iata,
    draft?.offer?.destination_iata,
    draft?.offer?.departure_time,
    draft?.offer?.arrival_time,
    draft?.offer?.stops,
    draft?.offer?.cabin_class,
    draft?.offer?.total_amount,
    draft?.offer?.currency,
    JSON.stringify(draft?.offer || {}),
    draft?.passengers?.length,
    JSON.stringify(draft?.passengers || []),
    draft?.contact?.email,
    draft?.contact?.phone,
    JSON.stringify(draft?.contact || {})
  ]);

  // Requirement 2: Reset price change checkbox whenever price change data is received
  useEffect(() => {
    if (priceChangeData) {
      setPriceChangeCheckbox(false);
    }
  }, [priceChangeData]);

  // Client-side idempotency key generated once per review session
  const [idempotencyKey] = useState(() =>
    generateIdempotencyKey(user?.id || 'usr', draft?.offer?.id || 0)
  );

  if (!draft || !draft.offer) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center space-y-4">
        <div className="w-16 h-16 bg-slate-100 text-slate-400 rounded-3xl flex items-center justify-center mx-auto">
          <Plane className="w-8 h-8 -rotate-45" />
        </div>
        <h2 className="text-2xl font-black text-slate-800 tracking-tight">No Booking in Progress</h2>
        <p className="text-slate-500 text-xs sm:text-sm max-w-md mx-auto leading-relaxed">
          Please select a flight offer and fill in traveler details first.
        </p>
        <div className="pt-2">
          <Link
            to="/flights"
            className="px-6 py-3 rounded-2xl bg-gradient-to-r from-brand-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-brand-500/20 hover:from-brand-500 hover:to-indigo-500 transition-all active:scale-95"
          >
            Search Flights
          </Link>
        </div>
      </div>
    );
  }

  const { offer, passengers = [], contact = {} } = draft;
  const isMock = offer.data_source === 'mock_simulation' || offer.is_simulation;
  const isDuffel = offer.data_source === 'duffel_sandbox';

  const formatDuration = (mins) => {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  // Dispatch final booking confirmation to backend
  const executeBooking = async (priceAccepted = false, updatedAmount = null) => {
    if (!isAuthenticated) {
      sessionStorage.setItem('travelmate_booking_draft', JSON.stringify(draft));
      navigate('/login?redirect=/booking/review');
      return;
    }

    setSubmitting(true);
    setErrorMessage('');

    const targetAmount = updatedAmount !== null ? updatedAmount : offer.total_amount;

    const payload = {
      flight_offer_id: Number(offer.id),
      passengers: passengers.map((p) => ({
        first_name: p.first_name,
        last_name: p.last_name,
        date_of_birth: p.date_of_birth,
        gender: p.gender || 'other',
        passport_number: p.passport_number || null,
      })),
      contact: {
        email: contact.email,
        phone: contact.phone,
      },
      confirmed_by_user: Boolean(priceAccepted ? priceChangeCheckbox : disclaimerAccepted),
      expected_amount: Number(targetAmount),
      expected_currency: offer.currency || 'INR',
      price_change_accepted: priceAccepted,
      idempotency_key: idempotencyKey,
    };

    try {
      const result = await bookingService.createBooking(payload, idempotencyKey);
      sessionStorage.removeItem('travelmate_booking_draft');
      sessionStorage.removeItem('travelmate_selected_offer');

      navigate('/booking/result', {
        state: {
          status: 'confirmed',
          booking: result,
          itinerary: offer,
          passengers,
          contact,
        },
      });
    } catch (err) {
      console.error('Booking submission error:', err);
      const res = err.response;

      if (!res) {
        navigate('/booking/result', {
          state: {
            status: 'uncertain',
            error: 'Network connection dropped before receiving confirmation from provider. Automatic retry is blocked.',
            itinerary: offer,
            passengers,
            contact,
          },
        });
        return;
      }

      if (res.status === 401) {
        navigate('/login?redirect=/booking/review');
        return;
      }

      const detail = res.data?.detail;

      if (res.status === 409 && (detail?.error_code === 'price_changed' || detail?.price_changed)) {
        setPriceChangeData({
          originalAmount: detail.original_amount || offer.total_amount,
          currentAmount: detail.current_amount,
          currency: detail.currency || offer.currency,
          message: detail.message || 'The airline has updated the live fare for this flight.',
        });
        setSubmitting(false);
        return;
      }

      if (res.status === 504 || detail?.error_code === 'provider_uncertain') {
        navigate('/booking/result', {
          state: {
            status: 'uncertain',
            error: typeof detail === 'object' ? detail.message : detail,
            itinerary: offer,
            passengers,
            contact,
          },
        });
        return;
      }

      if (res.status === 410 || detail?.error_code === 'offer_expired') {
        navigate('/booking/result', {
          state: {
            status: 'failed',
            error: 'This flight offer has expired from the airline inventory. Please perform a fresh flight search.',
            itinerary: offer,
          },
        });
        return;
      }

      const msg = typeof detail === 'object' ? detail.message : (detail || 'Booking request failed.');
      setErrorMessage(msg);
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-6">
      {/* Navigation header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <button
          type="button"
          onClick={() => navigate('/booking/passengers')}
          className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-500 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Passenger Details</span>
        </button>

        <div className="flex items-center gap-2.5 text-xs font-bold text-slate-500 bg-white px-4 py-2 rounded-2xl border border-slate-200/80 shadow-2xs">
          <span className="w-6 h-6 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs font-black shadow-xs">
            ✓
          </span>
          <span className="text-slate-500 font-semibold">Passenger Details</span>
          <span className="text-slate-300">➔</span>
          <span className="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center text-xs font-black shadow-xs">
            2
          </span>
          <span className="text-brand-700 font-extrabold">Review & Confirm</span>
        </div>
      </div>

      {/* Main Review Card */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm overflow-hidden">
        {/* Banner */}
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 p-6 sm:p-8 text-white">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="text-xs uppercase tracking-wider font-extrabold text-brand-300 block">
                Step 2: Formal Booking Review
              </span>
              <h2 className="text-xl sm:text-3xl font-black tracking-tight mt-1 text-white">
                Review Itinerary & Passenger Manifest
              </h2>
            </div>

            <div>
              {isMock && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30 backdrop-blur-sm">
                  <FlaskConical className="w-3.5 h-3.5" />
                  SIMULATION / MOCK ORDER
                </span>
              )}
              {isDuffel && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-400/20 text-blue-300 border border-blue-400/30 backdrop-blur-sm">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  DUFFEL TEST SANDBOX
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="p-6 sm:p-8 space-y-6">
          {/* Section 1: Flight Itinerary Details */}
          <div className="p-6 rounded-3xl bg-slate-50/70 border border-slate-200/80 space-y-4">
            <div className="flex items-center justify-between pb-3.5 border-b border-slate-200/70">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white flex items-center justify-center font-black text-xs shadow-xs">
                  {offer.airline_code}
                </div>
                <div>
                  <h3 className="font-extrabold text-slate-900 text-sm">{offer.airline_name}</h3>
                  <span className="text-xs font-mono font-semibold text-slate-500">Flight {offer.flight_number}</span>
                </div>
              </div>

              <div className="text-right">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Travel Date</span>
                <span className="text-xs font-black text-slate-800">{formatDate(offer.departure_time)}</span>
              </div>
            </div>

            {/* Flight Timings Graphic */}
            <div className="grid grid-cols-3 items-center gap-2 text-center sm:text-left py-1">
              <div>
                <div className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                  {formatTime(offer.departure_time)}
                </div>
                <div className="text-sm font-bold text-slate-700">{offer.origin_iata}</div>
                <div className="text-xs text-slate-400 font-medium">Scheduled Departure</div>
              </div>

              <div className="flex flex-col items-center">
                <span className="text-xs font-semibold text-slate-500 flex items-center gap-1 mb-1">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>{formatDuration(offer.duration_minutes)}</span>
                </span>
                <div className="w-full flex items-center justify-center py-1">
                  <div className="h-0.5 flex-1 bg-slate-300" />
                  <Plane className="w-4 h-4 text-brand-600 mx-2 -rotate-45" />
                  <div className="h-0.5 flex-1 bg-slate-300" />
                </div>
                <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200 mt-1">
                  {formatStops(offer.stops)}
                </span>
              </div>

              <div className="text-right">
                <div className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                  {formatTime(offer.arrival_time)}
                </div>
                <div className="text-sm font-bold text-slate-700">{offer.destination_iata}</div>
                <div className="text-xs text-slate-400 font-medium">Scheduled Arrival</div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-3.5 border-t border-slate-200/70 text-xs text-slate-600">
              <div className="flex items-center gap-3">
                <span className="capitalize font-bold text-slate-800 bg-white px-3 py-1 rounded-xl border border-slate-200 shadow-2xs">
                  Cabin: {offer.cabin_class?.replace('_', ' ') || 'Economy'}
                </span>
                <span className="inline-flex items-center gap-1.5 font-medium">
                  <Luggage className="w-4 h-4 text-slate-400" />
                  <span>{offer.baggage_included || 'Standard Check-in & Cabin included'}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Passenger Manifest & Masked Contact */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Passengers */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-3">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 pb-2.5 border-b border-slate-100">
                <Users className="w-4 h-4 text-brand-600" />
                <span>Travelers ({passengers.length})</span>
              </h4>

              <div className="space-y-3">
                {passengers.map((p, idx) => (
                  <div key={idx} className="text-xs space-y-1">
                    <p className="text-sm font-bold text-slate-900">
                      {p.first_name} {p.last_name}
                    </p>
                    <p className="text-slate-500 font-medium">
                      <span className="capitalize">{p.gender}</span> • {maskDobYear(p.date_of_birth)}
                    </p>
                    {p.passport_number && (
                      <p className="text-slate-600 font-mono font-semibold">
                        Passport: {maskPassport(p.passport_number)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Contact Delivery */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-3">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 pb-2.5 border-b border-slate-100">
                <Mail className="w-4 h-4 text-brand-600" />
                <span>E-Ticket Delivery Contact</span>
              </h4>

              <div className="space-y-2.5 text-xs">
                <div className="flex items-center gap-2 text-slate-700">
                  <Mail className="w-4 h-4 text-slate-400" />
                  <span className="font-mono font-bold">{maskEmail(contact.email)}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-700">
                  <Phone className="w-4 h-4 text-slate-400" />
                  <span className="font-mono font-bold">{maskPhone(contact.phone)}</span>
                </div>
                <p className="text-[11px] text-slate-400 pt-1 font-medium">
                  Confirmation e-ticket and airline PNR reference will be dispatched to this email.
                </p>
              </div>
            </div>
          </div>

          {/* Section 3: Fare Breakdown */}
          <div className="p-6 rounded-3xl bg-slate-50/70 border border-slate-200/80 space-y-2.5">
            <div className="flex justify-between items-center text-xs text-slate-600 font-medium">
              <span>Base Airfare</span>
              <span>{formatCurrency(offer.total_amount * 0.85, offer.currency)}</span>
            </div>
            <div className="flex justify-between items-center text-xs text-slate-600 font-medium">
              <span>Aviation Taxes & Carrier Surcharges</span>
              <span>{formatCurrency(offer.total_amount * 0.15, offer.currency)}</span>
            </div>
            <div className="flex justify-between items-center pt-3 border-t border-slate-200 text-base font-black text-slate-900">
              <span>Total Amount Due</span>
              <span className="text-2xl text-brand-600">
                {formatCurrency(offer.total_amount, offer.currency)}
              </span>
            </div>
          </div>

          {/* Section 4: Mandatory Legal / Order Disclaimer Box with Mock Disclosure Checkbox */}
          <div className="p-6 rounded-3xl bg-amber-50/90 border border-amber-300 shadow-sm space-y-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-bold text-amber-950 text-sm">
                <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
                <span>Mandatory Mock-Booking & Simulation Disclosure</span>
              </div>
              <span className="px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-amber-200/80 text-amber-950 border border-amber-300">
                Academic Simulation
              </span>
            </div>

            <div className="text-xs text-amber-950 leading-relaxed space-y-1.5 bg-amber-100/70 p-4 rounded-2xl border border-amber-200 font-medium">
              <p>
                <strong>Academic Demonstration Notice:</strong> TRAVELMATE AI is a final-year academic engineering demonstration project. 
                All bookings are processed via an offline simulation engine or provider sandbox.
              </p>
              <p>
                <strong>Zero Financial Liability:</strong> No real payment is charged, no credit/debit card is required, and no live commercial airline ticket or seat reservation will be issued.
              </p>
            </div>

            {/* Mandatory Explicit User Authorization Checkbox */}
            <label className="flex items-start gap-3 p-4 rounded-2xl bg-white border-2 border-amber-300 hover:border-amber-400 shadow-xs cursor-pointer select-none transition-all">
              <input
                type="checkbox"
                id="disclaimer-checkbox"
                checked={disclaimerAccepted}
                onChange={(e) => setDisclaimerAccepted(e.target.checked)}
                className="mt-0.5 h-5 w-5 rounded border-amber-400 text-brand-600 focus:ring-brand-500 cursor-pointer"
              />
              <span className="text-xs text-slate-800 leading-relaxed font-bold">
                I acknowledge that this is a simulated academic demonstration booking with no real payment or airline ticket issuance, and I explicitly confirm the passenger manifest and flight itinerary details above.
              </span>
            </label>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2.5 animate-in fade-in">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Booking Request Blocked</p>
                <p className="mt-0.5 font-medium">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Confirmation Action */}
          <div className="pt-3 flex flex-col sm:flex-row items-center justify-between gap-4">
            <button
              type="button"
              disabled={submitting}
              onClick={() => navigate('/booking/passengers')}
              className="w-full sm:w-auto px-6 py-3 rounded-2xl border border-slate-300 text-xs sm:text-sm font-bold text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Modify Details
            </button>

            <div className="w-full sm:w-auto flex flex-col items-stretch sm:items-end gap-2">
              <button
                type="button"
                id="confirm-booking-btn"
                disabled={submitting || !disclaimerAccepted}
                onClick={() => executeBooking(false)}
                className={`w-full sm:w-auto inline-flex items-center justify-center gap-2 px-9 py-4 rounded-2xl text-sm sm:text-base font-bold transition-all ${
                  submitting
                    ? 'bg-slate-400 text-white cursor-not-allowed shadow-none'
                    : !disclaimerAccepted
                    ? 'bg-slate-200 text-slate-400 border border-slate-300 cursor-not-allowed shadow-none'
                    : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-xl shadow-emerald-600/25 active:scale-95'
                }`}
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Securing Order with Provider...</span>
                  </>
                ) : (
                  <>
                    <Lock className="w-4 h-4" />
                    <span>Authorize & Confirm Booking</span>
                  </>
                )}
              </button>

              {!disclaimerAccepted && !submitting && (
                <p className="text-[11px] text-amber-800 font-semibold text-center sm:text-right flex items-center justify-center sm:justify-end gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span>Please review and check the mock-booking disclosure above to authorize.</span>
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Price Change Modal (HTTP 409) */}
      {priceChangeData && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <h3 className="text-xl font-black text-slate-900 tracking-tight">
              Airline Price Change Alert
            </h3>

            <p className="text-xs text-slate-600 leading-relaxed font-medium">
              {priceChangeData.message || 'The airline fare has changed during live seat verification.'}
            </p>

            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2 text-xs">
              <div className="flex justify-between text-slate-500 font-medium">
                <span>Original Expected Fare:</span>
                <span className="line-through">
                  {priceChangeData.currency} {Number(priceChangeData.originalAmount).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between font-bold text-slate-900 text-sm">
                <span>Updated Live Fare:</span>
                <span className="text-brand-600 text-base font-black">
                  {priceChangeData.currency} {Number(priceChangeData.currentAmount).toLocaleString()}
                </span>
              </div>
            </div>

            {/* Explicit Price Change Acceptance Checkbox */}
            <label className="flex items-start gap-2.5 p-3.5 rounded-2xl bg-amber-50/80 border border-amber-300 cursor-pointer select-none">
              <input
                type="checkbox"
                id="price-change-checkbox"
                checked={priceChangeCheckbox}
                onChange={(e) => setPriceChangeCheckbox(e.target.checked)}
                className="mt-0.5 h-4.5 w-4.5 rounded border-amber-400 text-brand-600 focus:ring-brand-500 cursor-pointer"
              />
              <span className="text-xs text-amber-950 font-bold">
                I explicitly authorize this simulated booking at the updated live fare of {priceChangeData.currency} {Number(priceChangeData.currentAmount).toLocaleString()}.
              </span>
            </label>

            <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-3">
              <button
                type="button"
                onClick={() => {
                  setPriceChangeData(null);
                  setPriceChangeCheckbox(false);
                  navigate('/flights');
                }}
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-slate-300 text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancel & Search Others
              </button>

              <button
                type="button"
                disabled={!priceChangeCheckbox || submitting}
                onClick={() => {
                  const newAmt = priceChangeData.currentAmount;
                  setPriceChangeData(null);
                  executeBooking(true, newAmt);
                }}
                className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold transition-all ${
                  !priceChangeCheckbox || submitting
                    ? 'bg-slate-300 text-slate-500 cursor-not-allowed shadow-none'
                    : 'bg-brand-600 hover:bg-brand-700 text-white shadow-md shadow-brand-500/20 active:scale-95'
                }`}
              >
                Accept New Price & Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
