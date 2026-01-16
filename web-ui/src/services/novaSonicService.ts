import { fetchAuthSession } from 'aws-amplify/auth';

const REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';
const VOICE_WS_URL = import.meta.env.VITE_VOICE_WS_URL || '';

// Audio config
const INPUT_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;

type AudioCallback = (text: string, isFinal: boolean) => void;

export class NovaSonicClient {
  private ws: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private isActive = false;
  private promptName = crypto.randomUUID();
  private contentName = crypto.randomUUID();
  private audioContentName = crypto.randomUUID();
  private audioQueue: ArrayBuffer[] = [];
  private isPlaying = false;
  private onTranscript: AudioCallback;
  private onAssistantText: AudioCallback;
  private systemPrompt: string;

  constructor(
    onTranscript: AudioCallback,
    onAssistantText: AudioCallback,
    systemPrompt?: string
  ) {
    this.onTranscript = onTranscript;
    this.onAssistantText = onAssistantText;
    this.systemPrompt = systemPrompt || `You are Ally, a Citizens Advice assistant helping UK residents with benefits, housing, employment, consumer rights, and debt. Keep responses concise and helpful. Speak naturally as in a phone conversation.`;
  }

  static isAvailable(): boolean {
    return !!VOICE_WS_URL;
  }

  async start(): Promise<void> {
    if (!VOICE_WS_URL) throw new Error('Voice WebSocket URL not configured');
    
    const session = await fetchAuthSession({ forceRefresh: true });
    const token = session.tokens?.accessToken?.toString();
    if (!token) throw new Error('No auth token');

    this.audioContext = new AudioContext({ sampleRate: INPUT_SAMPLE_RATE });
    this.mediaStream = await navigator.mediaDevices.getUserMedia({ 
      audio: { sampleRate: INPUT_SAMPLE_RATE, channelCount: 1, echoCancellation: true } 
    });

    const source = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
    
    // Connect to WebSocket
    this.ws = new WebSocket(`${VOICE_WS_URL}?token=${token}`);
    this.ws.binaryType = 'arraybuffer';
    
    await new Promise<void>((resolve, reject) => {
      if (!this.ws) return reject('No WebSocket');
      this.ws.onopen = () => resolve();
      this.ws.onerror = () => reject('WebSocket connection failed');
      setTimeout(() => reject('WebSocket timeout'), 10000);
    });

    this.ws.onmessage = (event) => this.handleMessage(event);
    this.ws.onclose = () => this.stop();
    
    this.isActive = true;
    
    // Start session
    this.sendSessionStart();
    
    // Connect audio pipeline
    source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);

