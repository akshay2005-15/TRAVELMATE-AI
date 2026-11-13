import React from 'react';
import { Link } from 'react-router-dom';
import {
  Mic,
  MessageSquare,
  Plane,
  ShieldCheck,
  TrendingDown,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Lock,
  Compass,
  Cpu,
  Layers,
  Zap,
  Globe2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)] overflow-hidden">
      {/* Hero Section */}
      <section className="relative overflow-hidden py-16 sm:py-24 lg:py-28">
        {/* Ambient background glow orbs */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-gradient-to-tr from-brand-400/20 via-indigo-400/20 to-purple-400/10 blur-3xl pointer-events-none rounded-full -z-10" />
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          {/* Top Pill */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/90 border border-brand-200/80 text-brand-800 text-xs font-bold mb-8 shadow-sm backdrop-blur-md animate-in fade-in slide-in-from-bottom-2">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-600"></span>
            </span>
            <span>Final-Year B.E. Project</span>
            <span className="text-slate-300">|</span>
            <span className="bg-gradient-to-r from-brand-600 to-indigo-600 bg-clip-text text-transparent">
              Autonomous AI Flight Intelligence
            </span>
          </div>

          {/* Main Headline */}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-[1.1] sm:leading-[1.15]">
            Book Flights Naturally with{' '}
            <span className="bg-gradient-to-r from-brand-600 via-indigo-600 to-sky-500 bg-clip-text text-transparent">
              Voice & Text Intelligence
            </span>
          </h1>

          <p className="mt-6 text-base sm:text-lg lg:text-xl text-slate-600 max-w-2xl mx-auto leading-relaxed font-normal">
            TRAVELMATE AI pairs the reasoning power of <strong>Google Gemini & LangGraph</strong> with real airline inventory to autonomously find, rank, and book flights with human-in-the-loop safety.
          </p>

          {/* Primary CTA Buttons */}
          <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link
              to="/chat"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-8 py-4 rounded-2xl text-sm font-bold text-white bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 shadow-xl shadow-brand-500/25 transition-all duration-200 active:scale-95 group"
            >
              <Sparkles className="w-4 h-4 text-brand-200 group-hover:rotate-12 transition-transform" />
              <span>Chat with AI Assistant</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link
              to="/flights"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-4 rounded-2xl text-sm font-bold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200/90 shadow-sm transition-all duration-200 active:scale-95"
            >
              <Compass className="w-4 h-4 text-slate-500" />
              <span>Explore Flight Search</span>
            </Link>

            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-4 rounded-2xl text-sm font-bold text-slate-700 hover:text-brand-600 transition-colors"
              >
                Go to Dashboard
              </Link>
            ) : (
              <Link
                to="/register"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-4 rounded-2xl text-sm font-bold text-slate-700 hover:text-brand-600 transition-colors"
              >
                Create Account
              </Link>
            )}
          </div>

          {/* Verification Trust Badges */}
          <div className="mt-12 flex flex-wrap justify-center items-center gap-4 sm:gap-8 text-xs text-slate-600 font-semibold">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/70 border border-slate-200/70 shadow-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Voice-to-Text & Text-to-Speech</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/70 border border-slate-200/70 shadow-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Real Provider Inventory (Duffel API)</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/70 border border-slate-200/70 shadow-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Deterministic Approval State Machine</span>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Highlights Grid */}
      <section className="py-20 bg-white border-t border-slate-200/70">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <span className="text-xs font-bold uppercase tracking-widest text-brand-600 bg-brand-50 px-3 py-1 rounded-full border border-brand-200/50">
              Architecture & Compliance
            </span>
            <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-3">
              Core Architectural Pillars
            </h2>
            <p className="mt-2 text-slate-500 text-sm sm:text-base max-w-xl mx-auto">
              Built in accordance with IEEE Software Engineering specifications (SRS & SAD v1.0).
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Card 1 */}
            <div className="p-7 rounded-3xl bg-slate-50/70 border border-slate-200/80 hover:bg-white hover:border-brand-300 hover:shadow-xl hover:shadow-brand-500/5 transition-all duration-300 group">
              <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform shadow-xs">
                <Mic className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Multimodal Assistant</h3>
              <p className="mt-2 text-xs sm:text-sm text-slate-600 leading-relaxed">
                Seamlessly interact via natural voice commands or live text chat. Slot-filling automatically asks for missing departure dates, passenger count, or destinations.
              </p>
            </div>

            {/* Card 2 */}
            <div className="p-7 rounded-3xl bg-slate-50/70 border border-slate-200/80 hover:bg-white hover:border-brand-300 hover:shadow-xl hover:shadow-brand-500/5 transition-all duration-300 group">
              <div className="w-12 h-12 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform shadow-xs">
                <Plane className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Live Provider Adapter</h3>
              <p className="mt-2 text-xs sm:text-sm text-slate-600 leading-relaxed">
                Direct integration with Duffel Flight API. No hallucinated prices or fake availability; every offer is validated against provider inventory.
              </p>
            </div>

            {/* Card 3 */}
            <div className="p-7 rounded-3xl bg-slate-50/70 border border-slate-200/80 hover:bg-white hover:border-brand-300 hover:shadow-xl hover:shadow-brand-500/5 transition-all duration-300 group">
              <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform shadow-xs">
                <TrendingDown className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Transparent Ranking</h3>
              <p className="mt-2 text-xs sm:text-sm text-slate-600 leading-relaxed">
                Explainable scoring engine balancing cost, duration, stops, and departure timings with clear human-readable recommendation rationales.
              </p>
            </div>

            {/* Card 4 */}
            <div className="p-7 rounded-3xl bg-slate-50/70 border border-slate-200/80 hover:bg-white hover:border-brand-300 hover:shadow-xl hover:shadow-brand-500/5 transition-all duration-300 group">
              <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform shadow-xs">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Safe Booking Engine</h3>
              <p className="mt-2 text-xs sm:text-sm text-slate-600 leading-relaxed">
                2-step revalidation and explicit approval verification. Zero raw card storage with idempotency protections against duplicate charges.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Security & Verification Banner */}
      <section className="bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950 text-white py-14 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 p-6 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-md">
            <div className="flex items-center gap-5">
              <div className="p-3.5 bg-gradient-to-tr from-brand-600 to-indigo-600 rounded-2xl shadow-md text-white shrink-0">
                <Lock className="w-7 h-7" />
              </div>
              <div>
                <h3 className="text-lg font-bold tracking-tight text-white">
                  Strict Separation of AI & Transactional Truth
                </h3>
                <p className="text-slate-400 text-xs sm:text-sm mt-1 max-w-xl">
                  The LLM interprets natural language requests, but the backend deterministic state machine strictly controls and enforces booking authorization.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <Link
                to="/login"
                className="px-6 py-3 rounded-xl text-xs font-bold text-slate-900 bg-white hover:bg-slate-100 transition-colors shadow-md"
              >
                Sign In to Demo
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
