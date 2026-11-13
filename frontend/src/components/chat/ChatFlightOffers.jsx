import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Clock,
  Luggage,
  ShieldCheck,
  FlaskConical,
  ArrowRight,
  Plane
} from 'lucide-react';

const AIRPORT_TZ = {
  BLR: 'Asia/Kolkata', DEL: 'Asia/Kolkata', BOM: 'Asia/Kolkata', MAA: 'Asia/Kolkata',
  CCU: 'Asia/Kolkata', HYD: 'Asia/Kolkata', COK: 'Asia/Kolkata', GOI: 'Asia/Kolkata',
  GOX: 'Asia/Kolkata', PNQ: 'Asia/Kolkata', AMD: 'Asia/Kolkata', JAI: 'Asia/Kolkata',
  TRV: 'Asia/Kolkata', IXC: 'Asia/Kolkata', GAU: 'Asia/Kolkata', LKO: 'Asia/Kolkata',
  LHR: 'Europe/London', LGW: 'Europe/London', JFK: 'America/New_York',
  EWR: 'America/New_York', SFO: 'America/Los_Angeles', DXB: 'Asia/Dubai',
  SIN: 'Asia/Singapore', DOH: 'Asia/Qatar', CDG: 'Europe/Paris', FRA: 'Europe/Berlin', AMS: 'Europe/Amsterdam'
};

export default function ChatFlightOffers({ offers, isSimulation, dataSource }) {
  const navigate = useNavigate();
  if (!offers || offers.length === 0) return null;

  const handleBookFlight = (offer) => {
    sessionStorage.setItem('travelmate_selected_offer', JSON.stringify(offer));
    navigate('/booking/passengers', { state: { offer } });
  };

  const formatTime = (isoString, iataCode) => {
    try {
      const dt = new Date(isoString);
      const tz = (iataCode && AIRPORT_TZ[iataCode.toUpperCase()]) || 'Asia/Kolkata';
      return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true, timeZone: tz });
    } catch {
      return isoString;
    }
  };

  const formatDate = (isoString, iataCode) => {
    try {
      const dt = new Date(isoString);
      const tz = (iataCode && AIRPORT_TZ[iataCode.toUpperCase()]) || 'Asia/Kolkata';
      return dt.toLocaleDateString([], { month: 'short', day: 'numeric', timeZone: tz });
    } catch {
      return '';
    }
  };

  const formatDuration = (mins) => {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  // Condition 2: Transparent provider badging
  const renderBadge = (offer) => {
    const isMock = offer.data_source === 'mock_simulation' || offer.is_simulation || isSimulation || dataSource === 'mock_simulation';
    const isDuffel = offer.data_source === 'duffel_sandbox' || dataSource === 'duffel_sandbox';

    if (isMock) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300">
          <FlaskConical className="w-3 h-3 text-amber-600" />
          SIMULATION
        </span>
      );
    }
    if (isDuffel) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-300">
          <ShieldCheck className="w-3 h-3 text-blue-600" />
          DUFFEL TEST
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300">
        <ShieldCheck className="w-3 h-3 text-emerald-600" />
        LIVE VERIFIED
      </span>
    );
  };

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center justify-between text-[11px] font-bold text-slate-500 uppercase tracking-wider px-1">
        <span>Available Options ({offers.length})</span>
        <span className="text-brand-600 font-semibold">Live Inventory</span>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {offers.map((offer, idx) => (
          <div
            key={offer.id || offer.provider_offer_id || idx}
            className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-sm hover:border-brand-400 hover:shadow-md transition-all flex flex-col gap-3 group"
          >
            {/* Top: Airline, Flight Number & Provider Badge */}
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white font-black text-xs flex items-center justify-center shadow-xs">
                  {offer.airline_code || 'FL'}
                </div>
                <div>
                  <span className="font-extrabold text-slate-900 text-sm">{offer.airline_name}</span>
                  <span className="text-xs text-slate-400 font-mono font-medium ml-2">{offer.flight_number}</span>
                </div>
              </div>
              <div>{renderBadge(offer)}</div>
            </div>

            {/* Route & Times */}
            <div className="grid grid-cols-3 items-center gap-2 text-center sm:text-left py-1">
              <div>
                <div className="text-xl font-black text-slate-900 tracking-tight">{formatTime(offer.departure_time, offer.origin_iata)}</div>
                <div className="text-xs font-bold text-slate-700">{offer.origin_iata}</div>
                <div className="text-[11px] text-slate-400 font-medium">{formatDate(offer.departure_time, offer.origin_iata)}</div>
              </div>

              <div className="flex flex-col items-center">
                <div className="flex items-center gap-1 text-[11px] text-slate-500 font-semibold">
                  <Clock className="w-3 h-3 text-slate-400" />
                  {formatDuration(offer.duration_minutes)}
                </div>
                <div className="w-full flex items-center justify-center py-1">
                  <div className="h-0.5 flex-1 bg-slate-200" />
                  <Plane className="w-3.5 h-3.5 text-brand-500 mx-1.5 -rotate-45" />
                  <div className="h-0.5 flex-1 bg-slate-200" />
                </div>
                <div className="text-[10px] font-bold">
                  {offer.stops === 0 ? (
                    <span className="text-emerald-600 bg-emerald-50 px-2 py-0.2 rounded-full border border-emerald-200">Non-stop</span>
                  ) : (
                    <span className="text-amber-700 bg-amber-50 px-2 py-0.2 rounded-full border border-amber-200">{offer.stops} stop</span>
                  )}
                </div>
              </div>

              <div className="text-right">
                <div className="text-xl font-black text-slate-900 tracking-tight">{formatTime(offer.arrival_time, offer.destination_iata)}</div>
                <div className="text-xs font-bold text-slate-700">{offer.destination_iata}</div>
                <div className="text-[11px] text-slate-400 font-medium">{formatDate(offer.arrival_time, offer.destination_iata)}</div>
              </div>
            </div>

            {/* Bottom: Cabin, Baggage & Price */}
            <div className="pt-2.5 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2 text-slate-500 font-medium">
                <span className="capitalize px-2 py-0.5 bg-slate-100 rounded-md text-slate-700 font-semibold text-[11px]">
                  {(offer.cabin_class || 'economy').replace('_', ' ')}
                </span>
                {offer.baggage_included && (
                  <span className="inline-flex items-center gap-1 text-slate-600">
                    <Luggage className="w-3.5 h-3.5 text-slate-400" />
                    Baggage Included
                  </span>
                )}
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right">
                  <span className="text-[11px] text-slate-400 mr-1 font-medium">{offer.currency || 'INR'}</span>
                  <span className="text-base sm:text-lg font-black text-brand-600">
                    {Number(offer.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => handleBookFlight(offer)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 shadow-sm shadow-brand-500/20 transition-all active:scale-95 shrink-0"
                >
                  <span>Book Flight</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
