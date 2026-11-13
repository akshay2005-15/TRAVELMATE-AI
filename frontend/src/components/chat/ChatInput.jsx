import React, { useRef, useEffect } from 'react';
import { Send, Loader2, Mic, MicOff, Square, X, AlertCircle, Sparkles } from 'lucide-react';

export default function ChatInput({
  input,
  setInput,
  onSendMessage,
  loading,
  disabled,
  isListening,
  isSTTSupported = true,
  sttError,
  onStartListening,
  onStopListening,
  onCancelListening,
  onClearSttError,
}) {
  const textareaRef = useRef(null);
  const initialTextRef = useRef('');

  // Auto-resize textarea height as text grows
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollH, 160)}px`;
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading && input.trim()) {
        if (isListening && onStopListening) {
          onStopListening();
        }
        onSendMessage();
      }
    }
  };

  const handleToggleVoice = () => {
    if (isListening) {
      if (onStopListening) onStopListening();
    } else {
      if (onStartListening) {
        initialTextRef.current = input;
        onStartListening((text) => setInput(text), input);
      }
    }
  };

  const handleCancelVoice = () => {
    if (onCancelListening) {
      onCancelListening();
    }
    setInput(initialTextRef.current);
  };

  return (
    <div className="bg-white/95 backdrop-blur-xl border-t border-slate-200/90 px-4 py-3 sm:py-4 shadow-lg">
      <div className="max-w-4xl mx-auto space-y-2.5">
        {/* STT Error Banner */}
        {sttError && (
          <div className="flex items-center justify-between text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-2xl px-3.5 py-2 animate-in fade-in">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
              <span className="font-medium">{sttError}</span>
            </div>
            {onClearSttError && (
              <button
                type="button"
                onClick={onClearSttError}
                className="text-rose-400 hover:text-rose-600 p-0.5 rounded-lg"
                aria-label="Dismiss error"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}

        {/* Listening Indicator Bar */}
        {isListening && (
          <div className="flex items-center justify-between bg-gradient-to-r from-rose-50 to-pink-50 border border-rose-200 rounded-2xl px-4 py-2.5 animate-in fade-in shadow-sm">
            <div className="flex items-center gap-3">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
              </span>
              <span className="text-xs font-bold text-rose-800">
                Listening to voice... Speak your flight criteria clearly
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleToggleVoice}
                className="text-xs px-3 py-1 rounded-xl bg-rose-600 text-white font-bold hover:bg-rose-700 transition-colors shadow-xs"
              >
                Done Speaking
              </button>
              <button
                type="button"
                onClick={handleCancelVoice}
                className="text-xs px-2.5 py-1 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition-colors font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!loading && input.trim()) {
              if (isListening && onStopListening) {
                onStopListening();
              }
              onSendMessage();
            }
          }}
          className={`relative flex items-end gap-2 bg-slate-50/80 border rounded-2xl p-2.5 shadow-inner transition-all ${
            isListening
              ? 'border-rose-400 ring-2 ring-rose-400/20 bg-rose-50/20'
              : 'border-slate-300 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20 focus-within:bg-white'
          }`}
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || loading}
            placeholder={
              isListening
                ? 'Listening to speech... (live preview appears here)'
                : "Ask anything about flights (e.g. 'Non-stop flights from BLR to DEL next Friday under 6000')..."
            }
            className="flex-1 bg-transparent resize-none border-0 text-slate-800 placeholder-slate-400 text-xs sm:text-sm focus:ring-0 focus:outline-none px-2 py-1.5 max-h-40 leading-relaxed disabled:opacity-50 font-medium"
          />

          <div className="flex items-center gap-1.5 shrink-0">
            {/* Microphone STT Button */}
            <button
              type="button"
              onClick={handleToggleVoice}
              disabled={disabled || loading || !isSTTSupported}
              title={
                !isSTTSupported
                  ? 'Voice recognition not supported in this browser (use Chrome, Edge, or Safari)'
                  : isListening
                  ? 'Stop listening'
                  : 'Speak request with microphone'
              }
              aria-label={isListening ? 'Stop listening' : 'Start voice input'}
              className={`inline-flex items-center justify-center w-10 h-10 rounded-xl transition-all ${
                isListening
                  ? 'bg-rose-500 text-white animate-pulse shadow-md shadow-rose-500/30 hover:bg-rose-600'
                  : !isSTTSupported
                  ? 'text-slate-300 cursor-not-allowed'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/80'
              }`}
            >
              {isListening ? (
                <Square className="w-4 h-4 fill-current" />
              ) : !isSTTSupported ? (
                <MicOff className="w-5 h-5 text-slate-300" />
              ) : (
                <Mic className="w-5 h-5" />
              )}
            </button>

            {/* Send Message Button */}
            <button
              type="submit"
              disabled={!input.trim() || loading || disabled}
              aria-label="Send message"
              className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 text-white hover:from-brand-500 hover:to-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed shadow-md shadow-brand-500/25 transition-all shrink-0 active:scale-95"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </form>

        <div className="flex items-center justify-between text-[11px] text-slate-400 px-1 font-medium">
          <span>
            Press <strong>Enter</strong> to send or click <strong>Mic</strong> to speak
          </span>
          <span className="flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-brand-500" />
            <span>Google Gemini NLP</span>
          </span>
        </div>
      </div>
    </div>
  );
}
