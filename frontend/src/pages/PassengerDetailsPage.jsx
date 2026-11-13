import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import {
  Plane,
  User,
  Users,
  Calendar,
  Mail,
  Phone,
  Shield,
  ShieldCheck,
  FlaskConical,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Luggage,
  Loader2,
  Lock,
  Compass
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { bookingService } from '../services/bookingService';

export default function PassengerDetailsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated } = useAuth();

  // Retrieve selected flight offer from route state or sessionStorage
  const [offer, setOffer] = useState(() => {
    if (location.state?.offer) {
      sessionStorage.setItem('travelmate_selected_offer', JSON.stringify(location.state.offer));
      return location.state.offer;
    }
    const saved = sessionStorage.getItem('travelmate_selected_offer');
    return saved ? JSON.parse(saved) : null;
  });

  // Revalidation state
  const [revalidating, setRevalidating] = useState(false);
  const [revalError, setRevalError] = useState(null);
  const [priceNotice, setPriceNotice] = useState(null);

  // Saved passenger profiles
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [loadingProfiles, setLoadingProfiles] = useState(false);
  const [selectedProfileId, setSelectedProfileId] = useState('');

  // Passenger form state
  const [passenger, setPassenger] = useState({
    first_name: '',
    last_name: '',
    date_of_birth: '',
    gender: 'male',
    passport_number: '',
  });

  const [contact, setContact] = useState({
    email: user?.email || '',
    phone: '',
  });

  const [saveProfileForFuture, setSaveProfileForFuture] = useState(false);
  const [errors, setErrors] = useState({});

  // 1. Revalidate offer availability on page load
  useEffect(() => {
    if (!offer?.id) return;

    const runRevalidation = async () => {
      setRevalidating(true);
      setRevalError(null);
      setPriceNotice(null);
      try {
        const reval = await bookingService.revalidateOffer(offer.id);
        if (!reval.is_valid) {
          setRevalError(reval.message || 'This flight offer is no longer available from the airline.');
        } else if (reval.price_changed) {
          setPriceNotice({
            oldPrice: offer.total_amount,
            newPrice: reval.current_amount,
            currency: reval.currency,
          });
          setOffer((prev) => ({
            ...prev,
            total_amount: reval.current_amount,
            currency: reval.currency,
          }));
        }
      } catch (err) {
        console.warn('Offer pre-validation warning:', err);
      } finally {
        setRevalidating(false);
      }
    };

    runRevalidation();
  }, [offer?.id]);

  // 2. Fetch saved passenger profiles if authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const loadProfiles = async () => {
        try {
          setLoadingProfiles(true);
          const profiles = await bookingService.getSavedPassengers();
          setSavedProfiles(profiles || []);
          if (profiles && profiles.length > 0) {
            const first = profiles[0];
            setSelectedProfileId(first.id);
            setPassenger({
              first_name: first.first_name || '',
              last_name: first.last_name || '',
              date_of_birth: first.date_of_birth || '',
              gender: first.gender || 'male',
              passport_number: first.passport_number || '',
            });
          }
        } catch (err) {
          console.warn('Failed to load saved passenger profiles:', err);
        } finally {
          setLoadingProfiles(false);
        }
      };

      loadProfiles();
    }
  }, [isAuthenticated]);

  // Update contact email when auth changes
  useEffect(() => {
    if (user?.email && !contact.email) {
      setContact((prev) => ({ ...prev, email: user.email }));
    }
  }, [user]);

  // Handle saved profile selection change
  const handleProfileSelect = (profileId) => {
    setSelectedProfileId(profileId);
    if (!profileId) {
      setPassenger({
        first_name: '',
        last_name: '',
        date_of_birth: '',
        gender: 'male',
        passport_number: '',
      });
      return;
    }
    const prof = savedProfiles.find((p) => String(p.id) === String(profileId));
    if (prof) {
      setPassenger({
        first_name: prof.first_name || '',
        last_name: prof.last_name || '',
        date_of_birth: prof.date_of_birth || '',
        gender: prof.gender || 'male',
        passport_number: prof.passport_number || '',
      });
    }
  };

  // Form Validation
  const validateForm = () => {
    const errs = {};
    if (!passenger.first_name.trim()) errs.first_name = 'First name is required.';
    if (!passenger.last_name.trim()) errs.last_name = 'Last name is required.';

    if (!passenger.date_of_birth) {
      errs.date_of_birth = 'Date of birth is required.';
    } else {
      const dobDate = new Date(passenger.date_of_birth);
      const today = new Date();
      if (isNaN(dobDate.getTime()) || dobDate >= today) {
        errs.date_of_birth = 'Date of birth must be a valid date in the past.';
      }
    }

    if (!contact.email.trim()) {
      errs.email = 'Contact email is required for e-ticket delivery.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email.trim())) {
      errs.email = 'Please provide a valid email address.';
    }

    const cleanPhone = contact.phone.replace(/\D/g, '');
    if (!contact.phone.trim()) {
      errs.phone = 'Contact phone number is required.';
    } else if (cleanPhone.length < 7) {
      errs.phone = 'Please provide a valid phone number with country/area code.';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleContinue = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    if (isAuthenticated && saveProfileForFuture && !selectedProfileId) {
      try {
        await bookingService.savePassengerProfile({
          first_name: passenger.first_name.trim(),
          last_name: passenger.last_name.trim(),
          date_of_birth: passenger.date_of_birth,
          gender: passenger.gender,
          passport_number: passenger.passport_number.trim() || null,
        });
      } catch (err) {
        console.warn('Could not auto-save passenger profile:', err);
      }
    }

    const bookingDraft = {
      offer,
      passengers: [
        {
          first_name: passenger.first_name.trim(),
          last_name: passenger.last_name.trim(),
          date_of_birth: passenger.date_of_birth,
          gender: passenger.gender,
          passport_number: passenger.passport_number.trim() || null,
        },
      ],
      contact: {
        email: contact.email.trim(),
        phone: contact.phone.trim(),
      },
    };

    sessionStorage.setItem('travelmate_booking_draft', JSON.stringify(bookingDraft));
    navigate('/booking/review', { state: bookingDraft });
  };

  if (!offer) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center space-y-4">
        <div className="w-16 h-16 bg-amber-50 text-amber-600 rounded-3xl flex items-center justify-center mx-auto shadow-inner border border-amber-200">
          <Plane className="w-8 h-8 -rotate-45" />
        </div>
        <h2 className="text-2xl font-black text-slate-800 tracking-tight">No Flight Selected</h2>
        <p className="text-slate-500 text-xs sm:text-sm max-w-md mx-auto leading-relaxed">
          Please select a flight offer from our flight search page or through the AI Assistant.
        </p>
        <div className="pt-2 flex justify-center gap-3">
          <Link
            to="/flights"
            className="px-6 py-3 rounded-2xl bg-gradient-to-r from-brand-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-brand-500/20 hover:from-brand-500 hover:to-indigo-500 transition-all active:scale-95"
          >
            Search Flights
          </Link>
          <Link
            to="/chat"
            className="px-6 py-3 rounded-2xl bg-slate-100 text-slate-700 font-bold text-xs hover:bg-slate-200 transition-colors"
          >
            Ask AI Assistant
          </Link>
        </div>
      </div>
    );
  }

  const isMock = offer.data_source === 'mock_simulation' || offer.is_simulation;
  const isDuffel = offer.data_source === 'duffel_sandbox';

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-6">
      {/* Back button and Step indicator */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-500 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Flight Selection</span>
        </button>

        <div className="flex items-center gap-2.5 text-xs font-bold text-slate-500 bg-white px-4 py-2 rounded-2xl border border-slate-200/80 shadow-2xs">
          <span className="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center text-xs font-black shadow-xs">
            1
          </span>
          <span className="text-brand-700 font-extrabold">Passenger Details</span>
          <span className="text-slate-300">➔</span>
          <span className="w-6 h-6 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center text-xs font-bold">
            2
          </span>
          <span className="text-slate-400 font-medium">Review & Confirm</span>
        </div>
      </div>

      {/* Selected Flight Card Summary Header */}
      <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center font-black text-xs text-white shadow-sm">
              {offer.airline_code || 'FL'}
            </div>
            <div>
              <h3 className="font-extrabold text-slate-900 text-sm">
                {offer.airline_name} • <span className="font-mono text-slate-400 font-semibold">{offer.flight_number}</span>
              </h3>
              <p className="text-xs text-slate-500 font-medium">
                {offer.origin_iata} ➔ {offer.destination_iata} • {new Date(offer.departure_time).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {isMock && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-300">
                <FlaskConical className="w-3.5 h-3.5 text-amber-600" />
                SIMULATION / MOCK
              </span>
            )}
            {isDuffel && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-300">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                DUFFEL TEST
              </span>
            )}
            <div className="text-right ml-2">
              <span className="text-[11px] text-slate-400 block font-semibold uppercase tracking-wider">Total Fare</span>
              <span className="text-xl font-black text-brand-600">
                {offer.currency === 'INR' ? '₹' : '$'}
                {Number(offer.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>

        {/* Live Revalidation Notice Banner */}
        {revalidating && (
          <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-600 font-medium animate-in fade-in">
            <Loader2 className="w-4 h-4 animate-spin text-brand-600 shrink-0" />
            <span>Verifying live seat inventory and fare with airline provider...</span>
          </div>
        )}

        {revalError && (
          <div className="flex items-start gap-2.5 px-4 py-3 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-800 animate-in fade-in">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Offer Unavailable</p>
              <p className="mt-0.5">{revalError}</p>
            </div>
          </div>
        )}

        {priceNotice && (
          <div className="flex items-start gap-2.5 px-4 py-3 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-900 animate-in fade-in">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Airline Fare Update</p>
              <p className="mt-0.5">
                The airline updated the live fare for this itinerary from {priceNotice.currency} {priceNotice.oldPrice.toLocaleString()} to {priceNotice.currency} {priceNotice.newPrice.toLocaleString()}. The review will reflect the current live fare.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Guest Authentication Advisory Callout */}
      {!isAuthenticated && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-3xl border border-blue-200/90 p-5 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-10 h-10 rounded-2xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 shadow-2xs">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">Guest Checkout Notice</h4>
              <p className="text-xs text-slate-600 mt-0.5 max-w-lg leading-relaxed">
                To track your booking status, view e-tickets, and autofill future trips, we recommend logging in. Your selected flight is preserved.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2.5 shrink-0">
            <Link
              to="/login?redirect=/booking/passengers"
              className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold shadow-md shadow-brand-500/20 transition-all active:scale-95"
            >
              Sign In
            </Link>
            <Link
              to="/register?redirect=/booking/passengers"
              className="px-4 py-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-bold transition-colors"
            >
              Register
            </Link>
          </div>
        </div>
      )}

      {/* Main Passenger Information Form */}
      <form onSubmit={handleContinue} className="bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-8 shadow-sm space-y-6">
        {/* Saved Profiles Quick Select */}
        {isAuthenticated && savedProfiles.length > 0 && (
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
            <label className="block text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-brand-600" />
              <span>Autofill from Saved Travelers</span>
            </label>
            <select
              value={selectedProfileId}
              onChange={(e) => handleProfileSelect(e.target.value)}
              className="w-full sm:w-auto px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs font-semibold bg-white text-slate-800 focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="">-- Enter New Traveler Details --</option>
              {savedProfiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.first_name} {p.last_name} ({p.gender || 'passenger'}, DOB: {p.date_of_birth || 'N/A'})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Section: Traveler Personal Details */}
        <div className="space-y-4">
          <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <User className="w-4 h-4 text-brand-600" />
            <span>Passenger 1 Details (Adult)</span>
          </h4>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                First Name / Given Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={passenger.first_name}
                onChange={(e) => setPassenger({ ...passenger, first_name: e.target.value })}
                placeholder="e.g. Rahul"
                className={`w-full px-4 py-3 rounded-2xl border text-sm text-slate-800 font-semibold focus:ring-2 focus:ring-brand-500/20 transition-all ${
                  errors.first_name ? 'border-rose-400 bg-rose-50/30' : 'border-slate-300'
                }`}
              />
              {errors.first_name && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.first_name}</p>}
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Last Name / Family Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={passenger.last_name}
                onChange={(e) => setPassenger({ ...passenger, last_name: e.target.value })}
                placeholder="e.g. Kumar"
                className={`w-full px-4 py-3 rounded-2xl border text-sm text-slate-800 font-semibold focus:ring-2 focus:ring-brand-500/20 transition-all ${
                  errors.last_name ? 'border-rose-400 bg-rose-50/30' : 'border-slate-300'
                }`}
              />
              {errors.last_name && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.last_name}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Date of Birth <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                required
                value={passenger.date_of_birth}
                onChange={(e) => setPassenger({ ...passenger, date_of_birth: e.target.value })}
                max={new Date().toISOString().split('T')[0]}
                className={`w-full px-4 py-3 rounded-2xl border text-sm text-slate-800 font-semibold focus:ring-2 focus:ring-brand-500/20 transition-all ${
                  errors.date_of_birth ? 'border-rose-400 bg-rose-50/30' : 'border-slate-300'
                }`}
              />
              {errors.date_of_birth && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.date_of_birth}</p>}
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Gender <span className="text-rose-500">*</span>
              </label>
              <select
                value={passenger.gender}
                onChange={(e) => setPassenger({ ...passenger, gender: e.target.value })}
                className="w-full px-4 py-3 rounded-2xl border border-slate-300 text-sm text-slate-800 font-semibold focus:ring-2 focus:ring-brand-500/20"
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other / Non-Binary</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Passport Number <span className="text-slate-400 font-normal">(Optional for domestic flights)</span>
            </label>
            <input
              type="text"
              value={passenger.passport_number}
              onChange={(e) => setPassenger({ ...passenger, passport_number: e.target.value.toUpperCase() })}
              placeholder="e.g. P12345678"
              maxLength={20}
              className="w-full sm:w-1/2 px-4 py-3 rounded-2xl border border-slate-300 text-sm text-slate-800 font-mono font-bold focus:ring-2 focus:ring-brand-500/20 uppercase"
            />
            <p className="text-[11px] text-slate-400 mt-1 font-medium">
              Passport numbers are encrypted and masked for strict privacy in all read views.
            </p>
          </div>
        </div>

        {/* Section: Contact & Delivery Information */}
        <div className="space-y-4 pt-4 border-t border-slate-100">
          <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <Mail className="w-4 h-4 text-brand-600" />
            <span>Contact & E-Ticket Delivery</span>
          </h4>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Email Address <span className="text-rose-500">*</span>
              </label>
              <input
                type="email"
                required
                value={contact.email}
                onChange={(e) => setContact({ ...contact, email: e.target.value })}
                placeholder="your.email@example.com"
                className={`w-full px-4 py-3 rounded-2xl border text-sm text-slate-800 font-semibold focus:ring-2 focus:ring-brand-500/20 transition-all ${
                  errors.email ? 'border-rose-400 bg-rose-50/30' : 'border-slate-300'
                }`}
              />
              {errors.email && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.email}</p>}
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Contact Phone <span className="text-rose-500">*</span>
              </label>
              <input
                type="tel"
                required
                value={contact.phone}
                onChange={(e) => setContact({ ...contact, phone: e.target.value })}
                placeholder="+919876543210"
                className={`w-full px-4 py-3 rounded-2xl border text-sm text-slate-800 font-semibold focus:ring-2 focus:ring-brand-500/20 transition-all ${
                  errors.phone ? 'border-rose-400 bg-rose-50/30' : 'border-slate-300'
                }`}
              />
              {errors.phone && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.phone}</p>}
            </div>
          </div>
        </div>

        {/* Security & Financial Protection Guarantee */}
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/90 flex items-start gap-3.5">
          <Lock className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
          <div className="text-xs text-slate-600 leading-relaxed font-medium">
            <span className="font-bold text-slate-900 block mb-0.5">Zero Financial Credential Storage</span>
            TRAVELMATE AI never requests, collects, or stores credit/debit card numbers or CVV codes. All test reservations are securely settled through Duffel Sandbox test balance or authentic mock provider adapters.
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-100">
          <button
            type="button"
            onClick={() => navigate('/flights')}
            className="w-full sm:w-auto px-5 py-3 rounded-2xl border border-slate-300 text-xs sm:text-sm font-bold text-slate-600 hover:bg-slate-50 transition-colors"
          >
            Cancel & Return
          </button>

          <button
            type="submit"
            disabled={revalidating || !!revalError}
            className={`w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-2xl text-xs sm:text-sm font-bold text-white shadow-md transition-all ${
              revalidating || !!revalError
                ? 'bg-slate-300 cursor-not-allowed shadow-none'
                : 'bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 shadow-brand-500/25 active:scale-95'
            }`}
          >
            <span>Proceed to Booking Review</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