    this.processor.onaudioprocess = (e) => {
      if (!this.isActive) return;
      const inputData = e.inputBuffer.getChannelData(0);
      this.sendAudioChunk(inputData);
    };
  }

  private sendSessionStart(): void {
    this.sendEvent({
      event: {
        sessionStart: {
          inferenceConfiguration: { maxTokens: 1024, topP: 0.9, temperature: 0.7 }
        }
      }
    });

    this.sendEvent({
      event: {
        promptStart: {
          promptName: this.promptName,
          textOutputConfiguration: { mediaType: 'text/plain' },
          audioOutputConfiguration: {
            mediaType: 'audio/lpcm',
            sampleRateHertz: OUTPUT_SAMPLE_RATE,
            sampleSizeBits: 16,
            channelCount: 1,
            voiceId: 'tiffany',
            encoding: 'base64',
            audioType: 'SPEECH'
          }
        }
      }
    });

    // System prompt
    this.sendEvent({
      event: {
        contentStart: {
          promptName: this.promptName,
          contentName: this.contentName,
          type: 'TEXT',
          interactive: true,
          role: 'SYSTEM',
          textInputConfiguration: { mediaType: 'text/plain' }
        }
      }
    });

    this.sendEvent({
      event: {
        textInput: {
          promptName: this.promptName,
          contentName: this.contentName,
          content: this.systemPrompt
        }
      }
    });

    this.sendEvent({
      event: {
        contentEnd: {
          promptName: this.promptName,
          contentName: this.contentName
        }
      }
    });

    // Start audio input
    this.sendEvent({
      event: {
        contentStart: {
          promptName: this.promptName,
          contentName: this.audioContentName,
          type: 'AUDIO',
          interactive: true,
          role: 'USER',
          audioInputConfiguration: {
            mediaType: 'audio/lpcm',
            sampleRateHertz: INPUT_SAMPLE_RATE,
            sampleSizeBits: 16,
            channelCount: 1,
            audioType: 'SPEECH',
            encoding: 'base64'
          }
        }
      }
    });
  }

  private sendEvent(event: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(event));
    }
  }

  private sendAudioChunk(float32Data: Float32Array): void {
    const int16Data = new Int16Array(float32Data.length);
    for (let i = 0; i < float32Data.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Data[i]));
      int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    const base64 = btoa(String.fromCharCode(...new Uint8Array(int16Data.buffer)));
    
    this.sendEvent({
      event: {
        audioInput: {
          promptName: this.promptName,
          contentName: this.audioContentName,
          content: base64
        }
      }
    });
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data);
      
      if (data.event?.textOutput) {
        const text = data.event.textOutput.content;
        const role = data.role || 'ASSISTANT';
        
        if (role === 'USER') {
          this.onTranscript(text, true);
        } else {
          this.onAssistantText(text, false);
        }
      }
      
      if (data.event?.audioOutput) {
        const audioBase64 = data.event.audioOutput.content;
        const audioBytes = Uint8Array.from(atob(audioBase64), c => c.charCodeAt(0));
        this.audioQueue.push(audioBytes.buffer);
        this.playNextAudio();
      }
    } catch (e) {
      console.error('Error handling message:', e);
    }
  }

  private async playNextAudio(): Promise<void> {
    if (this.isPlaying || this.audioQueue.length === 0) return;
    
    this.isPlaying = true;
    const audioData = this.audioQueue.shift()!;
    
    const playbackContext = new AudioContext({ sampleRate: OUTPUT_SAMPLE_RATE });
    const int16Array = new Int16Array(audioData);
    const float32Array = new Float32Array(int16Array.length);
    
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 0x8000;
    }
    
    const buffer = playbackContext.createBuffer(1, float32Array.length, OUTPUT_SAMPLE_RATE);
    buffer.copyToChannel(float32Array, 0);
    
    const source = playbackContext.createBufferSource();
    source.buffer = buffer;
    source.connect(playbackContext.destination);
    source.onended = () => {
      this.isPlaying = false;
      playbackContext.close();
      this.playNextAudio();
    };
    source.start();
  }

  stop(): void {
    this.isActive = false;
    
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendEvent({
        event: { contentEnd: { promptName: this.promptName, contentName: this.audioContentName } }
      });
      this.sendEvent({
        event: { promptEnd: { promptName: this.promptName } }
      });
      this.sendEvent({ event: { sessionEnd: {} } });
      this.ws.close();
    }
    
    this.processor?.disconnect();
    this.mediaStream?.getTracks().forEach(t => t.stop());
    this.audioContext?.close();
    
    this.ws = null;
    this.processor = null;
    this.mediaStream = null;
    this.audioContext = null;
  }
}

// Simpler speech-to-text only using Web Speech API (works without backend)
export class BrowserSpeechRecognition {
  private recognition: any | null = null;
  private onResult: (text: string, isFinal: boolean) => void;
  private isListening = false;

  constructor(onResult: (text: string, isFinal: boolean) => void) {
    this.onResult = onResult;
    
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-GB';
      
      this.recognition.onresult = (event: any) => {
        const result = event.results[event.results.length - 1];
        this.onResult(result[0].transcript, result.isFinal);
      };
      
      this.recognition.onerror = (e: any) => {
        console.error('Speech recognition error:', e.error);
        if (e.error === 'not-allowed') {
          alert('Microphone access denied. Please allow microphone access in your browser settings.');
        }
      };
      this.recognition.onend = () => { 
        if (this.isListening) {
          try {
            this.recognition?.start();
          } catch (err) {
            console.error('Failed to restart recognition:', err);
            this.isListening = false;
          }
        }
      };
    }
  }

  start(): void {
    if (!this.recognition) throw new Error('Speech recognition not supported');
    this.isListening = true;
    try {
      this.recognition.start();
    } catch (err) {
      console.error('Failed to start recognition:', err);
      this.isListening = false;
    }
  }

  stop(): void {
    this.isListening = false;
    this.recognition?.stop();
  }

  isSupported(): boolean {
    return !!this.recognition;
  }
}

// Text-to-speech using Web Speech API
export const speak = (text: string, onEnd?: () => void): void => {
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-GB';
  utterance.rate = 1.0;
  
  // Select a British female voice
  const voices = speechSynthesis.getVoices();
  const britishFemaleVoice = voices.find(voice => 
    voice.lang === 'en-GB' && voice.name.toLowerCase().includes('female')
  ) || voices.find(voice => 
    voice.lang === 'en-GB' && (voice.name.includes('Google UK English Female') || voice.name.includes('Fiona') || voice.name.includes('Kate'))
  ) || voices.find(voice => 
    voice.lang === 'en-GB'
  );
  
  if (britishFemaleVoice) {
    utterance.voice = britishFemaleVoice;
  }
  
  if (onEnd) utterance.onend = onEnd;
  speechSynthesis.speak(utterance);
};

export const stopSpeaking = (): void => {
  speechSynthesis.cancel();
};
