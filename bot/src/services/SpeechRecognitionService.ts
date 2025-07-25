import OpenAI from 'openai';
import { SpeechRecognitionResult } from '../domain/types';
import { logger } from './logger';
import { createReadStream, unlinkSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

export class SpeechRecognitionService {
  private openai: OpenAI | null = null;
  private isEnabled: boolean;
  private costSummaryInterval: NodeJS.Timeout | null = null;
  private costAlertThresholds = {
    daily: 10.00,    // Alert at $10/day
    hourly: 1.00,    // Alert at $1/hour
    total: 50.00     // Alert at $50 total
  };
  private lastAlertTime = 0;
  private costTracker = {
    totalRequests: 0,
    totalMinutesProcessed: 0,
    estimatedCost: 0,
    lastRequestTime: 0,
    successfulTranscriptions: 0,
    failedTranscriptions: 0,
    totalResponseTimeMs: 0,
    sessionStartTime: Date.now()
  };

  constructor() {
    const apiKey = process.env.OPENAI_API_KEY;
    this.isEnabled = !!apiKey;
    
    if (this.isEnabled) {
      this.openai = new OpenAI({
        apiKey: apiKey
      });
      logger.info('[SpeechRecognitionService] 💰 OpenAI Whisper API enabled - will track costs');
      logger.info(`[SpeechRecognitionService] Session started at ${new Date().toISOString()}`);
      logger.info(`[SpeechRecognitionService] Whisper API pricing: $0.006/minute`);
      
      // Set up periodic cost summary logging (every 30 minutes)
      this.costSummaryInterval = setInterval(() => {
        if (this.costTracker.totalRequests > 0) {
          logger.info('[SpeechRecognitionService] 📊 === PERIODIC COST REPORT ===');
          this.logCostSummary();
        }
      }, 30 * 60 * 1000); // 30 minutes
      
    } else {
      logger.warn('[SpeechRecognitionService] ⚠️ OpenAI API key not provided. Speech recognition will be disabled.');
    }
  }

  async transcribeAudio(audioBuffer: Buffer, language: string = 'en'): Promise<SpeechRecognitionResult> {
    if (!this.isEnabled || !this.openai) {
      logger.error('[SpeechRecognitionService] ❌ Attempted to transcribe but service is disabled');
      throw new Error('Speech recognition is disabled. OpenAI API key not configured.');
    }

    const startTime = Date.now();
    const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(7)}`;
    
    try {
      // COST TRACKING: Calculate audio duration for cost estimation
      const audioDurationMinutes = audioBuffer.length / (48000 * 2 * 2 * 60); // 48kHz stereo 16-bit
      const estimatedCost = audioDurationMinutes * 0.006; // $0.006 per minute
      
      logger.info(`[SpeechRecognitionService] 💰 === WHISPER API CALL START === [${requestId}]`);
      logger.info(`[SpeechRecognitionService] 💰 Audio size: ${(audioBuffer.length / 1024 / 1024).toFixed(2)}MB`);
      logger.info(`[SpeechRecognitionService] 💰 Duration: ${audioDurationMinutes.toFixed(2)} minutes`);
      logger.info(`[SpeechRecognitionService] 💰 Estimated cost: $${estimatedCost.toFixed(4)}`);
      logger.info(`[SpeechRecognitionService] 💰 Language: ${language}`);

      // Create temporary file for audio data
      const tempFilePath = join(tmpdir(), `voice_${Date.now()}.wav`);
      writeFileSync(tempFilePath, audioBuffer);
      logger.debug(`[SpeechRecognitionService] Temp file created: ${tempFilePath}`);

      // Transcribe using OpenAI Whisper
      logger.info(`[SpeechRecognitionService] 🔄 Calling Whisper API... [${requestId}]`);
      const apiCallStart = Date.now();
      
      const transcription = await this.openai.audio.transcriptions.create({
        file: createReadStream(tempFilePath),
        model: 'whisper-1',
        language: language,
        response_format: 'verbose_json',
        temperature: 0.0
      });

      const apiResponseTime = Date.now() - apiCallStart;
      logger.info(`[SpeechRecognitionService] 📡 API response received in ${apiResponseTime}ms [${requestId}]`);

      // Clean up temporary file
      unlinkSync(tempFilePath);
      logger.debug(`[SpeechRecognitionService] Temp file cleaned up: ${tempFilePath}`);

      const processingTime = Date.now() - startTime;
      
      // Update cost tracking
      this.costTracker.totalRequests++;
      this.costTracker.successfulTranscriptions++;
      this.costTracker.totalMinutesProcessed += audioDurationMinutes;
      this.costTracker.estimatedCost += estimatedCost;
      this.costTracker.lastRequestTime = Date.now();
      this.costTracker.totalResponseTimeMs += processingTime;
      
      // Log detailed transcription results
      const segments = (transcription as any).segments || [];
      const avgLogprob = segments.length > 0 
        ? segments.reduce((sum: number, seg: any) => sum + (seg.avg_logprob || 0), 0) / segments.length 
        : 0;
      const estimatedConfidence = Math.min(0.99, Math.max(0.1, 0.95 + (avgLogprob * 0.1))); // Convert logprob to confidence
      
      const result: SpeechRecognitionResult = {
        text: transcription.text,
        confidence: estimatedConfidence,
        isPartial: false,
        language: transcription.language || language,
        processingTimeMs: processingTime,
        alternatives: [] // Whisper doesn't provide alternatives in this format
      };

      logger.info(`[SpeechRecognitionService] ✅ === TRANSCRIPTION SUCCESS === [${requestId}]`);
      logger.info(`[SpeechRecognitionService] ✅ Text: "${result.text}"`);
      logger.info(`[SpeechRecognitionService] ✅ Confidence: ${(result.confidence * 100).toFixed(1)}%`);
      logger.info(`[SpeechRecognitionService] ✅ Detected language: ${result.language}`);
      logger.info(`[SpeechRecognitionService] ✅ Processing time: ${processingTime}ms (API: ${apiResponseTime}ms)`);
      logger.info(`[SpeechRecognitionService] ✅ Cost: $${estimatedCost.toFixed(4)}`);
      logger.info(`[SpeechRecognitionService] 💰 Running total: $${this.costTracker.estimatedCost.toFixed(4)} (${this.costTracker.totalRequests} requests)`);
      
      // Check cost alerts
      this.checkCostAlerts();
      
      return result;

    } catch (error) {
      const processingTime = Date.now() - startTime;
      
      // Update failure tracking
      this.costTracker.totalRequests++;
      this.costTracker.failedTranscriptions++;
      this.costTracker.totalResponseTimeMs += processingTime;
      
      // Still charge for failed requests as OpenAI charges for them
      const audioDurationMinutes = audioBuffer.length / (48000 * 2 * 2 * 60);
      const estimatedCost = audioDurationMinutes * 0.006;
      this.costTracker.totalMinutesProcessed += audioDurationMinutes;
      this.costTracker.estimatedCost += estimatedCost;
      this.costTracker.lastRequestTime = Date.now();
      
      logger.error(`[SpeechRecognitionService] ❌ === TRANSCRIPTION FAILED === [${requestId}]`);
      logger.error(`[SpeechRecognitionService] ❌ Error type: ${error instanceof Error ? error.constructor.name : 'Unknown'}`);
      logger.error(`[SpeechRecognitionService] ❌ Error message: ${error instanceof Error ? error.message : String(error)}`);
      if (error instanceof Error && error.stack) {
        logger.error(`[SpeechRecognitionService] ❌ Stack trace:\n${error.stack}`);
      }
      logger.error(`[SpeechRecognitionService] ❌ Failed after: ${processingTime}ms`);
      logger.error(`[SpeechRecognitionService] ❌ Cost incurred: $${estimatedCost.toFixed(4)} (API charges even for failures)`);
      logger.error(`[SpeechRecognitionService] 💰 Running total: $${this.costTracker.estimatedCost.toFixed(4)} (${this.costTracker.failedTranscriptions} failures)`);
      
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
    
    logger.info(`[SpeechRecognitionService] 🎯 Parsing command from: "${transcriptionText}"`);
    
    // Remove wake word if present
    const cleanText = text.replace(/^kanye\s+/i, '');
    logger.debug(`[SpeechRecognitionService] Clean text after wake word removal: "${cleanText}"`);
    
    let result: { command: string; parameters: string[] };
    
    // Parse common music commands
    if (cleanText.startsWith('play ')) {
      result = {
        command: 'play',
        parameters: [cleanText.substring(5).trim()]
      };
    } else if (cleanText.includes('skip') || cleanText.includes('next')) {
      result = {
        command: 'skip',
        parameters: []
      };
    } else if (cleanText.includes('stop') || cleanText.includes('quit')) {
      result = {
        command: 'stop',
        parameters: []
      };
    } else if (cleanText.includes('pause')) {
      result = {
        command: 'pause',
        parameters: []
      };
    } else if (cleanText.includes('resume') || cleanText.includes('continue')) {
      result = {
        command: 'resume',
        parameters: []
      };
    } else if (cleanText.includes('queue') || cleanText.includes('what\'s playing')) {
      result = {
        command: 'queue',
        parameters: []
      };
    } else {
      // Default fallback - treat as search query
      result = {
        command: 'play',
        parameters: [cleanText]
      };
    }
    
    logger.info(`[SpeechRecognitionService] 🎯 Parsed command: ${result.command}${result.parameters.length > 0 ? ` with params: ["${result.parameters.join('", "')}"]` : ' (no params)'}`);
    
    return result;
  }

  // Cost tracking and monitoring methods
  getCostStats(): {
    totalRequests: number;
    totalMinutesProcessed: number;
    estimatedCost: number;
    averageCostPerRequest: number;
    lastRequestTime: number;
    successfulTranscriptions: number;
    failedTranscriptions: number;
    successRate: number;
    averageResponseTimeMs: number;
    sessionDurationMinutes: number;
  } {
    const sessionDurationMs = Date.now() - this.costTracker.sessionStartTime;
    const sessionDurationMinutes = sessionDurationMs / (1000 * 60);
    
    return {
      ...this.costTracker,
      averageCostPerRequest: this.costTracker.totalRequests > 0 
        ? this.costTracker.estimatedCost / this.costTracker.totalRequests 
        : 0,
      successRate: this.costTracker.totalRequests > 0
        ? (this.costTracker.successfulTranscriptions / this.costTracker.totalRequests) * 100
        : 0,
      averageResponseTimeMs: this.costTracker.totalRequests > 0
        ? this.costTracker.totalResponseTimeMs / this.costTracker.totalRequests
        : 0,
      sessionDurationMinutes
    };
  }

  resetCostTracking(): void {
    const previousStats = this.getCostStats();
    
    this.costTracker = {
      totalRequests: 0,
      totalMinutesProcessed: 0,
      estimatedCost: 0,
      lastRequestTime: 0,
      successfulTranscriptions: 0,
      failedTranscriptions: 0,
      totalResponseTimeMs: 0,
      sessionStartTime: Date.now()
    };
    
    logger.info('[SpeechRecognitionService] 🔄 === COST TRACKING RESET ===');
    logger.info(`[SpeechRecognitionService] 🔄 Previous session stats:`);
    logger.info(`[SpeechRecognitionService] 🔄   - Total cost: $${previousStats.estimatedCost.toFixed(4)}`);
    logger.info(`[SpeechRecognitionService] 🔄   - Requests: ${previousStats.totalRequests} (${previousStats.successfulTranscriptions} ✅, ${previousStats.failedTranscriptions} ❌)`);
    logger.info(`[SpeechRecognitionService] 🔄   - Success rate: ${previousStats.successRate.toFixed(1)}%`);
    logger.info(`[SpeechRecognitionService] 🔄   - Session duration: ${previousStats.sessionDurationMinutes.toFixed(1)} minutes`);
    logger.info(`[SpeechRecognitionService] 🔄 New session started at ${new Date().toISOString()}`);
  }

  logCostSummary(): void {
    const stats = this.getCostStats();
    
    logger.info('[SpeechRecognitionService] 💰 === WHISPER API COST SUMMARY ===');
    logger.info(`[SpeechRecognitionService] 💰 Session Duration: ${stats.sessionDurationMinutes.toFixed(1)} minutes`);
    logger.info(`[SpeechRecognitionService] 💰 Total Requests: ${stats.totalRequests}`);
    logger.info(`[SpeechRecognitionService] 💰   - Successful: ${stats.successfulTranscriptions} ✅`);
    logger.info(`[SpeechRecognitionService] 💰   - Failed: ${stats.failedTranscriptions} ❌`);
    logger.info(`[SpeechRecognitionService] 💰   - Success Rate: ${stats.successRate.toFixed(1)}%`);
    logger.info(`[SpeechRecognitionService] 💰 Audio Processed: ${stats.totalMinutesProcessed.toFixed(2)} minutes`);
    logger.info(`[SpeechRecognitionService] 💰 Total Cost: $${stats.estimatedCost.toFixed(4)}`);
    logger.info(`[SpeechRecognitionService] 💰 Average Cost/Request: $${stats.averageCostPerRequest.toFixed(4)}`);
    logger.info(`[SpeechRecognitionService] 💰 Average Response Time: ${stats.averageResponseTimeMs.toFixed(0)}ms`);
    
    if (stats.lastRequestTime > 0) {
      logger.info(`[SpeechRecognitionService] 💰 Last Request: ${new Date(stats.lastRequestTime).toISOString()}`);
    }
    
    // Cost projection
    if (stats.sessionDurationMinutes > 0 && stats.totalRequests > 0) {
      const requestsPerHour = (stats.totalRequests / stats.sessionDurationMinutes) * 60;
      const costPerHour = (stats.estimatedCost / stats.sessionDurationMinutes) * 60;
      logger.info(`[SpeechRecognitionService] 💰 Current Rate: ${requestsPerHour.toFixed(1)} requests/hour = $${costPerHour.toFixed(2)}/hour`);
      logger.info(`[SpeechRecognitionService] 💰 Projected Daily Cost (24h): $${(costPerHour * 24).toFixed(2)}`);
      logger.info(`[SpeechRecognitionService] 💰 Projected Monthly Cost (30d): $${(costPerHour * 24 * 30).toFixed(2)}`);
    }
    
    logger.info('[SpeechRecognitionService] 💰 ================================');
  }

  // Cleanup method to stop periodic logging
  cleanup(): void {
    if (this.costSummaryInterval) {
      clearInterval(this.costSummaryInterval);
      this.costSummaryInterval = null;
      logger.info('[SpeechRecognitionService] 🧹 Cleaned up periodic cost reporting');
    }
    
    // Log final cost summary
    if (this.costTracker.totalRequests > 0) {
      logger.info('[SpeechRecognitionService] 📊 === FINAL COST REPORT (Service Shutdown) ===');
      this.logCostSummary();
    }
  }

  private checkCostAlerts(): void {
    const now = Date.now();
    const timeSinceLastAlert = now - this.lastAlertTime;
    
    // Only alert once per hour max
    if (timeSinceLastAlert < 60 * 60 * 1000) {
      return;
    }
    
    const stats = this.getCostStats();
    
    // Check total cost threshold
    if (stats.estimatedCost >= this.costAlertThresholds.total) {
      logger.warn(`[SpeechRecognitionService] 🚨 COST ALERT: Total cost ($${stats.estimatedCost.toFixed(2)}) exceeds threshold ($${this.costAlertThresholds.total})!`);
      this.lastAlertTime = now;
      return;
    }
    
    // Check hourly rate
    if (stats.sessionDurationMinutes > 60) {
      const costPerHour = (stats.estimatedCost / stats.sessionDurationMinutes) * 60;
      if (costPerHour >= this.costAlertThresholds.hourly) {
        logger.warn(`[SpeechRecognitionService] 🚨 COST ALERT: Hourly rate ($${costPerHour.toFixed(2)}/hour) exceeds threshold ($${this.costAlertThresholds.hourly}/hour)!`);
        this.lastAlertTime = now;
        return;
      }
    }
    
    // Check projected daily cost
    if (stats.sessionDurationMinutes > 30 && stats.totalRequests > 0) {
      const requestsPerHour = (stats.totalRequests / stats.sessionDurationMinutes) * 60;
      const costPerHour = (stats.estimatedCost / stats.sessionDurationMinutes) * 60;
      const projectedDailyCost = costPerHour * 24;
      
      if (projectedDailyCost >= this.costAlertThresholds.daily) {
        logger.warn(`[SpeechRecognitionService] 🚨 COST ALERT: Projected daily cost ($${projectedDailyCost.toFixed(2)}) exceeds threshold ($${this.costAlertThresholds.daily})!`);
        logger.warn(`[SpeechRecognitionService] 🚨 Current rate: ${requestsPerHour.toFixed(1)} requests/hour`);
        this.lastAlertTime = now;
      }
    }
  }
}