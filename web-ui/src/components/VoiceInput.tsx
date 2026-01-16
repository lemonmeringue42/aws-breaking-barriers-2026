import { useState, useEffect, useRef } from 'react';
import { BrowserSpeechRecognition, speak, stopSpeaking } from '../services/novaSonicService';

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  onSend: (text: string) => void;
  disabled?: boolean;
  speakResponses?: boolean;
}

const VoiceInput = ({ onTranscript, onSend, disabled, speakResponses = true }: VoiceInputProps) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isSupported, setIsSupported] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    recognitionRef.current = new BrowserSpeechRecognition((text, isFinal) => {
      setTranscript(text);
      onTranscript(text);
      
      // Reset silence timer on speech
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      
      if (isFinal) {
        // Auto-send after 1.5s of silence
        silenceTimerRef.current = setTimeout(() => {
          if (text.trim()) {
            onSend(text.trim());
            setTranscript('');
            stopListening();
          }
        }, 1500);
      }
    });
    
    setIsSupported(recognitionRef.current.isSupported());
    
    return () => {
      recognitionRef.current?.stop();
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    };
  }, []);

  const startListening = async () => {
    if (!recognitionRef.current || disabled) return;
    
    // Request microphone permission first
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      console.error('Microphone permission denied:', err);
      alert('Please allow microphone access to use voice input');
      return;
    }
    
    stopSpeaking();
    setIsSpeaking(false);
    setTranscript('');
    
    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
    }
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
  };

  const toggleListening = () => {
    if (isListening) {
      stopListening();
      if (transcript.trim()) {
        onSend(transcript.trim());
        setTranscript('');
      }
    } else {
      startListening();
    }
  };

  const toggleSpeaker = () => {
    if (isSpeaking) {
      stopSpeaking();
      setIsSpeaking(false);
    } else {
      setIsSpeaking(true);
    }
  };

  if (!isSupported) return null;

  return (
    <div className="ca-voice-controls">
      <button
        type="button"
        onClick={toggleSpeaker}
        className={`ca-voice-btn ca-speaker-btn ${isSpeaking ? 'active' : ''}`}
        aria-label={isSpeaking ? 'Disable voice responses' : 'Enable voice responses'}
        title={isSpeaking ? 'Voice responses on' : 'Voice responses off'}
      >
        {isSpeaking ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
            <line x1="23" y1="9" x2="17" y2="15"/>
            <line x1="17" y1="9" x2="23" y2="15"/>
          </svg>
        )}
      </button>
      
      <button
        type="button"
        onClick={toggleListening}
        disabled={disabled}
        className={`ca-voice-btn ca-mic-btn ${isListening ? 'listening' : ''}`}
        aria-label={isListening ? 'Stop listening' : 'Start voice input'}
        title={isListening ? 'Click to stop' : 'Click to speak'}
      >
        {isListening ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        )}
      </button>
      
      {isListening && (
        <div className="ca-voice-indicator">
          <span className="ca-pulse" aria-hidden="true"/>
          <span className="sr-only">Listening...</span>
        </div>
      )}
      
      {transcript && (
        <div className="ca-transcript-preview" aria-live="polite">
          {transcript}
        </div>
      )}
    </div>
  );
};

// Hook to speak assistant responses
export const useVoiceResponse = () => {
  const [enabled, setEnabled] = useState(false);
  
  const speakResponse = (text: string) => {
    if (!enabled) return;
    // Strip markdown and speak
    const cleanText = text
      .replace(/[#*_`~\[\]()]/g, '')
      .replace(/\n+/g, '. ')
      .trim();
    speak(cleanText);
  };
  
  return { enabled, setEnabled, speakResponse };
};

export default VoiceInput;
