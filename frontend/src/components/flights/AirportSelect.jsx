import React, { useState, useEffect, useRef } from 'react';
import { Plane, Search, MapPin, Building2, Check } from 'lucide-react';
import { flightService } from '../../services/flightService';

export default function AirportSelect({ label, value, onChange, placeholder, error }) {
  const [query, setQuery] = useState(value || '');
  const [suggestions, setSuggestions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef(null);

  // Sync external value
  useEffect(() => {
    setQuery(value || '');
  }, [value]);

  // Query airport search API with debounce
  useEffect(() => {
    if (!isOpen) return;

    const timer = setTimeout(async () => {
      try {
        setLoading(true);
        const data = await flightService.getAirports(query);
        setSuggestions(data);
      } catch (err) {
        console.error('Failed to fetch airport suggestions:', err);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query, isOpen]);

  // Click outside listener to close dropdown
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (airport) => {
    setQuery(`${airport.city_name} (${airport.iata_code})`);
    onChange(airport.iata_code);
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={containerRef}>
      <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
        {label}
      </label>

      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
          <Plane className="w-4 h-4 -rotate-45" />
        </div>

        <input
          type="text"
          value={query}
          onFocus={() => setIsOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          placeholder={placeholder || 'Search city or IATA (e.g. BLR)'}
          className={`w-full pl-10 pr-3.5 py-3 rounded-2xl border text-sm font-semibold transition-all bg-white shadow-2xs ${error
              ? 'border-rose-300 focus:border-rose-500 focus:ring-2 focus:ring-rose-500/20'
              : 'border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20'
            }`}
        />
      </div>

      {error && <p className="mt-1 text-xs text-rose-600 font-medium">{error}</p>}

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute z-50 left-0 right-0 mt-2 max-h-64 overflow-y-auto bg-white/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-slate-200/90 py-1.5 text-sm divide-y divide-slate-100 animate-in fade-in slide-in-from-top-2">
          {loading ? (
            <div className="py-5 text-center text-xs text-slate-400 font-medium">Searching airports...</div>
          ) : suggestions.length === 0 ? (
            <div className="py-5 text-center text-xs text-slate-400 font-medium">No matching airports found</div>
          ) : (
            suggestions.map((airport) => (
              <button
                key={airport.iata_code}
                type="button"
                onClick={() => handleSelect(airport)}
                className="w-full text-left px-4 py-2.5 hover:bg-brand-50/80 flex items-center justify-between transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-slate-100 group-hover:bg-brand-100 text-slate-500 group-hover:text-brand-600 flex items-center justify-center shrink-0 transition-colors">
                    <Building2 className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-bold text-slate-900 group-hover:text-brand-900 block text-sm">
                      {airport.city_name}
                    </span>
                    <span className="text-[11px] text-slate-500 block truncate max-w-[200px]">
                      {airport.airport_name}
                    </span>
                  </div>
                </div>

                <div className="text-right">
                  <span className="px-2.5 py-1 text-xs font-mono font-black bg-slate-100 text-slate-800 rounded-lg group-hover:bg-brand-600 group-hover:text-white transition-colors">
                    {airport.iata_code}
                  </span>
                  <span className="text-[10px] text-slate-400 block mt-0.5">{airport.country}</span>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
