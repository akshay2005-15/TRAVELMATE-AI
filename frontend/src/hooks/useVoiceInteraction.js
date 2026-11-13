import { useState, useEffect, useRef, useCallback } from 'react';
import { sanitizeTextForSpeech } from '../utils/speechSanitizer';
import { selectPreferredVoice, CONVERSATIONAL_VOICE_SETTINGS } from '../utils/voiceSelector';

/**
 * Custom React Hook for TRAVELMATE AI Voice Interaction.
 * Provides:
 * - Speech-to-Text (STT) via Web Speech API (SpeechRecognition / webkitSpeechRecognition).
 * - Text-to-Speech (TTS) via SpeechSynthesis with sanitization, natural female voice selection
 *   (preferring Indian English en-IN with fallback to Chrome/Edge natural female voices),
 *   conversational pacing, autoplay unsticking, debounced user controls, and stale-event protection.
 */
export function useVoiceInteraction() {
  // --- Speech-to-Text (STT) State ---
  const [isListening, setIsListening] = useState(false);
  const [sttError, setSttError] = useState(null);
  const recognitionRef = useRef(null);
  const isAbortedRef = useRef(false);

  const isSTTSupported =
    typeof window !== 'undefined' &&
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

  // --- Text-to-Speech (TTS) State ---
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);
  const [isMuted, setIsMuted] = useState(() => {
    try {
      return localStorage.getItem('travelmate_voice_muted') === 'true';
    } catch {
      return false;
    }
  });
  const [voices, setVoices] = useState([]);

  // Lifecycle & timing refs to avoid stale closures and cancellation cascades
  const isSpeakingRef = useRef(false);
  const speakingMessageIdRef = useRef(null);
  const isMutedRef = useRef(isMuted);
  const speechInitiatorRef = useRef(null); // 'user' | 'auto' | null
  const speechStartTimeRef = useRef(0);
  const lastClickTimeRef = useRef(0);

  const lastAutoSpokenIdRef = useRef(null);
  const activeUtteranceRef = useRef(null);
  const keepAliveTimerRef = useRef(null);
  const speakTimeoutRef = useRef(null);

  const isTTSSupported =
    typeof window !== 'undefined' && 'speechSynthesis' in window;

  // Keep refs in sync with state for stable callbacks
  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  useEffect(() => {
    speakingMessageIdRef.current = speakingMessageId;
  }, [speakingMessageId]);

  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  // Initialize and load TTS voices
  useEffect(() => {
    if (!isTTSSupported) {
      console.warn('[TTS] SpeechSynthesis is not supported in this browser environment.');
      return;
    }

    const loadVoices = () => {
      try {
        const available = window.speechSynthesis.getVoices();
        if (available && available.length > 0) {
          console.log(`[TTS] Voices loaded: ${available.length} available.`);
          setVoices(available);
        }
      } catch (err) {
        console.error('[TTS] Error loading voices:', err);
      }
    };

    // Load initial voices immediately
    loadVoices();

    // Attach voiceschanged listener using addEventListener and onvoiceschanged
    if (window.speechSynthesis.addEventListener) {
      window.speechSynthesis.addEventListener('voiceschanged', loadVoices);
    } else if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }

    // Chrome and WebKit browsers often populate voices asynchronously after page mount.
    // Use multi-stage polling intervals to reliably capture available voices as soon as ready.
    const pollDelays = [50, 150, 350, 750, 1500, 3000];
    const pollTimers = pollDelays.map((delay) => setTimeout(loadVoices, delay));

    return () => {
      pollTimers.forEach(clearTimeout);
      if (window.speechSynthesis.removeEventListener) {
        window.speechSynthesis.removeEventListener('voiceschanged', loadVoices);
      }
      // Note: Do NOT call window.speechSynthesis.cancel() here!
    };
  }, [isTTSSupported]);

  // Find best natural female voice
  // Prefers natural-sounding female Indian English (en-IN), falling back to natural female Chrome/Edge voices
  const getPreferredVoice = useCallback(() => {
    let voiceList = [];
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      voiceList = window.speechSynthesis.getVoices();
    }
    if (!voiceList || voiceList.length === 0) {
      voiceList = voices;
    }

    if (!voiceList || voiceList.length === 0) {
      console.log('[TTS] No voices returned by browser yet; using system default voice.');
      return null;
    }

    const selected = selectPreferredVoice(voiceList);
    if (selected) {
      console.log(
        `[TTS] Selected voice: "${selected.name}" (${selected.lang}), localService: ${Boolean(selected.localService)}`
      );
      return selected;
    }

    console.log(`[TTS] Using default browser voice: "${voiceList[0]?.name}"`);
    return voiceList[0] || null;
  }, [voices]);

  // Stop speaking
  const stopSpeaking = useCallback(() => {
    if (isTTSSupported) {
      console.log('[TTS] stopSpeaking called. Cancelling active utterances.');
      if (keepAliveTimerRef.current) {
        clearInterval(keepAliveTimerRef.current);
        keepAliveTimerRef.current = null;
      }
      if (speakTimeoutRef.current) {
        clearTimeout(speakTimeoutRef.current);
        speakTimeoutRef.current = null;
      }
      activeUtteranceRef.current = null;
      window._activeTravelmateUtterance = null;
      speechInitiatorRef.current = null;
      speechStartTimeRef.current = 0;

      try {
        window.speechSynthesis.cancel();
      } catch (e) {
        console.warn('[TTS] Error cancelling speechSynthesis:', e);
      }
      setIsSpeaking(false);
      setSpeakingMessageId(null);
    }
  }, [isTTSSupported]);

  // Toggle Mute
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      console.log(`[TTS] Voice output toggled to: ${next ? 'MUTED' : 'UNMUTED'}`);
      try {
        localStorage.setItem('travelmate_voice_muted', String(next));
      } catch (err) {
        console.error('[TTS] Failed to save mute state to localStorage', err);
      }
      if (next) {
        stopSpeaking();
      }
      return next;
    });
  }, [stopSpeaking]);

  /**
   * Speak AI assistant response.
   * Handles user clicks and auto-play cleanly without premature cancellation.
   */
  const speakText = useCallback(
    (rawText, messageId = null, options = {}) => {
      const { isUserClick = false, isAuto = false } = options;
      const now = Date.now();

      console.log('[TTS] speakText invoked:', {
        messageId,
        isUserClick,
        isAuto,
        currentIsSpeaking: isSpeakingRef.current,
        currentSpeakingMessageId: speakingMessageIdRef.current,
        isMuted: isMutedRef.current,
        textLength: rawText?.length,
      });

      if (!isTTSSupported) {
        console.warn('[TTS] Speech synthesis is not supported in this browser.');
        return;
      }

      if (!rawText || !rawText.trim()) {
        console.warn('[TTS] Empty text provided to speakText. Aborting.');
        return;
      }

      // Debounce rapid user clicks (< 300ms) to prevent accidental double-click cancel loops
      if (isUserClick) {
        if (now - lastClickTimeRef.current < 300) {
          console.log('[TTS] Ignoring rapid duplicate click within 300ms.');
          return;
        }
        lastClickTimeRef.current = now;
      }

      // Check if user is clicking to toggle off currently playing message:
      // Only toggle off if:
      // 1. Same message is actively speaking
      // 2. It was initiated by user click
      // 3. It has been speaking for at least 500ms (so initial click doesn't cancel itself)
      const isSameMessagePlaying =
        isSpeakingRef.current && speakingMessageIdRef.current === messageId;
      const wasInitiatedByUser = speechInitiatorRef.current === 'user';
      const hasSpokenLongEnough = now - speechStartTimeRef.current > 500;

      if (isUserClick && isSameMessagePlaying && wasInitiatedByUser && hasSpokenLongEnough) {
        console.log('[TTS] User intentionally clicked speaker to stop playback:', messageId);
        stopSpeaking();
        return;
      }

      // If auto-speaking and voice is muted, skip
      if (isAuto && isMutedRef.current) {
        console.log('[TTS] Auto-speak skipped: voice output is muted by user preference.');
        return;
      }

      // If auto-speaking and already spoken this message ID, skip to avoid repeated audio
      if (isAuto && messageId && lastAutoSpokenIdRef.current === messageId) {
        console.log('[TTS] Auto-speak skipped: already spoke message ID:', messageId);
        return;
      }

      // If user explicitly clicked the speaker icon and voice was muted, automatically unmute
      if (isUserClick && isMutedRef.current) {
        console.log('[TTS] User explicitly clicked speaker icon. Automatically unmuting voice.');
        setIsMuted(false);
        try {
          localStorage.setItem('travelmate_voice_muted', 'false');
        } catch {
          // ignore
        }
      }

      const cleanText = sanitizeTextForSpeech(rawText);
      console.log('[TTS] Sanitized text preview:', cleanText.slice(0, 100));

      if (!cleanText) {
        console.warn('[TTS] Sanitized text is empty after removing metadata.');
        return;
      }

      // Clear any pending timers
      if (speakTimeoutRef.current) {
        clearTimeout(speakTimeoutRef.current);
        speakTimeoutRef.current = null;
      }
      if (keepAliveTimerRef.current) {
        clearInterval(keepAliveTimerRef.current);
        keepAliveTimerRef.current = null;
      }

      // Mark initiator before starting
      speechInitiatorRef.current = isUserClick ? 'user' : 'auto';

      // Unstick paused state and cancel prior speech cleanly
      try {
        if (window.speechSynthesis.paused) {
          console.log('[TTS] speechSynthesis was paused. Resuming before cancel.');
          window.speechSynthesis.resume();
        }
        window.speechSynthesis.cancel();
      } catch (e) {
        console.warn('[TTS] Error resetting speechSynthesis state:', e);
      }

      // Track auto-spoken message
      if (isAuto && messageId) {
        lastAutoSpokenIdRef.current = messageId;
      }

      // Delay slightly (35ms) to ensure Chrome's cancel() IPC processes before speak()
      speakTimeoutRef.current = setTimeout(() => {
        try {
          if (window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
          }

          const utterance = new SpeechSynthesisUtterance(cleanText);
          const voice = getPreferredVoice();

          if (voice) {
            utterance.voice = voice;
            utterance.lang = voice.lang || 'en-IN';
          } else {
            utterance.lang = 'en-IN';
          }

          utterance.volume = CONVERSATIONAL_VOICE_SETTINGS.volume;
          utterance.rate = CONVERSATIONAL_VOICE_SETTINGS.rate;
          utterance.pitch = CONVERSATIONAL_VOICE_SETTINGS.pitch;

          // Prevent Chrome garbage collection by storing strong persistent reference
          activeUtteranceRef.current = utterance;
          window._activeTravelmateUtterance = utterance;

          utterance.onstart = () => {
            speechStartTimeRef.current = Date.now();
            console.log(`[TTS] Speech started successfully for message ID: ${messageId}`);
            setIsSpeaking(true);
            setSpeakingMessageId(messageId);

            // Chrome keep-alive hack to prevent long speech freeze after 15 seconds
            if (keepAliveTimerRef.current) {
              clearInterval(keepAliveTimerRef.current);
            }
            keepAliveTimerRef.current = setInterval(() => {
              if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
                window.speechSynthesis.pause();
                window.speechSynthesis.resume();
              }
            }, 10000);
          };

          utterance.onend = () => {
            console.log(`[TTS] Speech finished successfully for message ID: ${messageId}`);
            // Guard against stale utterances
            if (activeUtteranceRef.current === utterance) {
              if (keepAliveTimerRef.current) {
                clearInterval(keepAliveTimerRef.current);
                keepAliveTimerRef.current = null;
              }
              activeUtteranceRef.current = null;
              window._activeTravelmateUtterance = null;
              speechInitiatorRef.current = null;
              speechStartTimeRef.current = 0;
              setIsSpeaking(false);
              setSpeakingMessageId(null);
            }
          };

          utterance.onerror = (e) => {
            const errType = e.error || 'unknown';
            if (errType === 'interrupted' || errType === 'canceled') {
              console.log(`[TTS] Utterance for message ${messageId} was ${errType} (expected during stop or cancel).`);
            } else {
              console.error(`[TTS] SpeechSynthesis error "${errType}" on message ${messageId}:`, {
                error: errType,
                elapsedTime: e.elapsedTime,
                charIndex: e.charIndex,
              });
            }

            // Guard against stale utterances
            if (activeUtteranceRef.current === utterance) {
              if (keepAliveTimerRef.current) {
                clearInterval(keepAliveTimerRef.current);
                keepAliveTimerRef.current = null;
              }
              activeUtteranceRef.current = null;
              window._activeTravelmateUtterance = null;
              speechInitiatorRef.current = null;
              speechStartTimeRef.current = 0;
              setIsSpeaking(false);
              setSpeakingMessageId(null);
            }
          };

          console.log('[TTS] Calling window.speechSynthesis.speak()...');
          window.speechSynthesis.speak(utterance);
        } catch (speakErr) {
          console.error('[TTS] Exception during speechSynthesis.speak:', speakErr);
          setIsSpeaking(false);
          setSpeakingMessageId(null);
        }
      }, 35);
    },
    [isTTSSupported, getPreferredVoice, stopSpeaking]
  );

  // Start speech recognition
  const startListening = useCallback(
    (onTranscriptChange, initialBaseText = '') => {
      if (!isSTTSupported) {
        setSttError('Voice recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
        return;
      }

      // If bot is speaking, cancel speech immediately to prevent audio feedback
      stopSpeaking();

      try {
        setSttError(null);
        isAbortedRef.current = false;

        const SpeechRecognitionClass =
          window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognitionClass();

        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
          setIsListening(true);
        };

        recognition.onresult = (event) => {
          let accumulated = '';
          for (let i = 0; i < event.results.length; i++) {
            accumulated += event.results[i][0].transcript;
          }

          const combined = initialBaseText
            ? `${initialBaseText.trim()} ${accumulated.trim()}`
            : accumulated.trim();

          if (onTranscriptChange) {
            onTranscriptChange(combined);
          }
        };

        recognition.onerror = (event) => {
          if (isAbortedRef.current) return;
          console.warn('Speech recognition error:', event.error);

          switch (event.error) {
            case 'not-allowed':
              setSttError('Microphone access was denied. Please allow microphone permissions in your browser.');
              break;
            case 'no-speech':
              setSttError('No speech detected. Please click the mic and speak clearly.');
              break;
            case 'network':
              setSttError('Network error during voice recognition. Check your connection.');
              break;
            case 'aborted':
              // User or app cancelled, no error message needed
              break;
            default:
              setSttError(`Voice recognition error (${event.error}). Please try again.`);
          }
          setIsListening(false);
        };

        recognition.onend = () => {
          setIsListening(false);
        };

        recognitionRef.current = recognition;
        recognition.start();
      } catch (err) {
        console.error('Failed to start speech recognition:', err);
        setSttError('Could not start voice recognition. Please try again.');
        setIsListening(false);
      }
    },
    [isSTTSupported, stopSpeaking]
  );

  // Stop listening gracefully
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {
        console.warn('Error stopping speech recognition:', err);
      }
      setIsListening(false);
    }
  }, []);

  // Cancel listening (discard session)
  const cancelListening = useCallback(() => {
    if (recognitionRef.current) {
      isAbortedRef.current = true;
      try {
        recognitionRef.current.abort();
      } catch (err) {
        console.warn('Error aborting speech recognition:', err);
      }
      setIsListening(false);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }
      if (speakTimeoutRef.current) {
        clearTimeout(speakTimeoutRef.current);
      }
      if (keepAliveTimerRef.current) {
        clearInterval(keepAliveTimerRef.current);
      }
      if (isTTSSupported) {
        try {
          window.speechSynthesis.cancel();
        } catch {
          // ignore
        }
      }
    };
  }, [isTTSSupported]);

  return {
    // STT
    isListening,
    isSTTSupported,
    sttError,
    startListening,
    stopListening,
    cancelListening,
    clearSttError: () => setSttError(null),

    // TTS
    isSpeaking,
    speakingMessageId,
    isTTSSupported,
    isMuted,
    toggleMute,
    speakText,
    stopSpeaking,
  };
}
export default useVoiceInteraction;
