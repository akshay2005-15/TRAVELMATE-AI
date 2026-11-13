import React, { useState } from 'react';
import {
  Plus,
  MessageSquare,
  Trash2,
  X,
  Plane,
  LogIn,
  Clock,
  Sparkles,
  Compass
} from 'lucide-react';
import { Link } from 'react-router-dom';

export default function ChatSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  isOpen,
  onClose,
  isAuthenticated,
  loadingConversations,
}) {
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  const formatRelativeTime = (isoString) => {
    try {
      const dt = new Date(isoString);
      const now = new Date();
      const diffMs = now - dt;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;
      return dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 md:hidden"
        />
      )}

      {/* Sidebar Drawer */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 w-72 sm:w-80 bg-white border-r border-slate-200/90 flex flex-col transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full md:translate-x-0'
          }`}
      >
        {/* Top Header & New Conversation Button */}
        <div className="p-4 border-b border-slate-200/80 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-black text-slate-900 text-sm">
              <div className="w-6 h-6 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-200/50">
                <Sparkles className="w-3.5 h-3.5 text-brand-600" />
              </div>
              <span>Flight Inquiries</span>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 md:hidden"
              aria-label="Close sidebar"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <button
            onClick={() => {
              onNewConversation();
              if (window.innerWidth < 768) onClose();
            }}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-2xl text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 shadow-md shadow-brand-500/20 active:scale-95 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>New Flight Inquiry</span>
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {loadingConversations ? (
            <div className="p-4 text-center text-xs text-slate-400 font-medium">Loading sessions...</div>
          ) : !isAuthenticated ? (
            <div className="p-5 text-center bg-slate-50/70 rounded-2xl border border-dashed border-slate-200 mx-1 space-y-2">
              <div className="w-10 h-10 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                <MessageSquare className="w-5 h-5" />
              </div>
              <p className="text-xs font-bold text-slate-800">Guest Session Active</p>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Sign in to save your conversation history across devices.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold bg-brand-50 text-brand-700 rounded-xl hover:bg-brand-100 border border-brand-200/60 transition-colors shadow-2xs mt-1"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </Link>
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-6 text-center text-slate-400 text-xs space-y-1">
              <Compass className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="font-bold text-slate-700">No previous inquiries</p>
              <p className="text-[11px] text-slate-400">Ask the assistant to start a new search!</p>
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              const isDeleting = confirmDeleteId === conv.id;

              return (
                <div
                  key={conv.id}
                  className={`group relative flex items-center justify-between rounded-2xl px-3.5 py-2.5 text-xs transition-all ${isActive
                      ? 'bg-slate-900 text-white font-bold shadow-sm'
                      : 'text-slate-700 hover:bg-slate-100/80 font-medium'
                    }`}
                >
                  <button
                    onClick={() => {
                      onSelectConversation(conv.id);
                      if (window.innerWidth < 768) onClose();
                    }}
                    className="flex-1 text-left min-w-0 pr-2"
                  >
                    <div className="flex items-center gap-2">
                      <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-brand-400' : 'text-slate-400'}`} />
                      <span className="truncate">{conv.title || 'Flight Inquiry'}</span>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-slate-400 mt-1 pl-5.5">
                      <Clock className="w-2.5 h-2.5" />
                      <span>{formatRelativeTime(conv.updated_at)}</span>
                    </div>
                  </button>

                  {/* Delete Button / Confirmation */}
                  {isDeleting ? (
                    <div className="flex items-center gap-1 shrink-0 bg-white shadow-sm p-1 rounded-xl border border-rose-200 animate-in fade-in">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteConversation(conv.id);
                          setConfirmDeleteId(null);
                        }}
                        className="px-2 py-0.5 bg-rose-600 text-white rounded-lg text-[10px] font-bold hover:bg-rose-700 transition-colors"
                        title="Confirm Delete"
                      >
                        Delete
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDeleteId(null);
                        }}
                        className="px-1.5 py-0.5 text-slate-500 hover:text-slate-700 text-[10px]"
                        title="Cancel"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDeleteId(conv.id);
                      }}
                      className={`opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all shrink-0 ${isActive ? 'text-slate-400 hover:text-rose-400 hover:bg-slate-800' : 'text-slate-400 hover:text-rose-600 hover:bg-rose-50'
                        }`}
                      title="Delete conversation"
                      aria-label="Delete conversation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-3.5 border-t border-slate-200/80 text-[11px] text-slate-400 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-2">
            <Plane className="w-3.5 h-3.5 text-brand-600 -rotate-45" />
            <span className="font-bold text-slate-700">TRAVELMATE AI</span>
          </div>
          <span className="text-[10px] font-mono text-slate-400 font-semibold">Gemini & LangGraph</span>
        </div>
      </aside>
    </>
  );
}
