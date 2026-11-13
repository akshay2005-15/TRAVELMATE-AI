import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plane,
  Search,
  Calendar,
  Users,
  AlertCircle,
  Loader2,
  SlidersHorizontal,
  ShieldCheck,
  FlaskConical,
  Sparkles,
  Info,
  ArrowRight
} from 'lucide-react';
import AirportSelect from '../components/flights/AirportSelect';
import FlightCard from '../components/flights/FlightCard';
import FlightFilters from '../components/flights/FlightFilters';
import { flightService } from '../services/flightService';

export default function FlightSearchPage() {
  const navigate = useNavigate();
  // Form State
  const [origin, setOrigin] = useState('BLR');
  const [destination, setDestination] = useState('DEL');
  
  // Set default departure date to 7 days from today
  const defaultDeparture = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().split('T')[0];
  }, []);

  const [departureDate, setDepartureDate] = useState(defaultDeparture);
  const [returnDate, setReturnDate] = useState('');
  const [passengers, setPassengers] = useState(1);
  const [cabinClass, setCabinClass] = useState('economy');
  const [providerMode, setProviderMode] = useState('auto'); // 'auto', 'duffel', 'mock'

  // Results State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchResponse, setSearchResponse] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);

  // Filter & Sort State
  const [filterStops, setFilterStops] = useState('all'); // 'all', 'nonstop', '1stop'
  const [sortBy, setSortBy] = useState('price_asc');
  const [maxPrice, setMaxPrice] = useState(null);

  // Fetch provider status on load
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const status = await flightService.getProviderStatus();
        setProviderStatus(status);
      } catch (err) {
        console.warn('Could not query provider status:', err);
      }
    };
    checkStatus();

    // Run an initial search for default route
    handleSearch();
  }, []);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setError('');

    // Client-side quick check
    if (origin.toUpperCase() === destination.toUpperCase()) {
      setError('Origin and destination airports must be different.');
      return;
    }

    setLoading(true);

    try {
      const payload = {
        origin: origin.toUpperCase(),
        destination: destination.toUpperCase(),
        departure_date: departureDate,
        return_date: returnDate || null,
        passengers: Number(passengers),
        cabin_class: cabinClass,
        force_provider: providerMode === 'auto' ? null : providerMode
      };

      const result = await flightService.searchFlights(payload);
      setSearchResponse(result);

      // Reset max price when new results arrive
      if (result.offers && result.offers.length > 0) {
        const prices = result.offers.map((o) => o.total_amount);
        setMaxPrice(Math.max(...prices));
      }
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail || 'Failed to search flights. Please verify your search criteria.';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // Compute min and max price from current result set
  const priceRange = useMemo(() => {
    if (!searchResponse || !searchResponse.offers || searchResponse.offers.length === 0) {
      return { min: 0, max: 0 };
    }
    const prices = searchResponse.offers.map((o) => o.total_amount);
    return {
      min: Math.min(...prices),
      max: Math.max(...prices),
    };
  }, [searchResponse]);

  // Filtered and sorted offers
  const filteredOffers = useMemo(() => {
    if (!searchResponse || !searchResponse.offers) return [];

    let list = [...searchResponse.offers];

    // Filter by stops
    if (filterStops === 'nonstop') {
      list = list.filter((o) => o.stops === 0);
    } else if (filterStops === '1stop') {
      list = list.filter((o) => o.stops <= 1);
    }

    // Filter by max price
    if (maxPrice) {
      list = list.filter((o) => o.total_amount <= maxPrice);
    }

    // Sort
    if (sortBy === 'price_asc') {
      list.sort((a, b) => a.total_amount - b.total_amount);
    } else if (sortBy === 'duration_asc') {
      list.sort((a, b) => a.duration_minutes - b.duration_minutes);
    } else if (sortBy === 'dep_time_asc') {
      list.sort((a, b) => new Date(a.departure_time) - new Date(b.departure_time));
    }

    return list;
  }, [searchResponse, filterStops, maxPrice, sortBy]);

  const handleSelectOffer = (offer) => {
    sessionStorage.setItem('travelmate_selected_offer', JSON.stringify(offer));
    navigate('/booking/passengers', { state: { offer } });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Page Header & Provider Transparency Pill */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-200/80">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-50 text-brand-700 text-xs font-bold mb-2 border border-brand-200/60">
            <Sparkles className="w-3.5 h-3.5 text-brand-500" />
            <span>Flight Discovery Engine</span>
          </div>
          <h1 className="text-2xl sm:text-4xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-600 via-brand-500 to-indigo-600 text-white flex items-center justify-center shadow-md shadow-brand-500/20">
              <Plane className="w-5 h-5 -rotate-45" />
            </div>
            <span>Find & Book Flights</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Real provider distribution via Duffel API with authentic offline simulation fallback.
          </p>
        </div>

        {/* Live Provider Status Banner */}
        <div className="flex items-center gap-2 text-xs">
          {providerStatus?.duffel_available ? (
            <div className="inline-flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-blue-50 border border-blue-200 text-blue-900 font-bold shadow-2xs">
              <ShieldCheck className="w-4 h-4 text-blue-600" />
              <span>Duffel Sandbox: <strong>Active</strong></span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 font-bold shadow-2xs">
              <FlaskConical className="w-4 h-4 text-amber-600" />
              <span>Mock Simulation: <strong>Ready (Fallback)</strong></span>
            </div>
          )}
        </div>
      </div>

      {/* Flight Search Form Box */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm p-6 sm:p-8">
        <form onSubmit={handleSearch} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Origin Airport */}
            <AirportSelect
              label="From (Origin)"
              value={origin}
              onChange={(code) => setOrigin(code)}
              placeholder="e.g. BLR, Delhi"
            />

            {/* Destination Airport */}
            <AirportSelect
              label="To (Destination)"
              value={destination}
              onChange={(code) => setDestination(code)}
              placeholder="e.g. DEL, Mumbai"
            />

            {/* Departure Date */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Departure Date
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Calendar className="w-4 h-4" />
                </div>
                <input
                  type="date"
                  required
                  min={new Date().toISOString().split('T')[0]}
                  value={departureDate}
                  onChange={(e) => setDepartureDate(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-3 rounded-2xl border border-slate-300 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all shadow-2xs bg-white"
                />
              </div>
            </div>

            {/* Passengers & Cabin Class */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Travelers
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Users className="w-4 h-4" />
                  </div>
                  <select
                    value={passengers}
                    onChange={(e) => setPassengers(Number(e.target.value))}
                    className="w-full pl-9 pr-2 py-3 rounded-2xl border border-slate-300 text-xs sm:text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all shadow-2xs bg-white"
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                      <option key={n} value={n}>
                        {n} {n === 1 ? 'Adult' : 'Adults'}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Class
                </label>
                <select
                  value={cabinClass}
                  onChange={(e) => setCabinClass(e.target.value)}
                  className="w-full px-3 py-3 rounded-2xl border border-slate-300 text-xs sm:text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all shadow-2xs bg-white"
                >
                  <option value="economy">Economy</option>
                  <option value="premium_economy">Prem. Eco</option>
                  <option value="business">Business</option>
                  <option value="first">First</option>
                </select>
              </div>
            </div>
          </div>

          {/* Provider Selection & Submit Button */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-100">
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
              <span className="font-bold text-slate-800">Provider Mode:</span>
              <label className="inline-flex items-center gap-1.5 cursor-pointer font-medium bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
                <input
                  type="radio"
                  name="provider_mode"
                  value="auto"
                  checked={providerMode === 'auto'}
                  onChange={() => setProviderMode('auto')}
                  className="text-brand-600 focus:ring-brand-500"
                />
                Auto (Duffel $\rightarrow$ Mock Fallback)
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer font-medium bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
                <input
                  type="radio"
                  name="provider_mode"
                  value="mock"
                  checked={providerMode === 'mock'}
                  onChange={() => setProviderMode('mock')}
                  className="text-brand-600 focus:ring-brand-500"
                />
                Mock Simulation
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full sm:w-auto px-8 py-3.5 rounded-2xl text-sm font-bold text-white bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 shadow-md shadow-brand-500/25 disabled:opacity-50 flex items-center justify-center gap-2 transition-all active:scale-95"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Searching Live Offers...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Search Flights</span>
                </>
              )}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs sm:text-sm flex items-start gap-2.5 animate-in fade-in">
            <AlertCircle className="w-5 h-5 shrink-0 text-rose-500 mt-0.5" />
            <span className="font-medium">{error}</span>
          </div>
        )}
      </div>

      {/* Search Results Area */}
      {searchResponse && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          {/* Left: Filters Sidebar */}
          <div className="lg:col-span-1">
            <FlightFilters
              totalOffers={filteredOffers.length}
              filterStops={filterStops}
              setFilterStops={setFilterStops}
              sortBy={sortBy}
              setSortBy={setSortBy}
              maxPrice={maxPrice}
              setMaxPrice={setMaxPrice}
              priceRange={priceRange}
            />
          </div>

          {/* Right: Flight Offer Cards */}
          <div className="lg:col-span-3 space-y-4">
            {/* Condition 2 Transparency Notification Bar */}
            <div className={`p-4 rounded-2xl border text-xs sm:text-sm flex items-start gap-3 ${
              searchResponse.is_simulation
                ? 'bg-amber-50/80 border-amber-200/90 text-amber-900'
                : 'bg-blue-50/80 border-blue-200/90 text-blue-900'
            }`}>
              <Info className={`w-5 h-5 shrink-0 mt-0.5 ${
                searchResponse.is_simulation ? 'text-amber-600' : 'text-blue-600'
              }`} />
              <div>
                <span className="font-bold">
                  {searchResponse.is_simulation
                    ? 'Demonstration Notice: Displaying Simulated Flight Offers'
                    : 'Provider Notice: Displaying Duffel Sandbox Test Offers'}
                </span>
                <p className="mt-0.5 text-xs text-slate-600 leading-relaxed">
                  {searchResponse.is_simulation
                    ? 'All prices, airline flight numbers, and durations are simulated authentically for testing and academic viva evaluation.'
                    : 'Live sandbox inventory returned directly from the Duffel flight distribution API.'}
                </p>
              </div>
            </div>

            {filteredOffers.length === 0 ? (
              <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center space-y-2">
                <Plane className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <h3 className="text-base font-bold text-slate-800">No flights matched your filters</h3>
                <p className="text-xs text-slate-500">
                  Try adjusting your stops or maximum price filter.
                </p>
              </div>
            ) : (
              filteredOffers.map((offer) => (
                <FlightCard
                  key={offer.id || offer.provider_offer_id}
                  offer={offer}
                  onSelect={handleSelectOffer}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
