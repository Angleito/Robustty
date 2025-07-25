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
        logger_1.logger.info(`[WakeWordDetectionService] 🚀 Starting initialization...`, {
            confidenceThreshold,
            sampleRate,
            costOptimizationMode: this.costOptimizationMode
        });
        this.initializeKanyePatterns();
        logger_1.logger.info('[WakeWordDetectionService] ✅ Initialized in COST OPTIMIZATION mode - only processing after wake word detection', {
            supportedKeywords: this.getSupportedKeywords(),
            processingEnabled: this.processingEnabled
        });
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
        logger_1.logger.info('[WakeWordDetectionService] 🎤 Initialized with Kanye detection patterns', {
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
    async detectWakeWord(audioBuffer, keyword = 'kanye') {
        if (!this.processingEnabled) {
            logger_1.logger.debug(`[WakeWordDetectionService] 🚫 Processing disabled, skipping detection for "${keyword}"`);
            return this.createNegativeResult(keyword, Date.now());
        }
        const startTime = Date.now();
        logger_1.logger.debug(`[WakeWordDetectionService] 🔍 Starting wake word detection for "${keyword}"`, {
            bufferLength: audioBuffer.length,
            bufferDurationMs: (audioBuffer.length / (this.sampleRate * 4)) * 1000,
            confidenceThreshold: this.confidenceThreshold,
            costOptimizationMode: this.costOptimizationMode
        });
        try {
            if (audioBuffer.length < 3200) {
                const skipReason = `Buffer too short: ${audioBuffer.length} bytes < 3200 bytes (~67ms)`;
                logger_1.logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: ${skipReason}`);
                return this.createNegativeResult(keyword, startTime);
            }
            const rawAudioLevel = AudioProcessingService_1.AudioProcessingService.calculateAudioLevel(audioBuffer);
            logger_1.logger.debug(`[WakeWordDetectionService] 📊 Raw audio level: ${rawAudioLevel.toFixed(4)}`);
            if (rawAudioLevel < 0.03) {
                const skipReason = `Audio too quiet: level ${rawAudioLevel.toFixed(4)} < 0.03 threshold`;
                logger_1.logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: ${skipReason} (likely silence)`);
                return this.createNegativeResult(keyword, startTime);
            }
            const preprocessStart = Date.now();
            const processedAudio = this.costOptimizedPreprocessing(audioBuffer);
            const preprocessTime = Date.now() - preprocessStart;
            logger_1.logger.debug(`[WakeWordDetectionService] 🔧 Preprocessing completed`, {
                preprocessingTimeMs: preprocessTime,
                originalSize: audioBuffer.length,
                processedSize: processedAudio.length,
                costOptimized: this.costOptimizationMode
            });
            const processedAudioLevel = AudioProcessingService_1.AudioProcessingService.calculateAudioLevel(processedAudio);
            logger_1.logger.debug(`[WakeWordDetectionService] 📊 Processed audio level: ${processedAudioLevel.toFixed(4)}`);
            if (processedAudioLevel < 0.05) {
                const skipReason = `Processed audio too quiet: level ${processedAudioLevel.toFixed(4)} < 0.05 threshold`;
                logger_1.logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: ${skipReason}`);
                return this.createNegativeResult(keyword, startTime);
            }
            const patterns = this.wakeWordPatterns.get(keyword.toLowerCase());
            if (!patterns) {
                logger_1.logger.warn(`[WakeWordDetectionService] ⚠️ No patterns found for keyword: "${keyword}"`, {
                    availableKeywords: this.getSupportedKeywords()
                });
                return this.createNegativeResult(keyword, startTime);
            }
            logger_1.logger.debug(`[WakeWordDetectionService] 🎵 Starting pattern analysis`, {
                keyword,
                patternCount: patterns.length,
                primaryPatternThreshold: patterns[0]?.threshold
            });
            const analysisStart = Date.now();
            const result = this.fastAnalyzeAudioPatterns(processedAudio, patterns, keyword);
            const analysisTime = Date.now() - analysisStart;
            const processingTime = Date.now() - startTime;
            if (result.detected) {
                logger_1.logger.info(`[WakeWordDetectionService] 🎯 WAKE WORD DETECTED! "${keyword}"`, {
                    confidence: result.confidence.toFixed(3),
                    confidenceThreshold: this.confidenceThreshold,
                    processingTimeMs: processingTime,
                    analysisTimeMs: analysisTime,
                    startTimeMs: result.startTime.toFixed(1),
                    endTimeMs: result.endTime.toFixed(1)
                });
            }
            else {
                logger_1.logger.debug(`[WakeWordDetectionService] 🔍 No wake word detected`, {
                    keyword,
                    maxConfidence: result.confidence.toFixed(3),
                    confidenceThreshold: this.confidenceThreshold,
                    processingTimeMs: processingTime,
                    analysisTimeMs: analysisTime,
                    missedBy: (this.confidenceThreshold - result.confidence).toFixed(3)
                });
            }
            return result;
        }
        catch (error) {
            logger_1.logger.error('[WakeWordDetectionService] ❌ Error detecting wake word:', {
                keyword,
                error: error instanceof Error ? error.message : String(error),
                stack: error instanceof Error ? error.stack : undefined,
                processingTimeMs: Date.now() - startTime
            });
            return this.createNegativeResult(keyword, startTime);
        }
    }
    costOptimizedPreprocessing(audioBuffer) {
        if (!this.costOptimizationMode) {
            logger_1.logger.debug('[WakeWordDetectionService] 💰 Cost optimization disabled, using full preprocessing');
            return this.preprocessAudio(audioBuffer);
        }
        logger_1.logger.debug('[WakeWordDetectionService] 💰 Cost optimization enabled: skipping noise reduction, applying normalization only');
        return AudioProcessingService_1.AudioProcessingService.normalizeAudioLevel(audioBuffer, 0.6);
    }
    fastAnalyzeAudioPatterns(audioBuffer, patterns, keyword) {
        const samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
        let bestMatch = 0;
        let matchStart = 0;
        let matchEnd = 0;
        const windowSize = 512;
        const skipSamples = 256;
        logger_1.logger.debug(`[WakeWordDetectionService] 🎵 Analyzing audio patterns`, {
            sampleCount: samples.length,
            windowSize,
            skipSamples,
            effectiveSampleRate: this.sampleRate / (skipSamples / windowSize)
        });
        const envelopeStart = Date.now();
        const energyEnvelope = this.fastEnergyEnvelope(samples, windowSize, skipSamples);
        const envelopeTime = Date.now() - envelopeStart;
        logger_1.logger.debug(`[WakeWordDetectionService] 📈 Energy envelope calculated`, {
            envelopeLength: energyEnvelope.length,
            calculationTimeMs: envelopeTime,
            samplesProcessed: samples.length
        });
        if (energyEnvelope.length < 10) {
            logger_1.logger.debug(`[WakeWordDetectionService] ⏭️ Early exit: envelope too short (${energyEnvelope.length} < 10)`);
            return this.createNegativeResult(keyword, 0);
        }
        const primaryPattern = patterns[0];
        logger_1.logger.debug(`[WakeWordDetectionService] 🔍 Starting pattern matching`, {
            patternLength: primaryPattern.pattern.length,
            patternThreshold: primaryPattern.threshold,
            searchPositions: Math.floor((energyEnvelope.length - 20) / 2) + 1
        });
        let positionsChecked = 0;
        for (let i = 0; i < energyEnvelope.length - 20; i += 2) {
            positionsChecked++;
            const windowLength = Math.min(25, energyEnvelope.length - i);
            const window = energyEnvelope.slice(i, i + windowLength);
            const confidence = this.fastMatchPattern(window, primaryPattern.pattern, primaryPattern.threshold);
            if (confidence > bestMatch) {
                bestMatch = confidence;
                matchStart = i;
                matchEnd = i + windowLength;
                logger_1.logger.debug(`[WakeWordDetectionService] 📍 New best match found`, {
                    position: i,
                    confidence: confidence.toFixed(3),
                    windowLength
                });
            }
            if (confidence > 0.8) {
                logger_1.logger.debug(`[WakeWordDetectionService] 🎯 Early exit: strong match found`, {
                    confidence: confidence.toFixed(3),
                    position: i,
                    positionsChecked
                });
                break;
            }
        }
        const detected = bestMatch > this.confidenceThreshold;
        logger_1.logger.debug(`[WakeWordDetectionService] 🔍 Pattern matching complete`, {
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
    fastEnergyEnvelope(samples, windowSize, skipSamples) {
        const envelope = [];
        const windowCount = Math.floor((samples.length - windowSize) / skipSamples) + 1;
        logger_1.logger.debug(`[WakeWordDetectionService] 📊 Calculating fast energy envelope`, {
            totalSamples: samples.length,
            windowSize,
            skipSamples,
            expectedWindows: windowCount,
            samplingRate: '1/4 (every 4th sample)'
        });
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
            logger_1.logger.debug(`[WakeWordDetectionService] ⏭️ Signal too short for pattern: ${signal.length} < ${pattern.length}`);
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
        const startTime = Date.now();
        logger_1.logger.debug('[WakeWordDetectionService] 🔧 Starting full audio preprocessing');
        const noiseStart = Date.now();
        let processed = AudioProcessingService_1.AudioProcessingService.removeNoise(audioBuffer, 800);
        const noiseTime = Date.now() - noiseStart;
        logger_1.logger.debug(`[WakeWordDetectionService] 🔇 Noise removal completed`, {
            noiseThreshold: 800,
            processingTimeMs: noiseTime,
            inputSize: audioBuffer.length,
            outputSize: processed.length
        });
        const normalizeStart = Date.now();
        processed = AudioProcessingService_1.AudioProcessingService.normalizeAudioLevel(processed, 0.7);
        const normalizeTime = Date.now() - normalizeStart;
        logger_1.logger.debug(`[WakeWordDetectionService] 📊 Audio normalization completed`, {
            targetLevel: 0.7,
            processingTimeMs: normalizeTime,
            totalPreprocessingTimeMs: Date.now() - startTime
        });
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
        const oldThreshold = this.confidenceThreshold;
        this.confidenceThreshold = Math.max(0.1, Math.min(0.95, newThreshold));
        logger_1.logger.info(`[WakeWordDetectionService] 🎚️ Updated confidence threshold`, {
            oldThreshold,
            newThreshold: this.confidenceThreshold,
            requested: newThreshold,
            clamped: newThreshold !== this.confidenceThreshold
        });
    }
    addCustomPattern(keyword, patterns) {
        const normalizedKeyword = keyword.toLowerCase();
        const existingPatterns = this.wakeWordPatterns.has(normalizedKeyword);
        this.wakeWordPatterns.set(normalizedKeyword, patterns);
        logger_1.logger.info(`[WakeWordDetectionService] 🎤 ${existingPatterns ? 'Updated' : 'Added'} custom patterns`, {
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