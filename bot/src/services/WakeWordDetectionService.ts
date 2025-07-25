import { WakeWordResult } from '../domain/types';
import { logger } from './logger';
import { AudioProcessingService } from './AudioProcessingService';

interface AudioPattern {
  pattern: number[];
  threshold: number;
  minLength: number;
  maxLength: number;
}

export class WakeWordDetectionService {
  private wakeWordPatterns: Map<string, AudioPattern[]>;
  private confidenceThreshold: number;
  private readonly sampleRate: number;
  private processingEnabled: boolean = true;
  private costOptimizationMode: boolean = true; // Enable aggressive cost optimization

  constructor(confidenceThreshold: number = 0.6, sampleRate: number = 48000) { // Lower threshold for better detection
    this.confidenceThreshold = confidenceThreshold;
    this.sampleRate = sampleRate;
    this.wakeWordPatterns = new Map();
    
    logger.info(`[WakeWordDetectionService] 🚀 Starting initialization...`, {
      confidenceThreshold,
      sampleRate,
      costOptimizationMode: this.costOptimizationMode
    });
    
    // Initialize "Kanye" detection patterns
    this.initializeKanyePatterns();
    
    logger.info('[WakeWordDetectionService] ✅ Initialized in COST OPTIMIZATION mode - only processing after wake word detection', {
      supportedKeywords: this.getSupportedKeywords(),
      processingEnabled: this.processingEnabled
    });
  }

  private initializeKanyePatterns(): void {
    // Simplified audio pattern matching for "Kanye" 
    // These patterns represent approximate audio fingerprints
    const kanyePatterns: AudioPattern[] = [
      {
        // Pattern for "KAN" sound (plosive K + vowel AN)
        pattern: [0.1, 0.8, 0.9, 0.7, 0.4], 
        threshold: 0.6,
        minLength: 100, // ~2ms at 48kHz
        maxLength: 400  // ~8ms at 48kHz
      },
      {
        // Pattern for "YE" sound (consonant Y + vowel E)
        pattern: [0.3, 0.6, 0.8, 0.5, 0.2],
        threshold: 0.6,
        minLength: 150, // ~3ms at 48kHz
        maxLength: 500  // ~10ms at 48kHz
      }
    ];

    this.wakeWordPatterns.set('kanye', kanyePatterns);
    logger.info('[WakeWordDetectionService] Initialized with Kanye detection patterns');
  }

  async detectWakeWord(audioBuffer: Buffer, keyword: string = 'kanye'): Promise<WakeWordResult> {
    if (!this.processingEnabled) {
      return this.createNegativeResult(keyword, Date.now());
    }

    const startTime = Date.now();
    
    try {
      // COST OPTIMIZATION: Quick early exits to minimize processing
      
      // 1. Check minimum audio length (skip very short segments)
      if (audioBuffer.length < 3200) { // Less than ~67ms at 48kHz stereo
        return this.createNegativeResult(keyword, startTime);
      }

      // 2. Fast energy check before any processing
      const rawAudioLevel = AudioProcessingService.calculateAudioLevel(audioBuffer);
      if (rawAudioLevel < 0.03) { // Very quiet audio, likely silence
        return this.createNegativeResult(keyword, startTime);
      }

      // 3. Only preprocess if we pass initial energy check
      const processedAudio = this.costOptimizedPreprocessing(audioBuffer);
      
      // 4. Secondary energy check on processed audio
      const processedAudioLevel = AudioProcessingService.calculateAudioLevel(processedAudio);
      if (processedAudioLevel < 0.05) {
        return this.createNegativeResult(keyword, startTime);
      }

      const patterns = this.wakeWordPatterns.get(keyword.toLowerCase());
      if (!patterns) {
        logger.warn(`[WakeWordDetectionService] No patterns found for keyword: ${keyword}`);
        return this.createNegativeResult(keyword, startTime);
      }

      // 5. Lightweight pattern analysis optimized for speed
      const result = this.fastAnalyzeAudioPatterns(processedAudio, patterns, keyword);
      
      const processingTime = Date.now() - startTime;
      
      if (result.detected) {
        logger.info(`[WakeWordDetectionService] 🎯 WAKE WORD DETECTED! "${keyword}" in ${processingTime}ms (confidence: ${result.confidence.toFixed(3)})`);
      } else {
        logger.debug(`[WakeWordDetectionService] No wake word in ${processingTime}ms (max confidence: ${result.confidence.toFixed(3)})`);
      }
      
      return result;

    } catch (error) {
      logger.error('[WakeWordDetectionService] Error detecting wake word:', error);
      return this.createNegativeResult(keyword, startTime);
    }
  }

