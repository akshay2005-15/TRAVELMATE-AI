import React from 'react';
import { Plane, ShieldCheck, Cpu, Code2, Globe2, Sparkles, Activity } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="bg-slate-900 border-t border-slate-800 text-slate-400 mt-auto">
      <div className="max-w-7xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 pb-8 border-b border-slate-800/80">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-500 to-indigo-600 flex items-center justify-center text-white shadow-sm shadow-brand-500/20">
                <Plane className="w-4 h-4 -rotate-45" />
              </div>
              <span className="text-base font-black text-white tracking-tight">
                TRAVELMATE<span className="text-brand-400 ml-0.5">AI</span>
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono text-[10px] border border-slate-700">
                v1.0 Capstone
              </span>
            </div>
            <p className="text-xs text-slate-400 max-w-md leading-relaxed">
              Autonomous AI agent for conversational and manual flight discovery, transparent itinerary scoring, and deterministic booking state machine validation.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
              <span>Core Engines: <strong>Operational</strong></span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <Cpu className="w-3.5 h-3.5 text-indigo-400" />
              <span>Gemini 2.5 & LangGraph</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Safe 2-Step Verification</span>
            </div>
          </div>
        </div>

        <div className="pt-6 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-slate-500">
          <div>
            &copy; {new Date().getFullYear()} TRAVELMATE AI. Built with React, Tailwind CSS, and FastAPI.
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Final-Year B.E. Project</span>
            <span>•</span>
            <span>Academic Demonstration Engine</span>
            <span>•</span>
            <span className="text-amber-400/90 font-medium">Zero Financial Liability</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
