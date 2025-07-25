import OpenAI from 'openai';
import { SpeechRecognitionResult } from '../domain/types';
import { logger } from './logger';
import { createReadStream, unlinkSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

export class SpeechRecognitionService {
  private openai: OpenAI | null = null;
  private isEnabled: boolean;
  private costTracker = {
    totalRequests: 0,
    totalMinutesProcessed: 0,
    estimatedCost: 0,
    lastRequestTime: 0
  };

  constructor() {
    const apiKey = process.env.OPENAI_API_KEY;
    this.isEnabled = !!apiKey;
    
    if (this.isEnabled) {
      this.openai = new OpenAI({
        apiKey: apiKey
      });
      logger.info('[SpeechRecognitionService] 💰 OpenAI Whisper API enabled - will track costs');
    } else {
      logger.warn('OpenAI API key not provided. Speech recognition will be disabled.');
    }
  }

  async transcribeAudio(audioBuffer: Buffer, language: string = 'en'): Promise<SpeechRecognitionResult> {
    if (!this.isEnabled || !this.openai) {
      throw new Error('Speech recognition is disabled. OpenAI API key not configured.');
    }

    const startTime = Date.now();
    
    try {
      // COST TRACKING: Calculate audio duration for cost estimation
      const audioDurationMinutes = audioBuffer.length / (48000 * 2 * 2 * 60); // 48kHz stereo 16-bit
      const estimatedCost = audioDurationMinutes * 0.006; // $0.006 per minute
      
      logger.info(`[SpeechRecognitionService] 🚨 PROCESSING WITH WHISPER API - Duration: ${audioDurationMinutes.toFixed(2)}min, Est. Cost: $${estimatedCost.toFixed(4)}`);

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
      
      // Update cost tracking
      this.costTracker.totalRequests++;
      this.costTracker.totalMinutesProcessed += audioDurationMinutes;
      this.costTracker.estimatedCost += estimatedCost;
      this.costTracker.lastRequestTime = Date.now();
      
      const result: SpeechRecognitionResult = {
        text: transcription.text,
        confidence: 0.95, // Whisper doesn't provide confidence scores, using high default
        isPartial: false,
        language: transcription.language || language,
        processingTimeMs: processingTime,
        alternatives: [] // Whisper doesn't provide alternatives in this format
      };

      logger.info(`[SpeechRecognitionService] ✅ SUCCESS: "${result.text}" in ${processingTime}ms | Total Cost So Far: $${this.costTracker.estimatedCost.toFixed(4)}`);
      return result;

    } catch (error) {
      const processingTime = Date.now() - startTime;
      logger.error('[SpeechRecognitionService] ❌ TRANSCRIPTION FAILED (cost still incurred):', error);
      
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

  // Cost tracking and monitoring methods
  getCostStats(): {
    totalRequests: number;
    totalMinutesProcessed: number;
    estimatedCost: number;
    averageCostPerRequest: number;
    lastRequestTime: number;
  } {
    return {
      ...this.costTracker,
      averageCostPerRequest: this.costTracker.totalRequests > 0 
        ? this.costTracker.estimatedCost / this.costTracker.totalRequests 
        : 0
    };
  }

  resetCostTracking(): void {
    this.costTracker = {
      totalRequests: 0,
      totalMinutesProcessed: 0,
      estimatedCost: 0,
      lastRequestTime: 0
    };
    logger.info('[SpeechRecognitionService] Cost tracking reset');
  }

  logCostSummary(): void {
    const stats = this.getCostStats();
    logger.info(`[SpeechRecognitionService] 💰 COST SUMMARY:
      - Total Requests: ${stats.totalRequests}
      - Total Minutes: ${stats.totalMinutesProcessed.toFixed(2)}
      - Estimated Cost: $${stats.estimatedCost.toFixed(4)}
      - Avg Cost/Request: $${stats.averageCostPerRequest.toFixed(4)}
      - Last Request: ${new Date(stats.lastRequestTime).toISOString()}`);
  }
}