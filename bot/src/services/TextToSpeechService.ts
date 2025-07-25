import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';
import { Readable } from 'stream';
import { logger } from './logger';

export interface TTSConfig {
  apiKey?: string;
  voiceId?: string;
  modelId?: string;
  enabled?: boolean;
}

export class TextToSpeechService {
  private client: ElevenLabsClient | null = null;
  private voiceId: string;
  private modelId: string;
  private enabled: boolean;

  constructor(config: TTSConfig = {}) {
    this.enabled = config.enabled ?? process.env.TTS_ENABLED === 'true';
    this.voiceId = config.voiceId ?? process.env.ELEVENLABS_VOICE_ID ?? 'ErXwobaYiN019PkySvjV'; // Default voice
    this.modelId = config.modelId ?? process.env.ELEVENLABS_MODEL_ID ?? 'eleven_monolingual_v1';

    logger.info(`[TTS] Initializing TextToSpeechService - enabled from env: ${process.env.TTS_ENABLED}, enabled: ${this.enabled}`);
    logger.info(`[TTS] Voice ID: ${this.voiceId}, Model ID: ${this.modelId}`);

    if (this.enabled) {
      const apiKey = config.apiKey ?? process.env.ELEVENLABS_API_KEY;
      logger.info(`[TTS] API key provided: ${!!apiKey}`);
      
      if (!apiKey) {
        logger.error('[TTS] ElevenLabs API key not provided, TTS will be disabled');
        this.enabled = false;
      } else {
        try {
          this.client = new ElevenLabsClient({ apiKey });
          logger.info('[TTS] ✅ Text-to-Speech service initialized successfully with ElevenLabs');
        } catch (error) {
          logger.error('[TTS] Failed to initialize ElevenLabs client:', error);
          this.enabled = false;
        }
      }
    } else {
      logger.info('[TTS] ⚠️ Text-to-Speech service disabled by configuration');
    }
  }

  isEnabled(): boolean {
    const enabled = this.enabled && this.client !== null;
    logger.debug(`[TTS] isEnabled check - enabled: ${this.enabled}, has client: ${!!this.client}, result: ${enabled}`);
    return enabled;
  }

  async generateSpeech(text: string): Promise<Readable | null> {
    logger.info(`[TTS] generateSpeech called with text: "${text}"`);
    
    if (!this.isEnabled() || !this.client) {
      logger.error('[TTS] Service disabled or not initialized, skipping TTS generation');
      logger.error(`[TTS] Debug - isEnabled: ${this.isEnabled()}, client exists: ${!!this.client}`);
      return null;
    }

    try {
      logger.info(`[TTS] 🎤 Generating speech using ElevenLabs API...`);
      logger.info(`[TTS] Request params - voiceId: ${this.voiceId}, modelId: ${this.modelId}`);
      
      const audioStream = await this.client.textToSpeech.stream(
        this.voiceId,
        {
          modelId: this.modelId,
          text,
          voiceSettings: {
            stability: 0.75,
            similarityBoost: 0.85,
            style: 0.5,
            useSpeakerBoost: true
          }
        }
      );
      
      logger.info('[TTS] ElevenLabs API call successful, received audio stream');

      // Convert the async generator to a Node.js Readable stream
      const readable = Readable.from(audioStream);
      
      logger.info('[TTS] ✅ Speech generation successful, returning audio stream');
      return readable;
    } catch (error) {
      logger.error('[TTS] ❌ Failed to generate speech:', error);
      logger.error('[TTS] Error details:', error instanceof Error ? error.stack : 'Unknown error');
      
      // Log additional debugging info
      if (error instanceof Error && error.message.includes('401')) {
        logger.error('[TTS] Authentication error - check your ElevenLabs API key');
      } else if (error instanceof Error && error.message.includes('voice')) {
        logger.error('[TTS] Voice error - check if voice ID is valid');
      }
      
      return null;
    }
  }

  async preloadVoice(): Promise<void> {
    if (!this.isEnabled() || !this.client) return;

    try {
      // Test the voice with a short phrase to ensure it's working
      await this.generateSpeech('Test');
      logger.info('[TTS] Voice preloaded successfully');
    } catch (error) {
      logger.error('[TTS] Failed to preload voice:', error);
    }
  }

  // Get available voices (useful for configuration)
  async getAvailableVoices(): Promise<any[]> {
    if (!this.isEnabled() || !this.client) return [];

    try {
      const voices = await this.client.voices.getAll();
      return voices.voices;
    } catch (error) {
      logger.error('[TTS] Failed to get available voices:', error);
      return [];
    }
  }

  setVoice(voiceId: string): void {
    this.voiceId = voiceId;
    logger.info(`[TTS] Voice changed to: ${voiceId}`);
  }

  setEnabled(enabled: boolean): void {
    if (enabled && !this.client && process.env.ELEVENLABS_API_KEY) {
      this.client = new ElevenLabsClient({ apiKey: process.env.ELEVENLABS_API_KEY });
    }
    this.enabled = enabled && this.client !== null;
    logger.info(`[TTS] Service ${this.enabled ? 'enabled' : 'disabled'}`);
  }
}