  // Lightweight preprocessing optimized for cost
  private costOptimizedPreprocessing(audioBuffer: Buffer): Buffer {
    if (!this.costOptimizationMode) {
      return this.preprocessAudio(audioBuffer);
    }

    // Minimal preprocessing for cost optimization
    // Skip noise reduction, only do basic normalization
    return AudioProcessingService.normalizeAudioLevel(audioBuffer, 0.6);
  }

  // Fast pattern analysis optimized for speed over accuracy
  private fastAnalyzeAudioPatterns(audioBuffer: Buffer, patterns: AudioPattern[], keyword: string): WakeWordResult {
    const samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
    let bestMatch = 0;
    let matchStart = 0;
    let matchEnd = 0;

    // Use larger windows and skip samples for faster processing
    const windowSize = 512; // Larger window for speed
    const skipSamples = 256; // Skip samples to process faster
    
    const energyEnvelope = this.fastEnergyEnvelope(samples, windowSize, skipSamples);
    
    if (energyEnvelope.length < 10) { // Too short to contain wake word
      return this.createNegativeResult(keyword, 0);
    }

    // Only check the most distinctive patterns first
    const primaryPattern = patterns[0]; // Use primary pattern only for speed
    
    for (let i = 0; i < energyEnvelope.length - 20; i += 2) { // Skip every other position
      const windowLength = Math.min(25, energyEnvelope.length - i); // Smaller window
      const window = energyEnvelope.slice(i, i + windowLength);
      
      const confidence = this.fastMatchPattern(window, primaryPattern.pattern, primaryPattern.threshold);
      
      if (confidence > bestMatch) {
        bestMatch = confidence;
        matchStart = i;
        matchEnd = i + windowLength;
      }
      
      // Early exit if we find a strong match (cost optimization)
      if (confidence > 0.8) {
        break;
      }
    }

    const detected = bestMatch > this.confidenceThreshold;

    return {
      detected,
      confidence: bestMatch,
      keyword,
      startTime: (matchStart * skipSamples / this.sampleRate) * 1000,
      endTime: (matchEnd * skipSamples / this.sampleRate) * 1000
    };
  }

  // Faster energy envelope calculation
  private fastEnergyEnvelope(samples: Int16Array, windowSize: number, skipSamples: number): number[] {
    const envelope: number[] = [];
    
    for (let i = 0; i < samples.length - windowSize; i += skipSamples) {
      const window = samples.slice(i, i + windowSize);
      let energy = 0;
      
      // Sample every 4th value for speed
      for (let j = 0; j < window.length; j += 4) {
        energy += window[j] * window[j];
      }
      
      envelope.push(Math.sqrt(energy / (window.length / 4)) / 32767);
    }
    
    return envelope;
  }

  // Simplified pattern matching for speed
  private fastMatchPattern(signal: number[], pattern: number[], threshold: number): number {
    if (signal.length < pattern.length) {
      return 0;
    }

    let bestCorrelation = 0;
    const maxOffset = Math.min(5, signal.length - pattern.length); // Limit search range
    
    for (let offset = 0; offset <= maxOffset; offset++) {
      let correlation = 0;
      let signalMagnitude = 0;
      
      for (let i = 0; i < pattern.length; i++) {
        const signalValue = signal[offset + i];
        correlation += signalValue * pattern[i];
        signalMagnitude += signalValue * signalValue;
      }

      const normalizedCorrelation = correlation / (Math.sqrt(signalMagnitude) + 1e-10);
      bestCorrelation = Math.max(bestCorrelation, normalizedCorrelation);
    }

    return Math.max(0, bestCorrelation);
  }

  private preprocessAudio(audioBuffer: Buffer): Buffer {
    // Remove background noise
    let processed = AudioProcessingService.removeNoise(audioBuffer, 800);
    
    // Normalize audio levels
    processed = AudioProcessingService.normalizeAudioLevel(processed, 0.7);
    
    return processed;
  }

