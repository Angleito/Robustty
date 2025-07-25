"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WakeWordDetectionService = void 0;
var logger_1 = require("./logger");
var AudioProcessingService_1 = require("./AudioProcessingService");
var WakeWordDetectionService = /** @class */ (function () {
    function WakeWordDetectionService(confidenceThreshold, sampleRate) {
        if (confidenceThreshold === void 0) { confidenceThreshold = 0.6; }
        if (sampleRate === void 0) { sampleRate = 48000; }
        this.processingEnabled = true;
        this.costOptimizationMode = true; // Enable aggressive cost optimization
        this.confidenceThreshold = confidenceThreshold;
        this.sampleRate = sampleRate;
        this.wakeWordPatterns = new Map();
        logger_1.logger.info("[WakeWordDetectionService] \uD83D\uDE80 Starting initialization...", {
            confidenceThreshold: confidenceThreshold,
            sampleRate: sampleRate,
            costOptimizationMode: this.costOptimizationMode
        });
        // Initialize "Kanye" detection patterns
        this.initializeKanyePatterns();
        logger_1.logger.info('[WakeWordDetectionService] ✅ Initialized in COST OPTIMIZATION mode - only processing after wake word detection', {
            supportedKeywords: this.getSupportedKeywords(),
            processingEnabled: this.processingEnabled
        });
    }
    WakeWordDetectionService.prototype.initializeKanyePatterns = function () {
        var _this = this;
        // Simplified audio pattern matching for "Kanye" 
        // These patterns represent approximate audio fingerprints
        var kanyePatterns = [
            {
                // Pattern for "KAN" sound (plosive K + vowel AN)
                pattern: [0.1, 0.8, 0.9, 0.7, 0.4],
                threshold: 0.6,
                minLength: 100, // ~2ms at 48kHz
                maxLength: 400 // ~8ms at 48kHz
            },
            {
                // Pattern for "YE" sound (consonant Y + vowel E)
                pattern: [0.3, 0.6, 0.8, 0.5, 0.2],
                threshold: 0.6,
                minLength: 150, // ~3ms at 48kHz
                maxLength: 500 // ~10ms at 48kHz
            }
        ];
        this.wakeWordPatterns.set('kanye', kanyePatterns);
        logger_1.logger.info('[WakeWordDetectionService] 🎤 Initialized with Kanye detection patterns', {
            patternCount: kanyePatterns.length,
            patterns: kanyePatterns.map(function (p, idx) { return ({
                index: idx,
                description: idx === 0 ? 'KAN sound' : 'YE sound',
                patternValues: p.pattern,
                threshold: p.threshold,
                durationRangeMs: "".concat((p.minLength / _this.sampleRate * 1000).toFixed(1), "-").concat((p.maxLength / _this.sampleRate * 1000).toFixed(1))
            }); })
        });
    };
    WakeWordDetectionService.prototype.detectWakeWord = function (audioBuffer_1) {
        return __awaiter(this, arguments, void 0, function (audioBuffer, keyword) {
            var startTime, skipReason, rawAudioLevel, skipReason, preprocessStart, processedAudio, preprocessTime, processedAudioLevel, skipReason, patterns, analysisStart, result, analysisTime, processingTime;
            var _a;
            if (keyword === void 0) { keyword = 'kanye'; }
            return __generator(this, function (_b) {
                if (!this.processingEnabled) {
                    logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDEAB Processing disabled, skipping detection for \"".concat(keyword, "\""));
                    return [2 /*return*/, this.createNegativeResult(keyword, Date.now())];
                }
                startTime = Date.now();
                logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDD0D Starting wake word detection for \"".concat(keyword, "\""), {
                    bufferLength: audioBuffer.length,
                    bufferDurationMs: (audioBuffer.length / (this.sampleRate * 4)) * 1000, // 4 bytes per sample (stereo 16-bit)
                    confidenceThreshold: this.confidenceThreshold,
                    costOptimizationMode: this.costOptimizationMode
                });
                try {
                    // COST OPTIMIZATION: Quick early exits to minimize processing
                    // 1. Check minimum audio length (skip very short segments)
                    if (audioBuffer.length < 3200) { // Less than ~67ms at 48kHz stereo
                        skipReason = "Buffer too short: ".concat(audioBuffer.length, " bytes < 3200 bytes (~67ms)");
                        logger_1.logger.debug("[WakeWordDetectionService] \u23ED\uFE0F Early exit: ".concat(skipReason));
                        return [2 /*return*/, this.createNegativeResult(keyword, startTime)];
                    }
                    rawAudioLevel = AudioProcessingService_1.AudioProcessingService.calculateAudioLevel(audioBuffer);
                    logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDCCA Raw audio level: ".concat(rawAudioLevel.toFixed(4)));
                    if (rawAudioLevel < 0.03) { // Very quiet audio, likely silence
                        skipReason = "Audio too quiet: level ".concat(rawAudioLevel.toFixed(4), " < 0.03 threshold");
                        logger_1.logger.debug("[WakeWordDetectionService] \u23ED\uFE0F Early exit: ".concat(skipReason, " (likely silence)"));
                        return [2 /*return*/, this.createNegativeResult(keyword, startTime)];
                    }
                    preprocessStart = Date.now();
                    processedAudio = this.costOptimizedPreprocessing(audioBuffer);
                    preprocessTime = Date.now() - preprocessStart;
                    logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDD27 Preprocessing completed", {
                        preprocessingTimeMs: preprocessTime,
                        originalSize: audioBuffer.length,
                        processedSize: processedAudio.length,
                        costOptimized: this.costOptimizationMode
                    });
                    processedAudioLevel = AudioProcessingService_1.AudioProcessingService.calculateAudioLevel(processedAudio);
                    logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDCCA Processed audio level: ".concat(processedAudioLevel.toFixed(4)));
                    if (processedAudioLevel < 0.05) {
                        skipReason = "Processed audio too quiet: level ".concat(processedAudioLevel.toFixed(4), " < 0.05 threshold");
                        logger_1.logger.debug("[WakeWordDetectionService] \u23ED\uFE0F Early exit: ".concat(skipReason));
                        return [2 /*return*/, this.createNegativeResult(keyword, startTime)];
                    }
                    patterns = this.wakeWordPatterns.get(keyword.toLowerCase());
                    if (!patterns) {
                        logger_1.logger.warn("[WakeWordDetectionService] \u26A0\uFE0F No patterns found for keyword: \"".concat(keyword, "\""), {
                            availableKeywords: this.getSupportedKeywords()
                        });
                        return [2 /*return*/, this.createNegativeResult(keyword, startTime)];
                    }
                    logger_1.logger.debug("[WakeWordDetectionService] \uD83C\uDFB5 Starting pattern analysis", {
                        keyword: keyword,
                        patternCount: patterns.length,
                        primaryPatternThreshold: (_a = patterns[0]) === null || _a === void 0 ? void 0 : _a.threshold
                    });
                    analysisStart = Date.now();
                    result = this.fastAnalyzeAudioPatterns(processedAudio, patterns, keyword);
                    analysisTime = Date.now() - analysisStart;
                    processingTime = Date.now() - startTime;
                    if (result.detected) {
                        logger_1.logger.info("[WakeWordDetectionService] \uD83C\uDFAF WAKE WORD DETECTED! \"".concat(keyword, "\""), {
                            confidence: result.confidence.toFixed(3),
                            confidenceThreshold: this.confidenceThreshold,
                            processingTimeMs: processingTime,
                            analysisTimeMs: analysisTime,
                            startTimeMs: result.startTime.toFixed(1),
                            endTimeMs: result.endTime.toFixed(1)
                        });
                    }
                    else {
                        logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDD0D No wake word detected", {
                            keyword: keyword,
                            maxConfidence: result.confidence.toFixed(3),
                            confidenceThreshold: this.confidenceThreshold,
                            processingTimeMs: processingTime,
                            analysisTimeMs: analysisTime,
                            missedBy: (this.confidenceThreshold - result.confidence).toFixed(3)
                        });
                    }
                    return [2 /*return*/, result];
                }
                catch (error) {
                    logger_1.logger.error('[WakeWordDetectionService] ❌ Error detecting wake word:', {
                        keyword: keyword,
                        error: error instanceof Error ? error.message : String(error),
                        stack: error instanceof Error ? error.stack : undefined,
                        processingTimeMs: Date.now() - startTime
                    });
                    return [2 /*return*/, this.createNegativeResult(keyword, startTime)];
                }
                return [2 /*return*/];
            });
        });
    };
    // Lightweight preprocessing optimized for cost
    WakeWordDetectionService.prototype.costOptimizedPreprocessing = function (audioBuffer) {
        if (!this.costOptimizationMode) {
            logger_1.logger.debug('[WakeWordDetectionService] 💰 Cost optimization disabled, using full preprocessing');
            return this.preprocessAudio(audioBuffer);
        }
        // Minimal preprocessing for cost optimization
        // Skip noise reduction, only do basic normalization
        logger_1.logger.debug('[WakeWordDetectionService] 💰 Cost optimization enabled: skipping noise reduction, applying normalization only');
        return AudioProcessingService_1.AudioProcessingService.normalizeAudioLevel(audioBuffer, 0.6);
    };
    // Fast pattern analysis optimized for speed over accuracy
    WakeWordDetectionService.prototype.fastAnalyzeAudioPatterns = function (audioBuffer, patterns, keyword) {
        var samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
        var bestMatch = 0;
        var matchStart = 0;
        var matchEnd = 0;
        // Use larger windows and skip samples for faster processing
        var windowSize = 512; // Larger window for speed
        var skipSamples = 256; // Skip samples to process faster
        logger_1.logger.debug("[WakeWordDetectionService] \uD83C\uDFB5 Analyzing audio patterns", {
            sampleCount: samples.length,
            windowSize: windowSize,
            skipSamples: skipSamples,
            effectiveSampleRate: this.sampleRate / (skipSamples / windowSize)
        });
        var envelopeStart = Date.now();
        var energyEnvelope = this.fastEnergyEnvelope(samples, windowSize, skipSamples);
        var envelopeTime = Date.now() - envelopeStart;
        logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDCC8 Energy envelope calculated", {
            envelopeLength: energyEnvelope.length,
            calculationTimeMs: envelopeTime,
            samplesProcessed: samples.length
        });
        if (energyEnvelope.length < 10) { // Too short to contain wake word
            logger_1.logger.debug("[WakeWordDetectionService] \u23ED\uFE0F Early exit: envelope too short (".concat(energyEnvelope.length, " < 10)"));
            return this.createNegativeResult(keyword, 0);
        }
        // Only check the most distinctive patterns first
        var primaryPattern = patterns[0]; // Use primary pattern only for speed
        logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDD0D Starting pattern matching", {
            patternLength: primaryPattern.pattern.length,
            patternThreshold: primaryPattern.threshold,
            searchPositions: Math.floor((energyEnvelope.length - 20) / 2) + 1
        });
        var positionsChecked = 0;
        for (var i = 0; i < energyEnvelope.length - 20; i += 2) { // Skip every other position
            positionsChecked++;
            var windowLength = Math.min(25, energyEnvelope.length - i); // Smaller window
            var window_1 = energyEnvelope.slice(i, i + windowLength);
            var confidence = this.fastMatchPattern(window_1, primaryPattern.pattern, primaryPattern.threshold);
            if (confidence > bestMatch) {
                bestMatch = confidence;
                matchStart = i;
                matchEnd = i + windowLength;
                logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDCCD New best match found", {
                    position: i,
                    confidence: confidence.toFixed(3),
                    windowLength: windowLength
                });
            }
            // Early exit if we find a strong match (cost optimization)
            if (confidence > 0.8) {
                logger_1.logger.debug("[WakeWordDetectionService] \uD83C\uDFAF Early exit: strong match found", {
                    confidence: confidence.toFixed(3),
                    position: i,
                    positionsChecked: positionsChecked
                });
                break;
            }
        }
        var detected = bestMatch > this.confidenceThreshold;
        logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDD0D Pattern matching complete", {
            detected: detected,
            bestConfidence: bestMatch.toFixed(3),
            confidenceThreshold: this.confidenceThreshold,
            positionsChecked: positionsChecked,
            matchLocation: detected ? "".concat(matchStart, "-").concat(matchEnd) : 'none'
        });
        return {
            detected: detected,
            confidence: bestMatch,
            keyword: keyword,
            startTime: (matchStart * skipSamples / this.sampleRate) * 1000,
            endTime: (matchEnd * skipSamples / this.sampleRate) * 1000
        };
    };
    // Faster energy envelope calculation
    WakeWordDetectionService.prototype.fastEnergyEnvelope = function (samples, windowSize, skipSamples) {
        var envelope = [];
        var windowCount = Math.floor((samples.length - windowSize) / skipSamples) + 1;
        logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDCCA Calculating fast energy envelope", {
            totalSamples: samples.length,
            windowSize: windowSize,
            skipSamples: skipSamples,
            expectedWindows: windowCount,
            samplingRate: '1/4 (every 4th sample)'
        });
        for (var i = 0; i < samples.length - windowSize; i += skipSamples) {
            var window_2 = samples.slice(i, i + windowSize);
            var energy = 0;
            // Sample every 4th value for speed
            for (var j = 0; j < window_2.length; j += 4) {
                energy += window_2[j] * window_2[j];
            }
            envelope.push(Math.sqrt(energy / (window_2.length / 4)) / 32767);
        }
        return envelope;
    };
    // Simplified pattern matching for speed
    WakeWordDetectionService.prototype.fastMatchPattern = function (signal, pattern, threshold) {
        if (signal.length < pattern.length) {
            logger_1.logger.debug("[WakeWordDetectionService] \u23ED\uFE0F Signal too short for pattern: ".concat(signal.length, " < ").concat(pattern.length));
            return 0;
        }
        var bestCorrelation = 0;
        var maxOffset = Math.min(5, signal.length - pattern.length); // Limit search range
        for (var offset = 0; offset <= maxOffset; offset++) {
            var correlation = 0;
            var signalMagnitude = 0;
            for (var i = 0; i < pattern.length; i++) {
                var signalValue = signal[offset + i];
                correlation += signalValue * pattern[i];
                signalMagnitude += signalValue * signalValue;
            }
            var normalizedCorrelation = correlation / (Math.sqrt(signalMagnitude) + 1e-10);
            bestCorrelation = Math.max(bestCorrelation, normalizedCorrelation);
        }
        return Math.max(0, bestCorrelation);
    };
    WakeWordDetectionService.prototype.preprocessAudio = function (audioBuffer) {
        var startTime = Date.now();
        logger_1.logger.debug('[WakeWordDetectionService] 🔧 Starting full audio preprocessing');
        // Remove background noise
        var noiseStart = Date.now();
        var processed = AudioProcessingService_1.AudioProcessingService.removeNoise(audioBuffer, 800);
        var noiseTime = Date.now() - noiseStart;
        logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDD07 Noise removal completed", {
            noiseThreshold: 800,
            processingTimeMs: noiseTime,
            inputSize: audioBuffer.length,
            outputSize: processed.length
        });
        // Normalize audio levels
        var normalizeStart = Date.now();
        processed = AudioProcessingService_1.AudioProcessingService.normalizeAudioLevel(processed, 0.7);
        var normalizeTime = Date.now() - normalizeStart;
        logger_1.logger.debug("[WakeWordDetectionService] \uD83D\uDCCA Audio normalization completed", {
            targetLevel: 0.7,
            processingTimeMs: normalizeTime,
            totalPreprocessingTimeMs: Date.now() - startTime
        });
        return processed;
    };
    WakeWordDetectionService.prototype.analyzeAudioPatterns = function (audioBuffer, patterns, keyword) {
        var samples = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
        var bestMatch = 0;
        var matchStart = 0;
        var matchEnd = 0;
        // Convert audio to energy envelope for pattern matching
        var energyEnvelope = this.calculateEnergyEnvelope(samples);
        for (var i = 0; i < energyEnvelope.length - 20; i++) {
            var windowSize = Math.min(50, energyEnvelope.length - i);
            var window_3 = energyEnvelope.slice(i, i + windowSize);
            for (var _i = 0, patterns_1 = patterns; _i < patterns_1.length; _i++) {
                var pattern = patterns_1[_i];
                var confidence = this.matchPattern(window_3, pattern.pattern, pattern.threshold);
                if (confidence > bestMatch && confidence > this.confidenceThreshold) {
                    bestMatch = confidence;
                    matchStart = i;
                    matchEnd = i + windowSize;
                }
            }
        }
        var detected = bestMatch > this.confidenceThreshold;
        if (detected) {
            logger_1.logger.info("[WakeWordDetectionService] Wake word \"".concat(keyword, "\" detected with confidence ").concat(bestMatch.toFixed(3)));
        }
        return {
            detected: detected,
            confidence: bestMatch,
            keyword: keyword,
            startTime: (matchStart / this.sampleRate) * 1000,
            endTime: (matchEnd / this.sampleRate) * 1000
        };
    };
    WakeWordDetectionService.prototype.calculateEnergyEnvelope = function (samples, windowSize) {
        if (windowSize === void 0) { windowSize = 1024; }
        var envelope = [];
        for (var i = 0; i < samples.length; i += windowSize) {
            var window_4 = samples.slice(i, i + windowSize);
            var energy = 0;
            for (var j = 0; j < window_4.length; j++) {
                energy += window_4[j] * window_4[j];
            }
            envelope.push(Math.sqrt(energy / window_4.length) / 32767);
        }
        return envelope;
    };
    WakeWordDetectionService.prototype.matchPattern = function (signal, pattern, threshold) {
        if (signal.length < pattern.length) {
            return 0;
        }
        var bestCorrelation = 0;
        for (var offset = 0; offset <= signal.length - pattern.length; offset++) {
            var correlation = 0;
            var patternMagnitude = 0;
            var signalMagnitude = 0;
            for (var i = 0; i < pattern.length; i++) {
                var signalValue = signal[offset + i];
                var patternValue = pattern[i];
                correlation += signalValue * patternValue;
                patternMagnitude += patternValue * patternValue;
                signalMagnitude += signalValue * signalValue;
            }
            // Normalized cross-correlation
            var normalizedCorrelation = correlation / (Math.sqrt(patternMagnitude * signalMagnitude) + 1e-10);
            bestCorrelation = Math.max(bestCorrelation, normalizedCorrelation);
        }
        return Math.max(0, bestCorrelation);
    };
    WakeWordDetectionService.prototype.createNegativeResult = function (keyword, startTime) {
        return {
            detected: false,
            confidence: 0,
            keyword: keyword,
            startTime: 0,
            endTime: 0
        };
    };
    WakeWordDetectionService.prototype.updateConfidenceThreshold = function (newThreshold) {
        var oldThreshold = this.confidenceThreshold;
        this.confidenceThreshold = Math.max(0.1, Math.min(0.95, newThreshold));
        logger_1.logger.info("[WakeWordDetectionService] \uD83C\uDF9A\uFE0F Updated confidence threshold", {
            oldThreshold: oldThreshold,
            newThreshold: this.confidenceThreshold,
            requested: newThreshold,
            clamped: newThreshold !== this.confidenceThreshold
        });
    };
    WakeWordDetectionService.prototype.addCustomPattern = function (keyword, patterns) {
        var normalizedKeyword = keyword.toLowerCase();
        var existingPatterns = this.wakeWordPatterns.has(normalizedKeyword);
        this.wakeWordPatterns.set(normalizedKeyword, patterns);
        logger_1.logger.info("[WakeWordDetectionService] \uD83C\uDFA4 ".concat(existingPatterns ? 'Updated' : 'Added', " custom patterns"), {
            keyword: normalizedKeyword,
            patternCount: patterns.length,
            patterns: patterns.map(function (p, idx) { return ({
                index: idx,
                patternLength: p.pattern.length,
                threshold: p.threshold,
                minLength: p.minLength,
                maxLength: p.maxLength
            }); }),
            totalKeywords: this.wakeWordPatterns.size
        });
    };
    WakeWordDetectionService.prototype.getSupportedKeywords = function () {
        return Array.from(this.wakeWordPatterns.keys());
    };
    // Cost optimization controls
    WakeWordDetectionService.prototype.enableProcessing = function () {
        this.processingEnabled = true;
        logger_1.logger.info('[WakeWordDetectionService] ✅ Wake word processing ENABLED');
    };
    WakeWordDetectionService.prototype.disableProcessing = function () {
        this.processingEnabled = false;
        logger_1.logger.info('[WakeWordDetectionService] ❌ Wake word processing DISABLED - saving compute costs');
    };
    WakeWordDetectionService.prototype.setCostOptimizationMode = function (enabled) {
        this.costOptimizationMode = enabled;
        logger_1.logger.info("[WakeWordDetectionService] Cost optimization mode: ".concat(enabled ? 'ENABLED' : 'DISABLED'));
    };
    WakeWordDetectionService.prototype.getProcessingStats = function () {
        return {
            enabled: this.processingEnabled,
            costOptimization: this.costOptimizationMode,
            confidenceThreshold: this.confidenceThreshold,
            supportedKeywords: this.wakeWordPatterns.size
        };
    };
    return WakeWordDetectionService;
}());
exports.WakeWordDetectionService = WakeWordDetectionService;
