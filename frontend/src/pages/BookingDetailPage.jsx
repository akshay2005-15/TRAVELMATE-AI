import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Plane,
  Clock,
  Luggage,
  Users,
  Mail,
  Phone,
  ShieldCheck,
  FlaskConical,
  AlertCircle,
  ShieldAlert,
  ArrowLeft,
  Copy,
  Check,
  Loader2,
  Calendar,
  Lock,
  Ticket
} from 'lucide-react';
import {
  bookingService,
  maskEmail,
  maskPhone,
  maskPassport,
  formatDate,
  formatTime,
  formatStops,
  formatCurrency,
  maskDobYear
} from '../services/bookingService';

export default function BookingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await bookingService.getBookingDetail(id);
        setBooking(data);
      } catch (err) {
        console.error('Failed to load booking detail:', err);
        const status = err.response?.status;
        const detail = err.response?.data?.detail;

        if (status === 403) {
          setError({
            type: 'forbidden',
            title: 'Access Restricted',
            message: 'You do not own this flight booking. Access to other traveler itineraries is strictly forbidden.',
          });
        } else if (status === 404) {
          setError({
            type: 'not_found',
            title: 'Booking Not Found',
            message: `Booking #${id} could not be located in our records.`,
          });
        } else {
          setError({
            type: 'general',
            title: 'Error Loading Booking',
            message: detail || 'Unable to retrieve booking details at this time.',
          });
        }
      } finally {
        setLoading(false);
      }
    };

    if (id) fetchDetail();
  }, [id]);

  const handleCopy = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-24 flex flex-col items-center justify-center space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
        <p className="text-xs text-slate-400 font-semibold">Retrieving official booking record #{id}...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center space-y-4">
        <div className="w-16 h-16 bg-rose-100 text-rose-600 rounded-3xl flex items-center justify-center mx-auto shadow-inner">
          {error.type === 'forbidden' ? <ShieldAlert className="w-8 h-8" /> : <AlertCircle className="w-8 h-8" />}
        </div>
        <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">{error.title}</h2>
        <p className="text-xs sm:text-sm text-slate-500 leading-relaxed max-w-sm mx-auto font-medium">{error.message}</p>
        <div className="pt-3">
          <Link
            to="/bookings"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-brand-600 text-white font-bold text-xs shadow-md shadow-brand-500/20 hover:bg-brand-700 transition-all active:scale-95"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to My Bookings</span>
          </Link>
        </div>
      </div>
    );
  }

  if (!booking) return null;

  const isMock = booking.is_simulation || booking.data_source === 'mock_simulation';
  const isDuffel = booking.data_source === 'duffel_sandbox';
  const pnr = booking.booking_reference || 'PENDING';
  const providerId = booking.provider_booking_id || 'N/A';

  const offer = booking.flight_offer || {};
  const airlineName = offer.airline_name || booking.airline_name || 'Airline';
  const airlineCode = offer.airline_code || booking.airline_code || 'FL';
  const flightNumber = offer.flight_number || booking.flight_number || '';
  const originIata = offer.origin_iata || booking.origin_iata || '---';
  const destinationIata = offer.destination_iata || booking.destination_iata || '---';
  const departureTime = offer.departure_time || booking.departure_time || booking.departure_date;
  const arrivalTime = offer.arrival_time || booking.arrival_time || booking.arrival_date;
  const stops = offer.stops !== undefined ? offer.stops : booking.stops;
  const cabinClass = offer.cabin_class || booking.cabin_class || 'economy';
  const baggage = offer.baggage_included || booking.baggage_included || 'Baggage included';

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-6">
      {/* Top Bar */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate('/bookings')}
          className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-500 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Booking History</span>
        </button>

        <span className="text-xs text-slate-400 font-mono font-medium">
          System Record ID #{booking.id}
        </span>
      </div>

      {/* Main Booking Dossier Card */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm overflow-hidden">
        {/* Banner Header */}
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs uppercase font-extrabold text-brand-300 tracking-wider block">
              Official Booking Dossier
            </span>
            <h1 className="text-xl sm:text-3xl font-black tracking-tight text-white mt-1">
              Itinerary Reference: {pnr}
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Provider Order ID: {providerId}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase">
              {booking.status || 'CONFIRMED'}
            </span>
            {isMock && (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30">
                <FlaskConical className="w-3.5 h-3.5" />
                SIMULATION
              </span>
            )}
            {isDuffel && (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-blue-400/20 text-blue-300 border border-blue-400/30">
                <ShieldCheck className="w-3.5 h-3.5" />
                DUFFEL SANDBOX
              </span>
            )}
          </div>
        </div>

        <div className="p-6 sm:p-8 space-y-6">
          {/* PNR Quick Copy Bar */}
          <div className="p-6 rounded-3xl bg-slate-50 border border-slate-200/90 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                Airline Booking Reference (PNR)
              </span>
              <span className="text-2xl sm:text-3xl font-mono font-black text-slate-900 tracking-wider">
                {pnr}
              </span>
            </div>

            <button
              type="button"
              onClick={() => handleCopy(pnr)}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-white border border-slate-300 text-xs font-bold text-slate-700 hover:bg-slate-100 shadow-xs transition-all active:scale-95"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-emerald-600" />
                  <span className="text-emerald-700 font-bold">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 text-slate-500" />
                  <span>Copy PNR</span>
                </>
              )}
            </button>
          </div>

          {/* Flight Details */}
          <div className="p-6 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3.5 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white font-black text-xs flex items-center justify-center shadow-xs">
                  {airlineCode}
                </div>
                <div>
                  <h4 className="font-extrabold text-slate-900 text-sm">{airlineName}</h4>
                  <span className="text-xs font-mono font-semibold text-slate-400">Flight {flightNumber || 'Scheduled'}</span>
                </div>
              </div>

              <div className="text-right">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Travel Date</span>
                <span className="text-xs font-black text-slate-800">{formatDate(departureTime)}</span>
              </div>
            </div>

            <div className="grid grid-cols-3 items-center text-center sm:text-left py-2">
              <div>
                <div className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">{formatTime(departureTime)}</div>
                <div className="text-sm font-bold text-slate-700">{originIata}</div>
              </div>

              <div className="flex flex-col items-center">
                <Plane className="w-5 h-5 text-brand-600 -rotate-45 mb-1" />
                <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                  {formatStops(stops)}
                </span>
                <span className="text-[11px] text-slate-400 capitalize mt-1 font-semibold">
                  {cabinClass}
                </span>
              </div>

              <div className="text-right">
                <div className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">{formatTime(arrivalTime)}</div>
                <div className="text-sm font-bold text-slate-700">{destinationIata}</div>
              </div>
            </div>
          </div>

          {/* Passenger Manifest */}
          <div className="p-6 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-4">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 pb-2.5 border-b border-slate-100">
              <Users className="w-4 h-4 text-brand-600" />
              <span>{isMock ? 'Simulated Travelers' : 'Traveler Manifest'} ({booking.passengers?.length || 0})</span>
            </h4>

            <div className="space-y-3">
              {booking.passengers?.map((p, idx) => (
                <div key={idx} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div>
                    <p className="font-extrabold text-slate-900 text-sm">
                      {p.first_name} {p.last_name}
                    </p>
                    <p className="text-slate-500 font-medium">
                      <span className="capitalize">{p.gender || 'Traveler'}</span>
                      {p.date_of_birth && (
                        <span className="ml-1 text-slate-400 font-normal">
                          • {maskDobYear(p.date_of_birth)}
                        </span>
                      )}
                    </p>
                  </div>

                  {p.passport_number && (
                    <div className="font-mono font-bold text-slate-700 bg-slate-100 px-3 py-1 rounded-xl border border-slate-200">
                      Passport: {maskPassport(p.passport_number)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Contact & Payment Information */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-5 rounded-3xl bg-slate-50 border border-slate-200/90 text-xs space-y-2">
              <span className="font-bold text-slate-700 uppercase tracking-wider block flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-brand-600" />
                <span>Dispatch Contact</span>
              </span>
              <p className="font-mono font-bold text-slate-900">{maskEmail(booking.contact_email)}</p>
              {booking.contact_phone && (
                <p className="font-mono font-bold text-slate-700">{maskPhone(booking.contact_phone)}</p>
              )}
            </div>

            <div className="p-5 rounded-3xl bg-slate-50 border border-slate-200/90 text-xs space-y-2">
              <span className="font-bold text-slate-700 uppercase tracking-wider block">
                Total Settlement
              </span>
              <div className="text-2xl font-black text-brand-600">
                {formatCurrency(booking.total_amount, booking.currency)}
              </div>
              <span className="text-[11px] text-slate-500 block font-medium">
                {isMock
                  ? 'Settlement Status: Simulated Order (No Real Payment Processed)'
                  : isDuffel
                  ? 'Settlement Status: Authorized via Duffel Test Sandbox'
                  : 'Settlement Status: Settled'}
              </span>
            </div>
          </div>

          {/* Transparency Disclaimer */}
          <div className="p-4 rounded-2xl bg-slate-100/90 text-xs text-slate-600 space-y-1 font-medium">
            <span className="font-bold text-slate-800 block">System Verification Notice</span>
            <p className="leading-relaxed">
              {isMock
                ? 'This booking was generated via authentic offline simulation for academic project demonstration. No real airline tickets, credit cards, or financial balances were charged.'
                : 'This booking was placed in Duffel API sandbox test mode with simulated settlement.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
