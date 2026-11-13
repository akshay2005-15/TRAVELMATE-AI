import React from 'react';
import { Sparkles, ArrowRight, Compass, MapPin } from 'lucide-react';

const SUGGESTIONS = [
  {
    label: 'Bengaluru to Delhi',
    query: 'Find flights from Bangalore to Delhi next Friday',
    desc: 'Round-trip or one-way domestic flights',
    badge: 'Popular'
  },
  {
    label: 'Mumbai to London',
    query: 'Cheapest flights from Mumbai to London next week',
    desc: 'International search with best value',
    badge: 'Best Value'
  },
  {
    label: 'Weekend to Goa',
    query: 'Flights from Bangalore to Goa tomorrow for 2 passengers',
    desc: 'Multi-passenger short getaway',
    badge: 'Weekend'
  },
  {
    label: 'Delhi to Dubai Business',
    query: 'Find 1 ticket in business class from Delhi to Dubai on 2026-12-05',
    desc: 'Premium cabin flight search',
    badge: 'Business'
  },
];

export default function PromptSuggestions({ onSelectPrompt }) {
  return (
    <div className="w-full max-w-2xl mx-auto my-6 px-4">
      <div className="flex items-center gap-2 mb-3.5 text-xs font-bold text-slate-500 uppercase tracking-wider">
        <Sparkles className="w-4 h-4 text-brand-600" />
        <span>Suggested Flight Searches</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {SUGGESTIONS.map((item, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => onSelectPrompt(item.query)}
            className="text-left p-4 rounded-2xl border border-slate-200/90 bg-white hover:border-brand-400 hover:shadow-md transition-all group flex flex-col justify-between shadow-2xs"
          >
            <div>
              <div className="flex items-center justify-between font-bold text-sm text-slate-800 group-hover:text-brand-600 transition-colors">
                <span className="flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-slate-400 group-hover:text-brand-500" />
                  {item.label}
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 group-hover:bg-brand-50 text-slate-600 group-hover:text-brand-700 px-2 py-0.5 rounded-full border border-slate-200/70 transition-colors">
                  {item.badge}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1.5 line-clamp-1 font-medium">"{item.query}"</p>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
              <span>{item.desc}</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-brand-600 group-hover:translate-x-0.5 transition-all" />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
