"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.WakeWordDetectionService = void 0;
const logger_1 = require("./logger");
const AudioProcessingService_1 = require("./AudioProcessingService");
class WakeWordDetectionService {
    wakeWordPatterns;
    confidenceThreshold;
    sampleRate;
    processingEnabled = true;
    costOptimizationMode = true;
    constructor(confidenceThreshold = 0.6, sampleRate = 48000) {
        this.confidenceThreshold = confidenceThreshold;
        this.sampleRate = sampleRate;
        this.wakeWordPatterns = new Map();
        this.initializeKanyePatterns();
        logger_1.logger.info('[WakeWordDetectionService] Initialized in COST OPTIMIZATION mode - only processing after wake word detection');
    }
    initializeKanyePatterns() {
        const kanyePatterns = [
            {
                pattern: [0.1, 0.8, 0.9, 0.7, 0.4],
                threshold: 0.6,
                minLength: 100,
                maxLength: 400
            },
            {
                pattern: [0.3, 0.6, 0.8, 0.5, 0.2],
                threshold: 0.6,
                minLength: 150,
                maxLength: 500
            }
        ];
        this.wakeWordPatterns.set('kanye', kanyePatterns);
        logger_1.logger.info('[WakeWordDetectionService] Initialized with Kanye detection patterns');
    }
    async detectWakeWord(audioBuffer, keyword = 'kanye') {
        if (!this.processingEnabled) {
            return this.createNegativeResult(keyword, Date.now());
        }
        const startTime = Date.now();
        try {
            if (audioBuffer.length < 3200) {
                return this.createNegativeResult(keyword, startTime);
            }
            const rawAudioLevel = AudioProcessingService_1.AudioProcessingService.calculateAudioLevel(audioBuffer);
            if (rawAudioLevel < 0.03) {
                return this.createNegativeResult(keyword, startTime);
            }
            const processedAudio = this.costOptimizedPreprocessing(audioBuffer);
            const processedAudioLevel = AudioProcessingService_1.AudioProcessingService.calculateAudioLevel(processedAudio);
            if (processedAudioLevel < 0.05) {
                return this.createNegativeResult(keyword, startTime);
            }
            const patterns = this.wakeWordPatterns.get(keyword.toLowerCase());
            if (!patterns) {
                logger_1.logger.warn(`[WakeWordDetectionService] No patterns found for keyword: ${keyword}`);
                return this.createNegativeResult(keyword, startTime);
            }
            const result = this.fastAnalyzeAudioPatterns(processedAudio, patterns, keyword);
            const processingTime = Date.now() - startTime;
            if (result.detected) {
                logger_1.logger.info(`[WakeWordDetectionService] 🎯 WAKE WORD DETECTED! "${keyword}" in ${processingTime}ms (confidence: ${result.confidence.toFixed(3)})`);
            }
            else {
                logger_1.logger.debug(`[WakeWordDetectionService] No wake word in ${processingTime}ms (max confidence: ${result.confidence.toFixed(3)})`);
            }
            return result;
        }
        catch (error) {
            logger_1.logger.error('[WakeWordDetectionService] Error detecting wake word:', error);
            return this.createNegativeResult(keyword, startTime);
        }
    }
    costOptimizedPreprocessing(audioBuffer) {
        if (!this.costOptimizationMode) {
            return this.preprocessAudio(audioBuffer);
        }
        return AudioProcessingService_1.AudioProcessingService.normalizeAudioLevel(audioBuffer, 0.6);
    }
    fastAnalyzeAudioPatterns(audioBuffer, patterns, keyword) {
        const samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
        let bestMatch = 0;
        let matchStart = 0;
        let matchEnd = 0;
        const windowSize = 512;
        const skipSamples = 256;
        const energyEnvelope = this.fastEnergyEnvelope(samples, windowSize, skipSamples);
        if (energyEnvelope.length < 10) {
            return this.createNegativeResult(keyword, 0);
        }
        const primaryPattern = patterns[0];
        for (let i = 0; i < energyEnvelope.length - 20; i += 2) {
            const windowLength = Math.min(25, energyEnvelope.length - i);
            const window = energyEnvelope.slice(i, i + windowLength);
            const confidence = this.fastMatchPattern(window, primaryPattern.pattern, primaryPattern.threshold);
            if (confidence > bestMatch) {
                bestMatch = confidence;
                matchStart = i;
                matchEnd = i + windowLength;
            }
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
    fastEnergyEnvelope(samples, windowSize, skipSamples) {
        const envelope = [];
        for (let i = 0; i < samples.length - windowSize; i += skipSamples) {
            const window = samples.slice(i, i + windowSize);
            let energy = 0;
            for (let j = 0; j < window.length; j += 4) {
                energy += window[j] * window[j];
            }
            envelope.push(Math.sqrt(energy / (window.length / 4)) / 32767);
        }
        return envelope;
    }
    fastMatchPattern(signal, pattern, threshold) {
        if (signal.length < pattern.length) {
            return 0;
        }
        let bestCorrelation = 0;
        const maxOffset = Math.min(5, signal.length - pattern.length);
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
    preprocessAudio(audioBuffer) {
        let processed = AudioProcessingService_1.AudioProcessingService.removeNoise(audioBuffer, 800);
        processed = AudioProcessingService_1.AudioProcessingService.normalizeAudioLevel(processed, 0.7);
        return processed;
    }
    analyzeAudioPatterns(audioBuffer, patterns, keyword) {
        const samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
        let bestMatch = 0;
        let matchStart = 0;
        let matchEnd = 0;
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
            logger_1.logger.info(`[WakeWordDetectionService] Wake word "${keyword}" detected with confidence ${bestMatch.toFixed(3)}`);
        }
        return {
            detected,
            confidence: bestMatch,
            keyword,
            startTime: (matchStart / this.sampleRate) * 1000,
            endTime: (matchEnd / this.sampleRate) * 1000
        };
    }
    calculateEnergyEnvelope(samples, windowSize = 1024) {
        const envelope = [];
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
    matchPattern(signal, pattern, threshold) {
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
            const normalizedCorrelation = correlation / (Math.sqrt(patternMagnitude * signalMagnitude) + 1e-10);
            bestCorrelation = Math.max(bestCorrelation, normalizedCorrelation);
        }
        return Math.max(0, bestCorrelation);
    }
    createNegativeResult(keyword, startTime) {
        return {
            detected: false,
            confidence: 0,
            keyword,
            startTime: 0,
            endTime: 0
        };
    }
    updateConfidenceThreshold(newThreshold) {
        this.confidenceThreshold = Math.max(0.1, Math.min(0.95, newThreshold));
        logger_1.logger.info(`[WakeWordDetectionService] Updated confidence threshold to ${this.confidenceThreshold}`);
    }
    addCustomPattern(keyword, patterns) {
        this.wakeWordPatterns.set(keyword.toLowerCase(), patterns);
        logger_1.logger.info(`[WakeWordDetectionService] Added custom patterns for keyword: ${keyword}`);
    }
    getSupportedKeywords() {
        return Array.from(this.wakeWordPatterns.keys());
    }
    enableProcessing() {
        this.processingEnabled = true;
        logger_1.logger.info('[WakeWordDetectionService] ✅ Wake word processing ENABLED');
    }
    disableProcessing() {
        this.processingEnabled = false;
        logger_1.logger.info('[WakeWordDetectionService] ❌ Wake word processing DISABLED - saving compute costs');
    }
    setCostOptimizationMode(enabled) {
        this.costOptimizationMode = enabled;
        logger_1.logger.info(`[WakeWordDetectionService] Cost optimization mode: ${enabled ? 'ENABLED' : 'DISABLED'}`);
    }
    getProcessingStats() {
        return {
            enabled: this.processingEnabled,
            costOptimization: this.costOptimizationMode,
            confidenceThreshold: this.confidenceThreshold,
            supportedKeywords: this.wakeWordPatterns.size
        };
    }
}
exports.WakeWordDetectionService = WakeWordDetectionService;
//# sourceMappingURL=WakeWordDetectionService.js.map