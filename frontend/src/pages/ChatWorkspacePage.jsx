import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Plane,
  PanelLeftOpen,
  PanelLeftClose,
  Loader2,
  AlertCircle,
  RefreshCw,
  Plus,
  Volume2,
  VolumeX,
  Square,
  Bot
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import chatService from '../services/chatService';
import useVoiceInteraction from '../hooks/useVoiceInteraction';
import ChatSidebar from '../components/chat/ChatSidebar';
import ChatMessage from '../components/chat/ChatMessage';
import ChatInput from '../components/chat/ChatInput';
import PromptSuggestions from '../components/chat/PromptSuggestions';

export default function ChatWorkspacePage() {
  const { user, isAuthenticated } = useAuth();
  const voice = useVoiceInteraction();

  // Conversation & Message State
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');

  // UI States
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState(null);

  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom of message list
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Load user conversation list on mount
  const fetchConversations = async () => {
    if (!isAuthenticated) return;
    try {
      setLoadingConversations(true);
      const data = await chatService.getConversations();
      setConversations(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setLoadingConversations(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, [isAuthenticated]);

  // Load a specific conversation's history
  const handleSelectConversation = async (convId) => {
    try {
      voice.stopSpeaking();
      if (voice.isListening) voice.stopListening();
      setError(null);
      setLoadingHistory(true);
      setActiveConversationId(convId);

      const conv = await chatService.getConversationHistory(convId);

      // Transform backend Message objects to UI format
      const formatted = (conv.messages || []).map((m) => {
        let parsedSlots = null;
        if (m.slots_json) {
          try {
            parsedSlots = JSON.parse(m.slots_json);
          } catch {
            parsedSlots = null;
          }
        }
        return {
          id: m.id,
          role: m.role,
          content: m.content,
          slots: parsedSlots,
          flight_offers: null,
          search_status: m.flight_search_id ? 'search_executed' : 'collecting_information',
          created_at: m.created_at,
        };
      });

      setMessages(formatted);
    } catch (err) {
      console.error('Failed to retrieve conversation history:', err);
      setError('Unable to load conversation messages. Please try again.');
    } finally {
      setLoadingHistory(false);
    }
  };

  // Start a fresh conversation session
  const handleNewConversation = () => {
    voice.stopSpeaking();
    if (voice.isListening) voice.stopListening();
    setActiveConversationId(null);
    setMessages([]);
    setInput('');
    setError(null);
  };

  // Delete a conversation session
  const handleDeleteConversation = async (convId) => {
    try {
      voice.stopSpeaking();
      await chatService.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleNewConversation();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      setError('Failed to delete conversation. Please try again.');
    }
  };

  // Send message to AI assistant
  const handleSendMessage = async (textOverride = null) => {
    const textToSend = (textOverride || input).trim();
    if (!textToSend || loading) return;

    voice.stopSpeaking();
    if (voice.isListening) voice.stopListening();

    setError(null);
    setInput('');

    // Append optimistic user message
    const userMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: textToSend,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await chatService.sendMessage(textToSend, activeConversationId);

      // Update active conversation ID if newly created
      if (!activeConversationId && response.conversation_id) {
        setActiveConversationId(response.conversation_id);
        fetchConversations();
      }

      // Append assistant reply with flight offers and search metadata
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.assistant_message,
        slots: response.slots,
        missing_fields: response.missing_fields,
        search_status: response.search_status,
        flight_offers: response.flight_offers,
        search_metadata: response.search_metadata,
        booking_workflow_state: response.booking_workflow_state,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Automatically speak assistant response if voice output is active
      if (!voice.isMuted && assistantMessage.content) {
        voice.speakText(assistantMessage.content, assistantMessage.id, { isAuto: true });
      }
    } catch (err) {
      console.error('Chat error:', err);
      const errorMsg =
        err.response?.data?.detail ||
        'The flight assistant was unable to process your message. Please check your connection and try again.';
      setError(errorMsg);

      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ ${errorMsg}`,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-slate-100 overflow-hidden">
      {/* Sidebar Drawer */}
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        isAuthenticated={isAuthenticated}
        loadingConversations={loadingConversations}
      />

      {/* Main Chat Workspace */}
      <div className="flex-1 flex flex-col h-full bg-slate-50/70 relative overflow-hidden">
        {/* Workspace Top Header Bar */}
        <header className="h-16 bg-white/95 backdrop-blur-xl border-b border-slate-200/90 px-4 sm:px-6 flex items-center justify-between shrink-0 shadow-xs z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              title={sidebarOpen ? 'Collapse Sidebar' : 'Open History'}
              aria-label="Toggle sidebar"
            >
              {sidebarOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5" />}
            </button>

            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-brand-600 via-brand-500 to-indigo-600 text-white flex items-center justify-center shadow-md shadow-brand-500/20">
                <Plane className="w-4.5 h-4.5 -rotate-45" />
              </div>
              <div>
                <h2 className="text-sm font-black text-slate-900 flex items-center gap-2 leading-none">
                  <span>AI Flight Assistant</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="System Online" />
                </h2>
                <span className="text-[11px] text-slate-400 font-semibold">
                  {isAuthenticated ? `Session: ${user?.full_name}` : 'Guest Session Active'}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Speaking Status Pill */}
            {voice.isSpeaking && (
              <div className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full text-xs text-emerald-800 animate-in fade-in shadow-2xs">
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="font-bold hidden sm:inline">Speaking</span>
                <button
                  type="button"
                  onClick={voice.stopSpeaking}
                  className="inline-flex items-center gap-1 text-emerald-700 hover:text-emerald-950 font-bold ml-1 text-xs px-1.5 py-0.5 rounded-md bg-emerald-100/70 hover:bg-emerald-100"
                  title="Stop speaking"
                >
                  <Square className="w-2.5 h-2.5 fill-current" />
                  <span>Stop</span>
                </button>
              </div>
            )}

            {/* Mute / Unmute Voice Toggle */}
            {voice.isTTSSupported && (
              <button
                type="button"
                onClick={voice.toggleMute}
                className={`p-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  voice.isMuted
                    ? 'bg-slate-100 text-slate-400 hover:text-slate-600'
                    : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200/60'
                }`}
                title={voice.isMuted ? 'Voice output muted (click to unmute)' : 'Voice output active (click to mute)'}
                aria-label={voice.isMuted ? 'Unmute voice output' : 'Mute voice output'}
              >
                {voice.isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4 text-indigo-600" />}
                <span className="hidden sm:inline">{voice.isMuted ? 'Muted' : 'Voice On'}</span>
              </button>
            )}

            <button
              onClick={handleNewConversation}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 hover:text-slate-900 transition-colors shadow-2xs"
              title="Reset conversation"
            >
              <Plus className="w-3.5 h-3.5 text-slate-500" />
              <span className="hidden sm:inline">New Search</span>
            </button>
          </div>
        </header>

        {/* Error Banner */}
        {error && (
          <div className="bg-rose-50 border-b border-rose-200 px-4 py-2.5 text-xs text-rose-700 flex items-center justify-between animate-in fade-in">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
              <span className="font-medium">{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-rose-500 hover:text-rose-800 font-bold ml-2"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Scrollable Chat Stream */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="max-w-4xl mx-auto">
            {loadingHistory ? (
              <div className="py-20 text-center">
                <Loader2 className="w-8 h-8 text-brand-600 animate-spin mx-auto mb-3" />
                <p className="text-sm font-semibold text-slate-600">Loading conversation history...</p>
              </div>
            ) : messages.length === 0 ? (
              /* Welcome Screen / Empty State */
              <div className="text-center py-8 sm:py-14 animate-in fade-in">
                <div className="w-18 h-18 rounded-3xl bg-gradient-to-tr from-brand-600 via-brand-500 to-indigo-600 text-white flex items-center justify-center mx-auto mb-5 shadow-xl shadow-brand-500/25">
                  <Sparkles className="w-9 h-9" />
                </div>
                <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">
                  Where would you like to fly?
                </h1>
                <p className="text-xs sm:text-sm text-slate-500 max-w-lg mx-auto mt-2.5 mb-8 leading-relaxed font-normal">
                  I am your <strong>TRAVELMATE AI flight copilot</strong>. Ask in natural language or speak your request. I will find verified live options or authentic simulation offers.
                </p>

                {/* Prompt Suggestion Chips */}
                <PromptSuggestions onSelectPrompt={(prompt) => handleSendMessage(prompt)} />
              </div>
            ) : (
              /* Conversation Messages */
              messages.map((msg, index) => (
                <ChatMessage
                  key={msg.id || index}
                  message={msg}
                  isCurrentSpeaking={voice.isSpeaking && voice.speakingMessageId === msg.id}
                  onSpeakMessage={(text, id) => voice.speakText(text, id, { isUserClick: true })}
                  onActionClick={(text) => handleSendMessage(text)}
                />
              ))
            )}

            {/* AI Reasoning / Loading Indicator */}
            {loading && (
              <div className="flex items-start gap-3.5 my-4 animate-in fade-in">
                <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white flex items-center justify-center shrink-0 shadow-md shadow-brand-500/20">
                  <Plane className="w-4.5 h-4.5 -rotate-45" />
                </div>
                <div className="bg-white border border-slate-200/90 rounded-3xl rounded-bl-sm px-5 py-3.5 shadow-sm flex items-center gap-3">
                  <Loader2 className="w-4 h-4 text-brand-600 animate-spin" />
                  <span className="text-xs sm:text-sm text-slate-600 font-semibold">
                    TRAVELMATE AI is reasoning with LangGraph & querying flight provider...
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Bottom Input Field */}
        <ChatInput
          input={input}
          setInput={setInput}
          onSendMessage={() => handleSendMessage()}
          loading={loading}
          disabled={loadingHistory}
          isListening={voice.isListening}
          isSTTSupported={voice.isSTTSupported}
          sttError={voice.sttError}
          onStartListening={voice.startListening}
          onStopListening={voice.stopListening}
          onCancelListening={voice.cancelListening}
          onClearSttError={voice.clearSttError}
        />
      </div>
    </div>
  );
}
