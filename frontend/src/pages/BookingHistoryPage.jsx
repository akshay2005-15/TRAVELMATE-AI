import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plane,
  Calendar,
  CreditCard,
  ShieldCheck,
  FlaskConical,
  ArrowRight,
  Loader2,
  AlertCircle,
  Sparkles,
  Ticket,
  Clock
} from 'lucide-react';
import { bookingService, formatDate, formatStops, formatCurrency } from '../services/bookingService';

export default function BookingHistoryPage() {
  const navigate = useNavigate();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchBookings = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await bookingService.getBookingHistory();
      setBookings(data || []);
    } catch (err) {
      console.error('Failed to load booking history:', err);
      const msg = err.response?.data?.detail || 'Unable to retrieve your booking records. Please check your connection.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBookings();
  }, []);

  const renderStatusBadge = (status) => {
    const s = (status || 'confirmed').toLowerCase();
    if (s === 'confirmed') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
          ● CONFIRMED
        </span>
      );
    }
    if (s === 'uncertain') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
          ▲ UNCERTAIN
        </span>
      );
    }
    if (s === 'processing' || s === 'pending') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
          ◌ PROCESSING
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
        ✕ FAILED
      </span>
    );
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-200/80">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-50 text-brand-700 text-xs font-bold mb-2 border border-brand-200/60">
            <Ticket className="w-3.5 h-3.5 text-brand-500" />
            <span>Travel History & Manifest</span>
          </div>
          <h1 className="text-2xl sm:text-4xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            <span>My Flight Bookings</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Review your confirmed itineraries, PNR references, and provider settlement records.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/flights"
            className="px-5 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors shadow-2xs"
          >
            Search Flights
          </Link>
          <Link
            to="/chat"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-brand-500/20 transition-all active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Assistant</span>
          </Link>
        </div>
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
          <p className="text-xs text-slate-400 font-semibold">Loading your flight records...</p>
        </div>
      )}

      {/* Error View */}
      {!loading && error && (
        <div className="p-6 rounded-3xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Error Loading Bookings</p>
              <p className="text-xs text-rose-700 mt-1">{error}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={fetchBookings}
            className="px-4 py-2 rounded-xl bg-rose-600 text-white text-xs font-bold hover:bg-rose-700 shrink-0 shadow-xs"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && bookings.length === 0 && (
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center max-w-lg mx-auto space-y-4 shadow-sm">
          <div className="w-16 h-16 bg-slate-100 text-slate-400 rounded-3xl flex items-center justify-center mx-auto">
            <Plane className="w-8 h-8 text-slate-400 -rotate-45" />
          </div>
          <h3 className="text-lg font-black text-slate-900 tracking-tight">No Flight Bookings Found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
            You haven't placed any flight reservations yet. Use our flight search engine or talk to the TRAVELMATE AI Assistant to plan and book your next journey!
          </p>
          <div className="pt-2 flex justify-center gap-3">
            <Link
              to="/flights"
              className="px-6 py-2.5 rounded-2xl bg-gradient-to-r from-brand-600 to-indigo-600 text-white text-xs font-bold hover:from-brand-500 hover:to-indigo-500 shadow-md shadow-brand-500/20 transition-all active:scale-95"
            >
              Explore Flights
            </Link>
            <Link
              to="/chat"
              className="px-6 py-2.5 rounded-2xl bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-bold hover:bg-indigo-100 transition-colors"
            >
              Chat with Assistant
            </Link>
          </div>
        </div>
      )}

      {/* Bookings List */}
      {!loading && !error && bookings.length > 0 && (
        <div className="space-y-4">
          {bookings.map((b) => {
            const isMock = b.is_simulation || b.data_source === 'mock_simulation';
            const isDuffel = b.data_source === 'duffel_sandbox';

            return (
              <div
                key={b.id}
                className="bg-white rounded-3xl border border-slate-200/90 hover:border-brand-400 p-6 shadow-sm hover:shadow-lg transition-all flex flex-col md:flex-row md:items-center justify-between gap-5 group"
              >
                {/* Left: Carrier, PNR & Route */}
                <div className="space-y-2.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="font-mono text-sm font-black text-slate-900 tracking-wider bg-slate-100 px-3 py-1 rounded-xl border border-slate-200">
                      {b.booking_reference || 'NO-PNR'}
                    </span>
                    {renderStatusBadge(b.status)}
                    {isMock && (
                      <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-300">
                        <FlaskConical className="w-3 h-3 text-amber-600" />
                        SIMULATION
                      </span>
                    )}
                    {isDuffel && (
                      <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-300">
                        <ShieldCheck className="w-3 h-3 text-blue-600" />
                        DUFFEL SANDBOX
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-sm">
                    <span className="font-extrabold text-slate-900">
                      {b.airline_name || 'Airline'} {b.flight_number ? `(${b.flight_number})` : ''}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="font-bold text-brand-700 bg-brand-50 px-2.5 py-0.5 rounded-lg border border-brand-200/50">
                      {b.origin_iata || '---'} ➔ {b.destination_iata || '---'}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs text-slate-500 font-medium">
                      Depart: {formatDate(b.departure_time || b.departure_date)}
                    </span>
                    {b.stops !== undefined && (
                      <>
                        <span className="text-slate-300">•</span>
                        <span className="text-xs text-slate-500 font-medium">
                          {formatStops(b.stops)}
                        </span>
                      </>
                    )}
                  </div>

                  <div className="text-xs text-slate-400 font-medium">
                    Booked on: {formatDate(b.created_at)}
                  </div>
                </div>

                {/* Right: Fare & View Action */}
                <div className="flex items-center justify-between md:justify-end gap-6 pt-3 md:pt-0 border-t md:border-t-0 border-slate-100">
                  <div className="text-left md:text-right">
                    <span className="text-[11px] text-slate-400 block font-bold uppercase tracking-wider">
                      {isMock ? 'Simulated Fare' : 'Total Paid'}
                    </span>
                    <span className="text-xl font-black text-slate-900">
                      {formatCurrency(b.total_amount, b.currency)}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => navigate(`/bookings/${b.id}`)}
                    className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-brand-50 hover:bg-brand-100 text-brand-700 text-xs font-bold border border-brand-200/80 transition-all active:scale-95 shrink-0 shadow-2xs group-hover:bg-brand-600 group-hover:text-white group-hover:border-transparent group-hover:shadow-md"
                  >
                    <span>View Itinerary</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
