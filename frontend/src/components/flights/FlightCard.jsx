import React from 'react';
import {
  Plane,
  Clock,
  Luggage,
  ShieldAlert,
  ShieldCheck,
  FlaskConical,
  ArrowRight,
  Sparkles
} from 'lucide-react';

export default function FlightCard({ offer, onSelect }) {
  // Format ISO timestamps to readable 12-hour time
  const formatTime = (isoString) => {
    try {
      const dt = new Date(isoString);
      return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return isoString;
    }
  };

  const formatDate = (isoString) => {
    try {
      const dt = new Date(isoString);
      return dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  const formatDuration = (mins) => {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  // Condition 2: Explicit Data Source Badging
  const renderDataSourceBadge = () => {
    if (offer.is_simulation || offer.data_source === 'mock_simulation') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-300/80 shadow-2xs">
          <FlaskConical className="w-3.5 h-3.5 text-amber-600" />
          SIMULATION / MOCK OFFER
        </span>
      );
    }
    if (offer.data_source === 'duffel_sandbox') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-300/80 shadow-2xs">
          <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
          DUFFEL TEST SANDBOX
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300/80 shadow-2xs">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
        VERIFIED LIVE OFFER
      </span>
    );
  };

  return (
    <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm hover:shadow-xl hover:border-brand-300 hover:-translate-y-0.5 transition-all duration-300 p-6 flex flex-col justify-between gap-5 relative overflow-hidden group">
      {/* Top Banner: Airline & Data Source Badge */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-600 via-brand-500 to-indigo-600 flex items-center justify-center font-black text-xs text-white shadow-sm shadow-brand-500/20 tracking-wider">
            {offer.airline_code}
          </div>
          <div>
            <h4 className="font-extrabold text-slate-900 text-sm leading-tight">{offer.airline_name}</h4>
            <span className="text-xs text-slate-400 font-mono font-medium">Flight {offer.flight_number}</span>
          </div>
        </div>

        <div>{renderDataSourceBadge()}</div>
      </div>

      {/* Middle: Itinerary Timings & Stops Graphic */}
      <div className="grid grid-cols-1 sm:grid-cols-3 items-center gap-4 py-1">
        {/* Departure */}
        <div className="text-left">
          <div className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            {formatTime(offer.departure_time)}
          </div>
          <div className="text-sm font-bold text-slate-700">{offer.origin_iata}</div>
          <div className="text-xs text-slate-400 font-medium">{formatDate(offer.departure_time)}</div>
        </div>

        {/* Flight Path Graphic */}
        <div className="flex flex-col items-center justify-center px-2">
          <div className="flex items-center gap-1 text-xs text-slate-500 font-semibold mb-1">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>{formatDuration(offer.duration_minutes)}</span>
          </div>

          <div className="w-full flex items-center relative py-1">
            <div className="h-0.5 w-full bg-slate-200" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-7 h-7 rounded-full bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-600 shadow-2xs group-hover:scale-110 transition-transform">
                <Plane className="w-3.5 h-3.5 rotate-45" />
              </div>
            </div>
          </div>

          <div className="mt-1.5">
            {offer.stops === 0 ? (
              <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                Non-stop
              </span>
            ) : (
              <span className="text-[11px] font-bold text-amber-800 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200 truncate max-w-[140px] block text-center" title={offer.stop_details}>
                {offer.stop_details || `${offer.stops} stop`}
              </span>
            )}
          </div>
        </div>

        {/* Arrival */}
        <div className="text-left sm:text-right">
          <div className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            {formatTime(offer.arrival_time)}
          </div>
          <div className="text-sm font-bold text-slate-700">{offer.destination_iata}</div>
          <div className="text-xs text-slate-400 font-medium">{formatDate(offer.arrival_time)}</div>
        </div>
      </div>

      {/* Bottom Bar: Baggage, Total Price & Select Action */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-100">
        <div className="flex items-center gap-3 text-xs text-slate-500 font-medium">
          <span className="inline-flex items-center gap-1.5">
            <Luggage className="w-4 h-4 text-slate-400" />
            <span>{offer.baggage_included || 'Standard baggage'}</span>
          </span>
          <span className="text-slate-300">•</span>
          <span className="capitalize text-slate-700 font-semibold bg-slate-100 px-2.5 py-0.5 rounded-md">
            {offer.cabin_class?.replace('_', ' ') || 'Economy'}
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className="text-[11px] text-slate-400 block font-semibold uppercase tracking-wider">Total Price</span>
            <span className="text-xl sm:text-2xl font-black text-brand-600">
              {offer.currency === 'INR' ? '₹' : '$'}
              {offer.total_amount.toLocaleString()}
            </span>
          </div>

          <button
            type="button"
            onClick={() => onSelect && onSelect(offer)}
            className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 shadow-md shadow-brand-500/20 active:scale-95 transition-all shrink-0"
          >
            <span>Select Offer</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