  private analyzeAudioPatterns(audioBuffer: Buffer, patterns: AudioPattern[], keyword: string): WakeWordResult {
    const samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
    let bestMatch = 0;
    let matchStart = 0;
    let matchEnd = 0;

    // Convert audio to energy envelope for pattern matching
    const energyEnvelope = this.calculateEnergyEnvelope(samples);
    
    for (let i = 0; i < energyEnvelope.length - 20; i++) {
      const windowSize = Math.min(50, energyEnvelope.length - i);
      const window = energyEnvelope.slice(i, i + windowSize);
      
      for (const pattern of patterns) {
        const confidence = this.matchPattern(window, pattern.pattern, pattern.threshold);
        
        if (confidence > bestMatch && confidence > this.confidenceThreshold) {
          bestMatch = confidence;
          matchStart = i;
          matchEnd = i + windowSize;
        }
      }
    }

    const detected = bestMatch > this.confidenceThreshold;
    
    if (detected) {
      logger.info(`[WakeWordDetectionService] Wake word "${keyword}" detected with confidence ${bestMatch.toFixed(3)}`);
    }

    return {
      detected,
      confidence: bestMatch,
      keyword,
      startTime: (matchStart / this.sampleRate) * 1000,
      endTime: (matchEnd / this.sampleRate) * 1000
    };
  }

  private calculateEnergyEnvelope(samples: Int16Array, windowSize: number = 1024): number[] {
    const envelope: number[] = [];
    
    for (let i = 0; i < samples.length; i += windowSize) {
      const window = samples.slice(i, i + windowSize);
      let energy = 0;
      
      for (let j = 0; j < window.length; j++) {
        energy += window[j] * window[j];
      }
      
      envelope.push(Math.sqrt(energy / window.length) / 32767);
    }
    
    return envelope;
  }

  private matchPattern(signal: number[], pattern: number[], threshold: number): number {
    if (signal.length < pattern.length) {
      return 0;
    }

    let bestCorrelation = 0;
    
    for (let offset = 0; offset <= signal.length - pattern.length; offset++) {
      let correlation = 0;
      let patternMagnitude = 0;
      let signalMagnitude = 0;

      for (let i = 0; i < pattern.length; i++) {
        const signalValue = signal[offset + i];
        const patternValue = pattern[i];
        
        correlation += signalValue * patternValue;
        patternMagnitude += patternValue * patternValue;
        signalMagnitude += signalValue * signalValue;
      }

      // Normalized cross-correlation
      const normalizedCorrelation = correlation / (Math.sqrt(patternMagnitude * signalMagnitude) + 1e-10);
      bestCorrelation = Math.max(bestCorrelation, normalizedCorrelation);
    }

    return Math.max(0, bestCorrelation);
  }

  private createNegativeResult(keyword: string, startTime: number): WakeWordResult {
    return {
      detected: false,
      confidence: 0,
      keyword,
      startTime: 0,
      endTime: 0
    };
  }

  updateConfidenceThreshold(newThreshold: number): void {
    this.confidenceThreshold = Math.max(0.1, Math.min(0.95, newThreshold));
    logger.info(`[WakeWordDetectionService] Updated confidence threshold to ${this.confidenceThreshold}`);
  }

  addCustomPattern(keyword: string, patterns: AudioPattern[]): void {
    this.wakeWordPatterns.set(keyword.toLowerCase(), patterns);
    logger.info(`[WakeWordDetectionService] Added custom patterns for keyword: ${keyword}`);
  }

  getSupportedKeywords(): string[] {
    return Array.from(this.wakeWordPatterns.keys());
  }

  // Cost optimization controls
  enableProcessing(): void {
    this.processingEnabled = true;
    logger.info('[WakeWordDetectionService] ✅ Wake word processing ENABLED');
  }

  disableProcessing(): void {
    this.processingEnabled = false;
    logger.info('[WakeWordDetectionService] ❌ Wake word processing DISABLED - saving compute costs');
  }

  setCostOptimizationMode(enabled: boolean): void {
    this.costOptimizationMode = enabled;
    logger.info(`[WakeWordDetectionService] Cost optimization mode: ${enabled ? 'ENABLED' : 'DISABLED'}`);
  }

  getProcessingStats(): {
    enabled: boolean;
    costOptimization: boolean;
    confidenceThreshold: number;
    supportedKeywords: number;
  } {
    return {
      enabled: this.processingEnabled,
      costOptimization: this.costOptimizationMode,
      confidenceThreshold: this.confidenceThreshold,
      supportedKeywords: this.wakeWordPatterns.size
    };
  }
}