import React from 'react';
import { Link } from 'react-router-dom';
import {
  User,
  Plane,
  Sparkles,
  MapPin,
  Calendar,
  Users,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Volume2,
  Lock,
  ArrowRight,
  Ticket
} from 'lucide-react';
import ChatFlightOffers from './ChatFlightOffers';

export default function ChatMessage({
  message,
  onSpeakMessage,
  isCurrentSpeaking = false,
  onActionClick
}) {
  const isUser = message.role === 'user';

  // Format assistant text with clean paragraph and bold formatting
  const renderFormattedContent = (content) => {
    if (!content) return null;

    return content.split('\n').map((line, idx) => {
      if (!line.trim()) {
        return <div key={idx} className="h-2" />;
      }

      // Format simple markdown bolding (**text**)
      const parts = line.split(/(\*\*.*?\*\*)/g);
      const formattedLine = parts.map((part, pIdx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={pIdx} className="font-bold text-slate-900">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith('*(') && part.endsWith(')*')) {
          return (
            <em key={pIdx} className="text-amber-800 font-semibold text-xs not-italic bg-amber-50 px-1.5 py-0.2 rounded border border-amber-200">
              {part.slice(1, -1)}
            </em>
          );
        }
        return part;
      });

      // Highlight bullet points
      if (line.trim().startsWith('•') || line.trim().startsWith('-') || line.trim().startsWith('*')) {
        return (
          <div key={idx} className="flex items-start gap-2 pl-2 my-1 text-xs sm:text-sm text-slate-700">
            <span className="text-brand-500 font-black shrink-0 mt-0.5">•</span>
            <span>{formattedLine}</span>
          </div>
        );
      }

      return (
        <p key={idx} className="text-xs sm:text-sm leading-relaxed text-slate-700 font-normal">
          {formattedLine}
        </p>
      );
    });
  };

  // Render active flight criteria pills if available
  const renderSlotBadges = () => {
    if (!message.slots) return null;
    const { origin, destination, departure_date, passengers, cabin_class, preferred_time } = message.slots;
    if (!origin && !destination && !departure_date && !preferred_time) return null;

    return (
      <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-slate-100">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1">
          Captured Criteria:
        </span>
        {origin && (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-800 border border-slate-200/60">
            <MapPin className="w-3 h-3 text-brand-600" />
            From: <strong>{origin}</strong>
          </span>
        )}
        {destination && (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-800 border border-slate-200/60">
            <MapPin className="w-3 h-3 text-brand-600" />
            To: <strong>{destination}</strong>
          </span>
        )}
        {departure_date && (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-800 border border-slate-200/60">
            <Calendar className="w-3 h-3 text-slate-500" />
            Depart: <strong>{departure_date}</strong>
          </span>
        )}
        {preferred_time && (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            {preferred_time.toLowerCase() === 'morning' ? 'Morning (< 12 PM)' : preferred_time.charAt(0).toUpperCase() + preferred_time.slice(1)}
          </span>
        )}
        {passengers > 1 && (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-800 border border-slate-200/60">
            <Users className="w-3 h-3 text-slate-500" />
            {passengers} travelers
          </span>
        )}
        {cabin_class && cabin_class !== 'economy' && (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            {cabin_class}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className={`flex gap-3 sm:gap-4 my-4.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {/* Assistant Avatar */}
      {!isUser && (
        <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-brand-600 via-brand-500 to-indigo-600 text-white flex items-center justify-center shrink-0 shadow-md shadow-brand-500/20 mt-0.5">
          <Plane className="w-4.5 h-4.5 -rotate-45" />
        </div>
      )}

      {/* Message Bubble */}
      <div
        className={`max-w-[88%] sm:max-w-[82%] rounded-3xl px-5 py-4 shadow-sm transition-all ${
          isUser
            ? 'bg-gradient-to-r from-brand-600 to-indigo-600 text-white rounded-br-sm shadow-md shadow-brand-500/15'
            : 'bg-white text-slate-800 border border-slate-200/90 rounded-bl-sm shadow-2xs'
        }`}
      >
        {/* Role Header (for Assistant) */}
        {!isUser && (
          <div className="flex items-center justify-between gap-2 mb-2.5 pb-2 border-b border-slate-100 text-xs">
            <div className="flex items-center gap-2 font-black text-slate-900">
              <Sparkles className="w-3.5 h-3.5 text-brand-600" />
              <span>TRAVELMATE AI</span>
              {onSpeakMessage && message.content && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSpeakMessage(message.content, message.id);
                  }}
                  className={`ml-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold transition-all flex items-center gap-1.5 ${
                    isCurrentSpeaking
                      ? 'text-brand-700 bg-brand-100 ring-1 ring-brand-400'
                      : 'text-slate-500 hover:text-brand-600 bg-slate-100 hover:bg-brand-50'
                  }`}
                  title={isCurrentSpeaking ? 'Stop reading response' : 'Listen to this response'}
                  aria-label={isCurrentSpeaking ? 'Stop reading response' : 'Listen to response'}
                >
                  <Volume2 className={`w-3 h-3 ${isCurrentSpeaking ? 'animate-pulse text-brand-600' : ''}`} />
                  <span>{isCurrentSpeaking ? 'Speaking' : 'Read'}</span>
                </button>
              )}
            </div>

            {/* Search & Booking Status Pills */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {message.search_status === 'search_executed' && (
                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  Flights Found
                </span>
              )}
              {message.search_status === 'clarification_needed' && (
                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-800 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                  <AlertCircle className="w-3 h-3 text-amber-600" />
                  Criteria Needed
                </span>
              )}
              {message.booking_workflow_state === 'booking_confirmation_required' && (
                <span className="inline-flex items-center gap-1 text-[10px] font-black text-purple-700 bg-purple-50 px-2.5 py-0.5 rounded-full border border-purple-200 uppercase">
                  <Lock className="w-3 h-3 text-purple-600" />
                  Review Ready
                </span>
              )}
              {message.booking_workflow_state === 'price_change_requires_approval' && (
                <span className="inline-flex items-center gap-1 text-[10px] font-black text-amber-800 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-300 uppercase">
                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                  Price Changed
                </span>
              )}
              {message.booking_workflow_state === 'booking_confirmed' && (
                <span className="inline-flex items-center gap-1 text-[10px] font-black text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full border border-emerald-300 uppercase">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  Confirmed
                </span>
              )}
              {message.booking_workflow_state === 'booking_uncertain' && (
                <span className="inline-flex items-center gap-1 text-[10px] font-black text-amber-800 bg-amber-100 px-2.5 py-0.5 rounded-full border border-amber-300 uppercase">
                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                  Uncertain Status
                </span>
              )}
            </div>
          </div>
        )}

        {/* Content */}
        {isUser ? (
          <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-medium">{message.content}</p>
        ) : (
          <div className="space-y-1.5">{renderFormattedContent(message.content)}</div>
        )}

        {/* Captured Criteria Slots */}
        {!isUser && renderSlotBadges()}

        {/* Embedded Flight Offer Cards */}
        {!isUser && message.flight_offers && message.flight_offers.length > 0 && (
          <ChatFlightOffers
            offers={message.flight_offers}
            isSimulation={message.search_metadata?.is_simulation}
            dataSource={message.search_metadata?.data_source}
          />
        )}

        {/* Booking Workflow Interactive Action Bar */}
        {!isUser && message.booking_workflow_state === 'booking_confirmation_required' && (
          <div className="mt-3.5 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => onActionClick && onActionClick('Confirm booking')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-md shadow-emerald-600/20 transition-all active:scale-95"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Authorize & Confirm Booking</span>
            </button>
            <button
              type="button"
              onClick={() => onActionClick && onActionClick('Cancel')}
              className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
            >
              Cancel
            </button>
          </div>
        )}

        {!isUser && message.booking_workflow_state === 'price_change_requires_approval' && (
          <div className="mt-3.5 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => onActionClick && onActionClick('Accept new price and confirm')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-brand-500/20 transition-all active:scale-95"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Accept New Price & Confirm</span>
            </button>
            <button
              type="button"
              onClick={() => onActionClick && onActionClick('Cancel')}
              className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
            >
              Cancel
            </button>
          </div>
        )}

        {!isUser && message.booking_workflow_state === 'booking_confirmed' && (
          <div className="mt-3.5 pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
            <span className="text-xs text-emerald-700 font-bold flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Reservation Active</span>
            </span>
            <Link
              to="/bookings"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-700 hover:text-brand-900 bg-brand-50 px-3.5 py-1.5 rounded-xl border border-brand-200/80 transition-colors shadow-2xs"
            >
              <Ticket className="w-3.5 h-3.5" />
              <span>View in My Bookings</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        )}

        {!isUser && message.booking_workflow_state === 'authentication_required' && (
          <div className="mt-3.5 pt-3 border-t border-slate-100 flex items-center gap-2.5">
            <Link
              to="/login"
              className="inline-flex items-center gap-1 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold transition-all shadow-xs"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="inline-flex items-center gap-1 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
            >
              Register
            </Link>
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="w-9 h-9 rounded-2xl bg-slate-800 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5 font-bold text-xs">
          <User className="w-4.5 h-4.5" />
        </div>
      )}
    </div>
  );
}
