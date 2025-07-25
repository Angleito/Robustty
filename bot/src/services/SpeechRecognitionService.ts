import OpenAI from 'openai';
import { SpeechRecognitionResult } from '../domain/types';
import { logger } from './logger';
import { createReadStream, unlinkSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

export class SpeechRecognitionService {
  private openai: OpenAI;
  private isEnabled: boolean;

  constructor() {
    const apiKey = process.env.OPENAI_API_KEY;
    this.isEnabled = !!apiKey;
    
    if (this.isEnabled) {
      this.openai = new OpenAI({
        apiKey: apiKey
      });
    } else {
      logger.warn('OpenAI API key not provided. Speech recognition will be disabled.');
    }
  }

  async transcribeAudio(audioBuffer: Buffer, language: string = 'en'): Promise<SpeechRecognitionResult> {
    if (!this.isEnabled) {
      throw new Error('Speech recognition is disabled. OpenAI API key not configured.');
    }

    const startTime = Date.now();
    
    try {
      // Create temporary file for audio data
      const tempFilePath = join(tmpdir(), `voice_${Date.now()}.wav`);
      writeFileSync(tempFilePath, audioBuffer);

      // Transcribe using OpenAI Whisper
      const transcription = await this.openai.audio.transcriptions.create({
        file: createReadStream(tempFilePath),
        model: 'whisper-1',
        language: language,
        response_format: 'verbose_json',
        temperature: 0.0
      });

      // Clean up temporary file
      unlinkSync(tempFilePath);

      const processingTime = Date.now() - startTime;
      
      const result: SpeechRecognitionResult = {
        text: transcription.text,
        confidence: 0.95, // Whisper doesn't provide confidence scores, using high default
        isPartial: false,
        language: transcription.language || language,
        processingTimeMs: processingTime,
        alternatives: [] // Whisper doesn't provide alternatives in this format
      };

      logger.info(`[SpeechRecognitionService] Transcribed "${result.text}" in ${processingTime}ms`);
      return result;

    } catch (error) {
      const processingTime = Date.now() - startTime;
      logger.error('[SpeechRecognitionService] Transcription failed:', error);
      
      return {
        text: '',
        confidence: 0,
        isPartial: false,
        language: language,
        processingTimeMs: processingTime,
        alternatives: []
      };
    }
  }

  async transcribeAudioStream(audioBuffer: Buffer): Promise<SpeechRecognitionResult> {
    return this.transcribeAudio(audioBuffer);
  }

  isServiceEnabled(): boolean {
    return this.isEnabled;
  }

  parseVoiceCommand(transcriptionText: string): { command: string; parameters: string[] } {
    const text = transcriptionText.toLowerCase().trim();
    
    // Remove wake word if present
    const cleanText = text.replace(/^kanye\s+/i, '');
    
    // Parse common music commands
    if (cleanText.startsWith('play ')) {
      return {
        command: 'play',
        parameters: [cleanText.substring(5).trim()]
      };
    }
    
    if (cleanText.includes('skip') || cleanText.includes('next')) {
      return {
        command: 'skip',
        parameters: []
      };
    }
    
    if (cleanText.includes('stop') || cleanText.includes('quit')) {
      return {
        command: 'stop',
        parameters: []
      };
    }
    
    if (cleanText.includes('pause')) {
      return {
        command: 'pause',
        parameters: []
      };
    }
    
    if (cleanText.includes('resume') || cleanText.includes('continue')) {
      return {
        command: 'resume',
        parameters: []
      };
    }

    if (cleanText.includes('queue') || cleanText.includes('what\'s playing')) {
      return {
        command: 'queue',
        parameters: []
      };
    }
    
    // Default fallback - treat as search query
    return {
      command: 'play',
      parameters: [cleanText]
    };
  }
}