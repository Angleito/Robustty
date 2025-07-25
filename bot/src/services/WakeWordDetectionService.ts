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
    logger.info('[WakeWordDetectionService] 🎤 Initialized with Kanye detection patterns', {
      patternCount: kanyePatterns.length,
      patterns: kanyePatterns.map((p, idx) => ({
        index: idx,
        description: idx === 0 ? 'KAN sound' : 'YE sound',
        patternValues: p.pattern,
        threshold: p.threshold,
        durationRangeMs: `${(p.minLength / this.sampleRate * 1000).toFixed(1)}-${(p.maxLength / this.sampleRate * 1000).toFixed(1)}`
      }))
    });
  }

  async detectWakeWord(audioBuffer: Buffer, keyword: string = 'kanye'): Promise<WakeWordResult> {
    if (!this.processingEnabled) {
      logger.debug(`[WakeWordDetectionService] 🚫 Processing disabled, skipping detection for "${keyword}"`);
      return this.createNegativeResult(keyword, Date.now());
    }

    const startTime = Date.now();
    
    logger.debug(`[WakeWordDetectionService] 🔍 Starting wake word detection for "${keyword}"`, {
      bufferLength: audioBuffer.length,
      bufferDurationMs: (audioBuffer.length / (this.sampleRate * 4)) * 1000, // 4 bytes per sample (stereo 16-bit)
      confidenceThreshold: this.confidenceThreshold,
      costOptimizationMode: this.costOptimizationMode
    });
    
    try {
      // COST OPTIMIZATION: Quick early exits to minimize processing
      
      // 1. Check minimum audio length (skip very short segments)
      if (audioBuffer.length < 3200) { // Less than ~67ms at 48kHz stereo
        const skipReason = `Buffer too short: ${audioBuffer.length} bytes < 3200 bytes (~67ms)`;
        logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: ${skipReason}`);
        return this.createNegativeResult(keyword, startTime);
      }

      // 2. Fast energy check before any processing
      const rawAudioLevel = AudioProcessingService.calculateAudioLevel(audioBuffer);
      logger.debug(`[WakeWordDetectionService] 📊 Raw audio level: ${rawAudioLevel.toFixed(4)}`);
      
      if (rawAudioLevel < 0.03) { // Very quiet audio, likely silence
        const skipReason = `Audio too quiet: level ${rawAudioLevel.toFixed(4)} < 0.03 threshold`;
        logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: ${skipReason} (likely silence)`);
        return this.createNegativeResult(keyword, startTime);
      }

      // 3. Only preprocess if we pass initial energy check
      const preprocessStart = Date.now();
      const processedAudio = this.costOptimizedPreprocessing(audioBuffer);
      const preprocessTime = Date.now() - preprocessStart;
      
      logger.debug(`[WakeWordDetectionService] 🔧 Preprocessing completed`, {
        preprocessingTimeMs: preprocessTime,
        originalSize: audioBuffer.length,
        processedSize: processedAudio.length,
        costOptimized: this.costOptimizationMode
      });
      
      // 4. Secondary energy check on processed audio
      const processedAudioLevel = AudioProcessingService.calculateAudioLevel(processedAudio);
      logger.debug(`[WakeWordDetectionService] 📊 Processed audio level: ${processedAudioLevel.toFixed(4)}`);
      
      if (processedAudioLevel < 0.05) {
        const skipReason = `Processed audio too quiet: level ${processedAudioLevel.toFixed(4)} < 0.05 threshold`;
        logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: ${skipReason}`);
        return this.createNegativeResult(keyword, startTime);
      }

      const patterns = this.wakeWordPatterns.get(keyword.toLowerCase());
      if (!patterns) {
        logger.warn(`[WakeWordDetectionService] ⚠️ No patterns found for keyword: "${keyword}"`, {
          availableKeywords: this.getSupportedKeywords()
        });
        return this.createNegativeResult(keyword, startTime);
      }

      logger.debug(`[WakeWordDetectionService] 🎵 Starting pattern analysis`, {
        keyword,
        patternCount: patterns.length,
        primaryPatternThreshold: patterns[0]?.threshold
      });

      // 5. Lightweight pattern analysis optimized for speed
      const analysisStart = Date.now();
      const result = this.fastAnalyzeAudioPatterns(processedAudio, patterns, keyword);
      const analysisTime = Date.now() - analysisStart;
      
      const processingTime = Date.now() - startTime;
      
      if (result.detected) {
        logger.info(`[WakeWordDetectionService] 🎯 WAKE WORD DETECTED! "${keyword}"`, {
          confidence: result.confidence.toFixed(3),
          confidenceThreshold: this.confidenceThreshold,
          processingTimeMs: processingTime,
          analysisTimeMs: analysisTime,
          startTimeMs: result.startTime.toFixed(1),
          endTimeMs: result.endTime.toFixed(1)
        });
      } else {
        logger.debug(`[WakeWordDetectionService] 🔍 No wake word detected`, {
          keyword,
          maxConfidence: result.confidence.toFixed(3),
          confidenceThreshold: this.confidenceThreshold,
          processingTimeMs: processingTime,
          analysisTimeMs: analysisTime,
          missedBy: (this.confidenceThreshold - result.confidence).toFixed(3)
        });
      }
      
      return result;

    } catch (error) {
      logger.error('[WakeWordDetectionService] ❌ Error detecting wake word:', {
        keyword,
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
        processingTimeMs: Date.now() - startTime
      });
      return this.createNegativeResult(keyword, startTime);
    }
  }

  // Lightweight preprocessing optimized for cost
  private costOptimizedPreprocessing(audioBuffer: Buffer): Buffer {
    if (!this.costOptimizationMode) {
      logger.debug('[WakeWordDetectionService] 💰 Cost optimization disabled, using full preprocessing');
      return this.preprocessAudio(audioBuffer);
    }

    // Minimal preprocessing for cost optimization
    // Skip noise reduction, only do basic normalization
    logger.debug('[WakeWordDetectionService] 💰 Cost optimization enabled: skipping noise reduction, applying normalization only');
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
    
    logger.debug(`[WakeWordDetectionService] 🎵 Analyzing audio patterns`, {
      sampleCount: samples.length,
      windowSize,
      skipSamples,
      effectiveSampleRate: this.sampleRate / (skipSamples / windowSize)
    });
    
    const envelopeStart = Date.now();
    const energyEnvelope = this.fastEnergyEnvelope(samples, windowSize, skipSamples);
    const envelopeTime = Date.now() - envelopeStart;
    
    logger.debug(`[WakeWordDetectionService] 📈 Energy envelope calculated`, {
      envelopeLength: energyEnvelope.length,
      calculationTimeMs: envelopeTime,
      samplesProcessed: samples.length
    });
    
    if (energyEnvelope.length < 10) { // Too short to contain wake word
      logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: envelope too short (${energyEnvelope.length} < 10)`);
      return this.createNegativeResult(keyword, 0);
    }

    // Only check the most distinctive patterns first
    const primaryPattern = patterns[0]; // Use primary pattern only for speed
    
    logger.debug(`[WakeWordDetectionService] 🔍 Starting pattern matching`, {
      patternLength: primaryPattern.pattern.length,
      patternThreshold: primaryPattern.threshold,
      searchPositions: Math.floor((energyEnvelope.length - 20) / 2) + 1
    });
    
    let positionsChecked = 0;
    for (let i = 0; i < energyEnvelope.length - 20; i += 2) { // Skip every other position
      positionsChecked++;
      const windowLength = Math.min(25, energyEnvelope.length - i); // Smaller window
      const window = energyEnvelope.slice(i, i + windowLength);
      
      const confidence = this.fastMatchPattern(window, primaryPattern.pattern, primaryPattern.threshold);
      
      if (confidence > bestMatch) {
        bestMatch = confidence;
        matchStart = i;
        matchEnd = i + windowLength;
        
        logger.debug(`[WakeWordDetectionService] 📍 New best match found`, {
          position: i,
          confidence: confidence.toFixed(3),
          windowLength
        });
      }
      
      // Early exit if we find a strong match (cost optimization)
      if (confidence > 0.8) {
        logger.debug(`[WakeWordDetectionService] 🎯 Early exit: strong match found`, {
          confidence: confidence.toFixed(3),
          position: i,
          positionsChecked
        });
        break;
      }
    }

    const detected = bestMatch > this.confidenceThreshold;

    logger.debug(`[WakeWordDetectionService] 🔍 Pattern matching complete`, {
      detected,
      bestConfidence: bestMatch.toFixed(3),
      confidenceThreshold: this.confidenceThreshold,
      positionsChecked,
      matchLocation: detected ? `${matchStart}-${matchEnd}` : 'none'
    });

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
    const windowCount = Math.floor((samples.length - windowSize) / skipSamples) + 1;
    
    logger.debug(`[WakeWordDetectionService] 📊 Calculating fast energy envelope`, {
      totalSamples: samples.length,
      windowSize,
      skipSamples,
      expectedWindows: windowCount,
      samplingRate: '1/4 (every 4th sample)'
    });
    
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
      logger.debug(`[WakeWordDetectionService] ⏭️ Signal too short for pattern: ${signal.length} < ${pattern.length}`);
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
    const startTime = Date.now();
    
    logger.debug('[WakeWordDetectionService] 🔧 Starting full audio preprocessing');
    
    // Remove background noise
    const noiseStart = Date.now();
    let processed = AudioProcessingService.removeNoise(audioBuffer, 800);
    const noiseTime = Date.now() - noiseStart;
    
    logger.debug(`[WakeWordDetectionService] 🔇 Noise removal completed`, {
      noiseThreshold: 800,
      processingTimeMs: noiseTime,
      inputSize: audioBuffer.length,
      outputSize: processed.length
    });
    
    // Normalize audio levels
    const normalizeStart = Date.now();
    processed = AudioProcessingService.normalizeAudioLevel(processed, 0.7);
    const normalizeTime = Date.now() - normalizeStart;
    
    logger.debug(`[WakeWordDetectionService] 📊 Audio normalization completed`, {
      targetLevel: 0.7,
      processingTimeMs: normalizeTime,
      totalPreprocessingTimeMs: Date.now() - startTime
    });
    
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
    const oldThreshold = this.confidenceThreshold;
    this.confidenceThreshold = Math.max(0.1, Math.min(0.95, newThreshold));
    logger.info(`[WakeWordDetectionService] 🎚️ Updated confidence threshold`, {
      oldThreshold,
      newThreshold: this.confidenceThreshold,
      requested: newThreshold,
      clamped: newThreshold !== this.confidenceThreshold
    });
  }

  addCustomPattern(keyword: string, patterns: AudioPattern[]): void {
    const normalizedKeyword = keyword.toLowerCase();
    const existingPatterns = this.wakeWordPatterns.has(normalizedKeyword);
    this.wakeWordPatterns.set(normalizedKeyword, patterns);
    
    logger.info(`[WakeWordDetectionService] 🎤 ${existingPatterns ? 'Updated' : 'Added'} custom patterns`, {
      keyword: normalizedKeyword,
      patternCount: patterns.length,
      patterns: patterns.map((p, idx) => ({
        index: idx,
        patternLength: p.pattern.length,
        threshold: p.threshold,
        minLength: p.minLength,
        maxLength: p.maxLength
      })),
      totalKeywords: this.wakeWordPatterns.size
    });
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