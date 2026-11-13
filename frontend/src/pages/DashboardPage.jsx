import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  User,
  Mail,
  Shield,
  Calendar,
  Users,
  Plane,
  Plus,
  Loader2,
  CheckCircle2,
  Sparkles,
  Ticket,
  ArrowRight,
  Clock,
  Compass,
  X
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import { bookingService, formatDate } from '../services/bookingService';

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [passengers, setPassengers] = useState([]);
  const [loadingPassengers, setLoadingPassengers] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newPassenger, setNewPassenger] = useState({
    first_name: '',
    last_name: '',
    date_of_birth: '',
    gender: 'male',
    passport_number: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [recentBookings, setRecentBookings] = useState([]);
  const [loadingBookings, setLoadingBookings] = useState(true);

  // Fetch saved passengers
  const fetchPassengers = async () => {
    try {
      setLoadingPassengers(true);
      const res = await api.get('/auth/passengers');
      setPassengers(res.data);
    } catch (err) {
      console.error('Failed to load passengers:', err);
    } finally {
      setLoadingPassengers(false);
    }
  };

  const fetchBookings = async () => {
    try {
      setLoadingBookings(true);
      const data = await bookingService.getBookingHistory();
      setRecentBookings(data ? data.slice(0, 3) : []);
    } catch (err) {
      console.warn('Failed to load recent bookings:', err);
    } finally {
      setLoadingBookings(false);
    }
  };

  useEffect(() => {
    fetchPassengers();
    fetchBookings();
  }, []);

  const handleAddPassenger = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setMessage('');

    try {
      await api.post('/auth/passengers', newPassenger);
      setMessage('Passenger profile saved successfully!');
      setShowAddModal(false);
      setNewPassenger({
        first_name: '',
        last_name: '',
        date_of_birth: '',
        gender: 'male',
        passport_number: ''
      });
      fetchPassengers();
    } catch (err) {
      alert('Failed to save passenger profile. Please check the fields.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Command Center Hero Banner */}
      <div className="relative overflow-hidden bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-9 text-white shadow-xl border border-slate-800">
        <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl pointer-events-none -z-0" />

        <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-brand-200 text-xs font-semibold backdrop-blur-md border border-white/10">
              <Sparkles className="w-3.5 h-3.5 text-brand-300" />
              <span>AI Command Center</span>
            </div>
            <h1 className="text-2xl sm:text-4xl font-black tracking-tight text-white">
              Welcome back, {user?.full_name}!
            </h1>
            <p className="text-slate-300 text-xs sm:text-sm max-w-xl leading-relaxed">
              Your autonomous travel portal is active. Manage your passenger manifest, review recent reservations, or consult the AI assistant.
            </p>
          </div>

          {/* User Dossier Quick Tag */}
          <div className="bg-white/10 backdrop-blur-xl rounded-2xl p-4 border border-white/15 text-xs space-y-2 shrink-0 sm:min-w-[240px]">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-400 to-indigo-400 text-slate-950 flex items-center justify-center font-black text-xs shadow-xs">
                {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
              </div>
              <div className="truncate">
                <span className="font-bold text-white block truncate">{user?.full_name}</span>
                <span className="text-[11px] text-slate-300 truncate block">{user?.email}</span>
              </div>
            </div>
            <div className="pt-2 border-t border-white/10 flex items-center justify-between text-[11px] text-slate-300">
              <span className="flex items-center gap-1 capitalize">
                <Shield className="w-3 h-3 text-brand-300" />
                Role: {user?.role || 'User'}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3 text-brand-300" />
                Member: {user?.created_at ? new Date(user.created_at).toLocaleDateString([], { month: 'short', year: 'numeric' }) : '2026'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {message && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs sm:text-sm flex items-center gap-2.5 animate-in fade-in">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span className="font-semibold">{message}</span>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left 2 Cols: Saved Passenger Manifest & Recent Bookings */}
        <div className="lg:col-span-2 space-y-8">
          {/* Saved Passenger Profiles Card */}
          <div className="bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-7 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-100">
              <div>
                <h2 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
                  <Users className="w-5 h-5 text-brand-600" />
                  Saved Passenger Profiles
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Pre-configured traveler details used for 1-click checkout (FR-035)
                </p>
              </div>

              <button
                onClick={() => setShowAddModal(true)}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-brand-600 hover:bg-brand-700 shadow-md shadow-brand-500/20 transition-all active:scale-95 shrink-0"
              >
                <Plus className="w-4 h-4" />
                <span>Add Passenger</span>
              </button>
            </div>

            {loadingPassengers ? (
              <div className="py-12 flex flex-col justify-center items-center text-slate-400 space-y-2">
                <Loader2 className="w-7 h-7 animate-spin text-brand-600" />
                <span className="text-xs">Loading passenger manifest...</span>
              </div>
            ) : passengers.length === 0 ? (
              <div className="text-center py-10 px-4 border-2 border-dashed border-slate-200 rounded-2xl">
                <Users className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <h3 className="text-sm font-bold text-slate-700">No passenger profiles yet</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                  Add traveler profiles to save time when booking flights with the assistant.
                </p>
                <button
                  onClick={() => setShowAddModal(true)}
                  className="mt-4 px-4 py-2 text-xs font-bold text-brand-600 bg-brand-50 hover:bg-brand-100 rounded-xl transition-colors"
                >
                  Create First Profile
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {passengers.map((p) => (
                  <div
                    key={p.id}
                    className="p-4 rounded-2xl border border-slate-200/90 bg-slate-50/50 hover:bg-white hover:border-brand-300 hover:shadow-md transition-all flex flex-col justify-between"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 font-bold text-xs flex items-center justify-center">
                          {p.first_name ? p.first_name.charAt(0).toUpperCase() : 'P'}
                        </div>
                        <div>
                          <span className="font-bold text-sm text-slate-900 block">
                            {p.first_name} {p.last_name}
                          </span>
                          <span className="text-[10px] text-slate-400 capitalize">
                            {p.gender || 'Traveler'}
                          </span>
                        </div>
                      </div>

                      <span className="px-2 py-0.5 text-[9px] uppercase font-bold bg-slate-200 text-slate-700 rounded-full">
                        Saved
                      </span>
                    </div>

                    <div className="mt-3 pt-2 border-t border-slate-200/60 text-xs text-slate-500 space-y-0.5">
                      {p.date_of_birth && (
                        <p className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>DOB: {p.date_of_birth}</span>
                        </p>
                      )}
                      {p.passport_number && (
                        <p className="font-mono text-slate-600 flex items-center gap-1.5">
                          <Shield className="w-3.5 h-3.5 text-slate-400" />
                          <span>Passport: {p.passport_number}</span>
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Flight Bookings Card */}
          <div className="bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-7 shadow-sm">
            <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
              <div>
                <h2 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
                  <Ticket className="w-5 h-5 text-brand-600" />
                  Recent Flight Bookings
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Your recent reservations, PNR references and provider statuses
                </p>
              </div>

              <Link
                to="/bookings"
                className="inline-flex items-center gap-1 text-xs font-bold text-brand-600 hover:text-brand-800 transition-colors"
              >
                <span>View All</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {loadingBookings ? (
              <div className="py-8 flex flex-col justify-center items-center text-slate-400 space-y-2">
                <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
                <span className="text-xs">Loading bookings...</span>
              </div>
            ) : recentBookings.length === 0 ? (
              <div className="p-8 rounded-2xl bg-slate-50/70 text-center text-xs text-slate-500 border border-slate-200/80 space-y-2">
                <p>No bookings placed yet.</p>
                <div className="flex justify-center gap-3 pt-1">
                  <Link to="/flights" className="text-brand-600 font-bold hover:underline">
                    Search flights
                  </Link>
                  <span>or</span>
                  <Link to="/chat" className="text-brand-600 font-bold hover:underline">
                    Talk to AI Assistant
                  </Link>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {recentBookings.map((b) => (
                  <div
                    key={b.id}
                    onClick={() => navigate(`/bookings/${b.id}`)}
                    className="p-4 rounded-2xl border border-slate-200 hover:border-brand-400 bg-white hover:bg-slate-50/60 cursor-pointer transition-all flex items-center justify-between gap-3 text-xs shadow-2xs group"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-black text-slate-900 bg-slate-100 px-2.5 py-0.5 rounded-lg border border-slate-200">
                          {b.booking_reference || 'PENDING'}
                        </span>
                        <span className="font-bold text-slate-800">
                          {b.airline_name} {b.flight_number ? `(${b.flight_number})` : ''}
                        </span>
                      </div>
                      <p className="text-slate-500 font-medium">
                        {b.origin_iata || '---'} ➔ {b.destination_iata || '---'} • {formatDate(b.departure_time || b.departure_date)}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="font-black text-slate-900 text-sm block">
                        {b.currency === 'INR' ? '₹' : '$'}
                        {Number(b.total_amount).toLocaleString()}
                      </span>
                      <span className="text-[10px] uppercase font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                        {b.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Col: AI Launch Tile & Phase Roadmap */}
        <div className="space-y-6">
          {/* AI Flight Assistant Launch Tile */}
          <div className="bg-gradient-to-br from-brand-600 via-indigo-600 to-indigo-700 rounded-3xl p-6 text-white shadow-lg shadow-brand-500/20 relative overflow-hidden">
            <div className="absolute -bottom-8 -right-8 w-32 h-32 bg-white/10 rounded-full blur-xl pointer-events-none" />
            <div className="relative z-10 space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-bold text-base text-white">AI Flight Copilot</h3>
                <p className="text-xs text-brand-100 mt-1 leading-relaxed">
                  Search, filter, and plan flights using voice or text. LangGraph orchestrates slot-filling and price validation autonomously.
                </p>
              </div>
              <Link
                to="/chat"
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-xs font-bold text-slate-900 bg-white hover:bg-slate-100 transition-all shadow-md active:scale-95"
              >
                <span>Launch Assistant</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>

          {/* Project Architecture Status */}
          <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-sm space-y-4">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2 pb-2 border-b border-slate-100">
              <Plane className="w-4 h-4 text-brand-600" />
              Capstone Milestones
            </h2>

            <div className="space-y-3 text-xs">
              <div className="flex items-start gap-3 p-3 rounded-2xl bg-emerald-50/70 text-emerald-900 border border-emerald-200/80">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Phase 1: Project & Auth</p>
                  <p className="text-[11px] text-emerald-700">FastAPI, JWT, Postgres/SQLite, React UI</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-2xl bg-emerald-50/70 text-emerald-900 border border-emerald-200/80">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Phase 2: Flight Search Adapter</p>
                  <p className="text-[11px] text-emerald-700">Duffel API live integration & mock engine</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-2xl bg-emerald-50/70 text-emerald-900 border border-emerald-200/80">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Phase 3: Conversational AI</p>
                  <p className="text-[11px] text-emerald-700">Google Gemini, LangGraph & Chat Workspace</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-2xl bg-emerald-50/70 text-emerald-900 border border-emerald-200/80">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Phase 4: Multimodal Voice & Booking</p>
                  <p className="text-[11px] text-emerald-700">Deterministic booking approval state machine</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Add Passenger Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 sm:p-7 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-600" />
                Add Passenger Profile
              </h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-500 mb-4">
              Enter details for one traveler. These will be auto-filled during checkout.
            </p>

            <form onSubmit={handleAddPassenger} className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">First Name *</label>
                  <input
                    type="text"
                    required
                    value={newPassenger.first_name}
                    onChange={(e) =>
                      setNewPassenger({ ...newPassenger, first_name: e.target.value })
                    }
                    className="w-full px-3 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                    placeholder="John"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Last Name *</label>
                  <input
                    type="text"
                    required
                    value={newPassenger.last_name}
                    onChange={(e) =>
                      setNewPassenger({ ...newPassenger, last_name: e.target.value })
                    }
                    className="w-full px-3 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                    placeholder="Doe"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Date of Birth (YYYY-MM-DD)
                </label>
                <input
                  type="date"
                  value={newPassenger.date_of_birth}
                  onChange={(e) =>
                    setNewPassenger({ ...newPassenger, date_of_birth: e.target.value })
                  }
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Gender</label>
                <select
                  value={newPassenger.gender}
                  onChange={(e) => setNewPassenger({ ...newPassenger, gender: e.target.value })}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Passport Number (Optional)
                </label>
                <input
                  type="text"
                  value={newPassenger.passport_number}
                  onChange={(e) =>
                    setNewPassenger({ ...newPassenger, passport_number: e.target.value })
                  }
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 uppercase font-mono"
                  placeholder="Z1234567"
                />
              </div>

              <div className="flex gap-3 justify-end pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-brand-600 hover:bg-brand-700 transition-all flex items-center gap-1.5 shadow-md shadow-brand-500/20"
                >
                  {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
