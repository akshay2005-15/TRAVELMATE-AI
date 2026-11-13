import React from 'react';
import { SlidersHorizontal, ArrowUpDown, Check, RotateCcw } from 'lucide-react';

export default function FlightFilters({
  totalOffers,
  filterStops,
  setFilterStops,
  sortBy,
  setSortBy,
  maxPrice,
  setMaxPrice,
  priceRange
}) {
  return (
    <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-sm space-y-6 sticky top-20">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-brand-600" />
          Filter & Sort
        </h3>
        <span className="text-[11px] font-bold text-brand-700 bg-brand-50 px-2.5 py-0.5 rounded-full border border-brand-200/60">
          {totalOffers} {totalOffers === 1 ? 'flight' : 'flights'}
        </span>
      </div>

      {/* Sort By Selector */}
      <div>
        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
          Sort Results By
        </label>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs font-semibold text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors shadow-2xs"
        >
          <option value="price_asc">Price: Low to High (Cheapest)</option>
          <option value="duration_asc">Duration: Shortest (Fastest)</option>
          <option value="dep_time_asc">Departure: Earliest First</option>
        </select>
      </div>

      {/* Stops Filter */}
      <div>
        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          Stops
        </label>
        <div className="space-y-1.5 text-xs">
          {[
            { id: 'all', label: 'All Flights' },
            { id: 'nonstop', label: 'Non-stop Only' },
            { id: '1stop', label: '1 Stop or Fewer' },
          ].map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setFilterStops(option.id)}
              className={`w-full text-left px-3.5 py-2.5 rounded-xl flex items-center justify-between transition-all ${
                filterStops === option.id
                  ? 'bg-slate-900 text-white font-bold shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100/80 font-medium'
              }`}
            >
              <span>{option.label}</span>
              {filterStops === option.id && <Check className="w-3.5 h-3.5 text-brand-400" />}
            </button>
          ))}
        </div>
      </div>

      {/* Max Price Slider */}
      {priceRange.max > priceRange.min && (
        <div className="pt-2 border-t border-slate-100">
          <div className="flex justify-between items-center mb-2">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Max Price
            </label>
            <span className="text-xs font-extrabold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-lg border border-brand-200/50">
              ₹{maxPrice ? maxPrice.toLocaleString() : priceRange.max.toLocaleString()}
            </span>
          </div>

          <input
            type="range"
            min={priceRange.min}
            max={priceRange.max}
            step={100}
            value={maxPrice || priceRange.max}
            onChange={(e) => setMaxPrice(Number(e.target.value))}
            className="w-full accent-brand-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
          />

          <div className="flex justify-between text-[11px] text-slate-400 mt-1.5 font-medium">
            <span>₹{priceRange.min.toLocaleString()}</span>
            <span>₹{priceRange.max.toLocaleString()}</span>
          </div>
        </div>
      )}

      {/* Clear Filters Reset */}
      <button
        type="button"
        onClick={() => {
          setFilterStops('all');
          setSortBy('price_asc');
          setMaxPrice(priceRange.max);
        }}
        className="w-full py-2.5 text-center text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-colors flex items-center justify-center gap-1.5 border border-slate-200"
      >
        <RotateCcw className="w-3.5 h-3.5" />
        <span>Reset Filters</span>
      </button>
    </div>
  );
}
