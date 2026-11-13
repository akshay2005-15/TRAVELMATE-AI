import React, { useState } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Plane,
  Clock,
  Users,
  Mail,
  Copy,
  Check,
  ArrowRight,
  ShieldCheck,
  FlaskConical,
  MessageSquare,
  Ticket
} from 'lucide-react';
import { maskEmail, formatDate, formatTime, formatStops } from '../services/bookingService';

export default function BookingResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  const state = location.state || {};
  const { status = 'confirmed', booking, itinerary, error } = state;

  const handleCopyPnr = (pnr) => {
    if (!pnr) return;
    navigator.clipboard.writeText(pnr);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  // If page was loaded directly without state
  if (!booking && !error) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center space-y-4">
        <div className="w-16 h-16 bg-slate-100 text-slate-400 rounded-3xl flex items-center justify-center mx-auto">
          <Plane className="w-8 h-8 -rotate-45" />
        </div>
        <h2 className="text-2xl font-black text-slate-800 tracking-tight">No Booking Record Found</h2>
        <p className="text-slate-500 text-xs sm:text-sm max-w-md mx-auto leading-relaxed">
          You can review your confirmed flight reservations in your account booking history.
        </p>
        <div className="pt-2 flex justify-center gap-3">
          <Link
            to="/bookings"
            className="px-6 py-3 rounded-2xl bg-brand-600 text-white font-bold text-xs shadow-md shadow-brand-500/20 hover:bg-brand-700 transition-colors"
          >
            My Bookings
          </Link>
          <Link
            to="/flights"
            className="px-6 py-3 rounded-2xl bg-slate-100 text-slate-700 font-bold text-xs hover:bg-slate-200 transition-colors"
          >
            Search Flights
          </Link>
        </div>
      </div>
    );
  }

  // Case 1: Status Uncertain
  if (status === 'uncertain') {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-6">
        <div className="bg-white rounded-3xl border border-amber-200 shadow-xl p-6 sm:p-8 text-center space-y-4">
          <div className="w-16 h-16 bg-amber-100 text-amber-700 rounded-3xl flex items-center justify-center mx-auto shadow-inner">
            <AlertTriangle className="w-8 h-8" />
          </div>

          <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Booking Status Uncertain
          </h2>

          <div className="p-5 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-900 text-left space-y-2.5 font-medium leading-relaxed">
            <p className="font-bold text-sm text-amber-950">Provider Connection Interrupted</p>
            <p>
              {error || 'A network timeout occurred while awaiting confirmation from the airline provider.'}
            </p>
            <p className="font-bold text-amber-950 pt-1">
              🔒 Duplicate Ticketing Protection Active: To prevent multiple charges or duplicate ticket issuance, automatic retries are blocked. Our backend has securely locked your booking intent.
            </p>
          </div>

          <p className="text-xs text-slate-500 max-w-lg mx-auto leading-relaxed">
            Please check your <strong>My Bookings</strong> section in a few minutes or contact support before attempting to create a new reservation.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
            <Link
              to="/bookings"
              className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs shadow-md shadow-brand-500/20 transition-all active:scale-95"
            >
              Check My Bookings
            </Link>
            <Link
              to="/chat"
              className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors"
            >
              Ask AI Assistant
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Case 2: Status Failed / Rejected
  if (status === 'failed') {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-6">
        <div className="bg-white rounded-3xl border border-rose-200 shadow-xl p-6 sm:p-8 text-center space-y-4">
          <div className="w-16 h-16 bg-rose-100 text-rose-700 rounded-3xl flex items-center justify-center mx-auto shadow-inner">
            <XCircle className="w-8 h-8" />
          </div>

          <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Booking Could Not Be Completed
          </h2>

          <p className="text-xs sm:text-sm text-slate-600 max-w-md mx-auto leading-relaxed">
            {error || 'The airline provider was unable to confirm this reservation.'}
          </p>

          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-600 max-w-md mx-auto font-medium">
            🛡️ <strong>Zero Charges Made:</strong> No funds were deducted from your account. You can select an alternative flight safely.
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
            <Link
              to="/flights"
              className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs shadow-md shadow-brand-500/20 transition-all active:scale-95"
            >
              Search Alternative Flights
            </Link>
            <Link
              to="/chat"
              className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors"
            >
              Return to Assistant
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Case 3: Confirmed Booking Outcome
  const pnr = booking?.booking_reference || 'PENDING-PNR';
  const providerId = booking?.provider_booking_id || 'N/A';
  const isMock = booking?.is_simulation || booking?.data_source === 'mock_simulation';
  const isDuffel = booking?.data_source === 'duffel_sandbox';

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-6">
      {/* Success Hero Card */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xl overflow-hidden">
        {/* Header Ribbon */}
        <div className="bg-gradient-to-r from-emerald-600 via-teal-600 to-brand-700 p-6 sm:p-8 text-white text-center sm:text-left flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white shrink-0 shadow-inner">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div>
              <span className="text-xs uppercase font-extrabold tracking-wider text-emerald-100 block">
                Order Completed Successfully
              </span>
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white mt-0.5">
                Flight Reservation Confirmed!
              </h1>
            </div>
          </div>

          <div className="shrink-0">
            {isMock && (
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-black bg-amber-400 text-slate-900 shadow-sm">
                <FlaskConical className="w-3.5 h-3.5 text-slate-900" />
                SIMULATION / MOCK ORDER
              </span>
            )}
            {isDuffel && (
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-black bg-blue-400 text-slate-900 shadow-sm">
                <ShieldCheck className="w-3.5 h-3.5 text-slate-900" />
                DUFFEL TEST SANDBOX
              </span>
            )}
          </div>
        </div>

        <div className="p-6 sm:p-8 space-y-6">
          {/* Booking Reference Box */}
          <div className="p-6 rounded-3xl bg-slate-50 border border-slate-200/90 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                Airline Booking Reference (PNR)
              </span>
              <div className="text-2xl sm:text-4xl font-black text-slate-900 tracking-wider font-mono mt-1">
                {pnr}
              </div>
              <span className="text-xs text-slate-500 font-mono font-medium block mt-1">
                Provider Order ID: {providerId}
              </span>
            </div>

            <button
              type="button"
              onClick={() => handleCopyPnr(pnr)}
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white hover:bg-slate-100 border border-slate-300 text-xs font-bold text-slate-700 shadow-xs transition-all active:scale-95"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-emerald-600" />
                  <span className="text-emerald-700 font-bold">PNR Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 text-slate-500" />
                  <span>Copy Reference</span>
                </>
              )}
            </button>
          </div>

          {/* Itinerary Overview */}
          {(() => {
            const flight = itinerary || booking?.flight_offer || (booking?.origin_iata ? booking : null);
            if (!flight) return null;

            const departureTime = flight.departure_time || booking?.departure_time || booking?.departure_date;
            const arrivalTime = flight.arrival_time || booking?.arrival_time || booking?.arrival_date;
            const stops = flight.stops !== undefined ? flight.stops : booking?.stops;

            return (
              <div className="p-6 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white font-black text-xs flex items-center justify-center shadow-xs">
                      {flight.airline_code || 'FL'}
                    </div>
                    <span className="text-sm font-extrabold text-slate-900">{flight.airline_name || 'Airline'}</span>
                    <span className="text-xs font-mono font-semibold text-slate-400">{flight.flight_number || ''}</span>
                  </div>
                  <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200 uppercase">
                    {booking?.status || 'CONFIRMED'}
                  </span>
                </div>

                <div className="grid grid-cols-3 items-center text-center sm:text-left py-2">
                  <div>
                    <div className="text-xl sm:text-2xl font-black text-slate-900">
                      {formatTime(departureTime)}
                    </div>
                    <div className="text-sm font-bold text-slate-700">{flight.origin_iata}</div>
                    <div className="text-[11px] text-slate-400 font-medium">{formatDate(departureTime)}</div>
                  </div>

                  <div className="flex flex-col items-center">
                    <Plane className="w-5 h-5 text-brand-600 -rotate-45 mb-1" />
                    <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                      {formatStops(stops)}
                    </span>
                  </div>

                  <div className="text-right">
                    <div className="text-xl sm:text-2xl font-black text-slate-900">
                      {formatTime(arrivalTime)}
                    </div>
                    <div className="text-sm font-bold text-slate-700">{flight.destination_iata}</div>
                    <div className="text-[11px] text-slate-400 font-medium">{formatDate(arrivalTime)}</div>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Passengers & Confirmation Delivery */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 text-xs space-y-2">
              <span className="font-bold text-slate-700 uppercase tracking-wider block flex items-center gap-1.5">
                <Users className="w-4 h-4 text-brand-600" />
                <span>{isMock ? 'Simulated Passengers' : 'Ticketed Passengers'}</span>
              </span>
              {booking?.passengers?.map((p, idx) => (
                <div key={idx} className="font-bold text-slate-900 text-sm">
                  {p.first_name} {p.last_name}
                </div>
              ))}
            </div>

            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 text-xs space-y-2">
              <span className="font-bold text-slate-700 uppercase tracking-wider block flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-brand-600" />
                <span>E-Ticket Dispatch</span>
              </span>
              <p className="text-slate-800 font-mono font-bold">
                {maskEmail(booking?.contact_email)}
              </p>
              <p className="text-[11px] text-slate-400">
                A copy of your flight itinerary has been dispatched to this address.
              </p>
            </div>
          </div>

          {/* Academic / Viva Transparency Guarantee Notice */}
          <div className="p-4 rounded-2xl bg-slate-100/90 border border-slate-200 text-xs text-slate-600 space-y-1 font-medium">
            <span className="font-bold text-slate-800 block">System Transparency Notice</span>
            <p className="leading-relaxed">
              {isMock
                ? 'This booking was generated via authentic offline simulation for final-year project demonstration. No real airline tickets or charges were processed.'
                : 'This booking was placed in Duffel API sandbox test mode with simulated settlement.'}
            </p>
          </div>

          {/* Bottom Actions */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-100">
            <Link
              to="/flights"
              className="w-full sm:w-auto px-6 py-3 rounded-2xl border border-slate-300 text-xs sm:text-sm font-bold text-slate-600 hover:bg-slate-50 transition-colors text-center"
            >
              Search More Flights
            </Link>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              <Link
                to="/chat"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-5 py-3 rounded-2xl bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-bold hover:bg-indigo-100 transition-colors"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>Chat with Assistant</span>
              </Link>
              <Link
                to="/bookings"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3 rounded-2xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-xs sm:text-sm font-bold shadow-md shadow-brand-500/25 transition-all active:scale-95"
              >
                <span>View in My Bookings</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
