"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpeechRecognitionService = void 0;
const openai_1 = __importDefault(require("openai"));
const logger_1 = require("./logger");
const fs_1 = require("fs");
const path_1 = require("path");
const os_1 = require("os");
class SpeechRecognitionService {
    openai = null;
    isEnabled;
    costSummaryInterval = null;
    costAlertThresholds = {
        daily: 10.00,
        hourly: 1.00,
        total: 50.00
    };
    lastAlertTime = 0;
    costTracker = {
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
            this.openai = new openai_1.default({
                apiKey: apiKey
            });
            logger_1.logger.info('[SpeechRecognitionService] 💰 OpenAI Whisper API enabled - will track costs');
            logger_1.logger.info(`[SpeechRecognitionService] Session started at ${new Date().toISOString()}`);
            logger_1.logger.info(`[SpeechRecognitionService] Whisper API pricing: $0.006/minute`);
            this.costSummaryInterval = setInterval(() => {
                if (this.costTracker.totalRequests > 0) {
                    logger_1.logger.info('[SpeechRecognitionService] 📊 === PERIODIC COST REPORT ===');
                    this.logCostSummary();
                }
            }, 30 * 60 * 1000);
        }
        else {
            logger_1.logger.warn('[SpeechRecognitionService] ⚠️ OpenAI API key not provided. Speech recognition will be disabled.');
        }
    }
    async transcribeAudio(audioBuffer, language = 'en') {
        if (!this.isEnabled || !this.openai) {
            logger_1.logger.error('[SpeechRecognitionService] ❌ Attempted to transcribe but service is disabled');
            throw new Error('Speech recognition is disabled. OpenAI API key not configured.');
        }
        const startTime = Date.now();
        const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(7)}`;
        try {
            const audioDurationMinutes = audioBuffer.length / (48000 * 2 * 2 * 60);
            const estimatedCost = audioDurationMinutes * 0.006;
            logger_1.logger.info(`[SpeechRecognitionService] 💰 === WHISPER API CALL START === [${requestId}]`);
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Audio size: ${(audioBuffer.length / 1024 / 1024).toFixed(2)}MB`);
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Duration: ${audioDurationMinutes.toFixed(2)} minutes`);
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Estimated cost: $${estimatedCost.toFixed(4)}`);
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Language: ${language}`);
            const tempFilePath = (0, path_1.join)((0, os_1.tmpdir)(), `voice_${Date.now()}.wav`);
            (0, fs_1.writeFileSync)(tempFilePath, audioBuffer);
            logger_1.logger.debug(`[SpeechRecognitionService] Temp file created: ${tempFilePath}`);
            logger_1.logger.info(`[SpeechRecognitionService] 🔄 Calling Whisper API... [${requestId}]`);
            const apiCallStart = Date.now();
            const transcription = await this.openai.audio.transcriptions.create({
                file: (0, fs_1.createReadStream)(tempFilePath),
                model: 'whisper-1',
                language: language,
                response_format: 'verbose_json',
                temperature: 0.0
            });
            const apiResponseTime = Date.now() - apiCallStart;
            logger_1.logger.info(`[SpeechRecognitionService] 📡 API response received in ${apiResponseTime}ms [${requestId}]`);
            (0, fs_1.unlinkSync)(tempFilePath);
            logger_1.logger.debug(`[SpeechRecognitionService] Temp file cleaned up: ${tempFilePath}`);
            const processingTime = Date.now() - startTime;
            this.costTracker.totalRequests++;
            this.costTracker.successfulTranscriptions++;
            this.costTracker.totalMinutesProcessed += audioDurationMinutes;
            this.costTracker.estimatedCost += estimatedCost;
            this.costTracker.lastRequestTime = Date.now();
            this.costTracker.totalResponseTimeMs += processingTime;
            const segments = transcription.segments || [];
            const avgLogprob = segments.length > 0
                ? segments.reduce((sum, seg) => sum + (seg.avg_logprob || 0), 0) / segments.length
                : 0;
            const estimatedConfidence = Math.min(0.99, Math.max(0.1, 0.95 + (avgLogprob * 0.1)));
            const result = {
                text: transcription.text,
                confidence: estimatedConfidence,
                isPartial: false,
                language: transcription.language || language,
                processingTimeMs: processingTime,
                alternatives: []
            };
            logger_1.logger.info(`[SpeechRecognitionService] ✅ === TRANSCRIPTION SUCCESS === [${requestId}]`);
            logger_1.logger.info(`[SpeechRecognitionService] ✅ Text: "${result.text}"`);
            logger_1.logger.info(`[SpeechRecognitionService] ✅ Confidence: ${(result.confidence * 100).toFixed(1)}%`);
            logger_1.logger.info(`[SpeechRecognitionService] ✅ Detected language: ${result.language}`);
            logger_1.logger.info(`[SpeechRecognitionService] ✅ Processing time: ${processingTime}ms (API: ${apiResponseTime}ms)`);
            logger_1.logger.info(`[SpeechRecognitionService] ✅ Cost: $${estimatedCost.toFixed(4)}`);
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Running total: $${this.costTracker.estimatedCost.toFixed(4)} (${this.costTracker.totalRequests} requests)`);
            this.checkCostAlerts();
            return result;
        }
        catch (error) {
            const processingTime = Date.now() - startTime;
            this.costTracker.totalRequests++;
            this.costTracker.failedTranscriptions++;
            this.costTracker.totalResponseTimeMs += processingTime;
            const audioDurationMinutes = audioBuffer.length / (48000 * 2 * 2 * 60);
            const estimatedCost = audioDurationMinutes * 0.006;
            this.costTracker.totalMinutesProcessed += audioDurationMinutes;
            this.costTracker.estimatedCost += estimatedCost;
            this.costTracker.lastRequestTime = Date.now();
            logger_1.logger.error(`[SpeechRecognitionService] ❌ === TRANSCRIPTION FAILED === [${requestId}]`);
            logger_1.logger.error(`[SpeechRecognitionService] ❌ Error type: ${error instanceof Error ? error.constructor.name : 'Unknown'}`);
            logger_1.logger.error(`[SpeechRecognitionService] ❌ Error message: ${error instanceof Error ? error.message : String(error)}`);
            if (error instanceof Error && error.stack) {
                logger_1.logger.error(`[SpeechRecognitionService] ❌ Stack trace:\n${error.stack}`);
            }
            logger_1.logger.error(`[SpeechRecognitionService] ❌ Failed after: ${processingTime}ms`);
            logger_1.logger.error(`[SpeechRecognitionService] ❌ Cost incurred: $${estimatedCost.toFixed(4)} (API charges even for failures)`);
            logger_1.logger.error(`[SpeechRecognitionService] 💰 Running total: $${this.costTracker.estimatedCost.toFixed(4)} (${this.costTracker.failedTranscriptions} failures)`);
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
    async transcribeAudioStream(audioBuffer) {
        return this.transcribeAudio(audioBuffer);
    }
    isServiceEnabled() {
        return this.isEnabled;
    }
    parseVoiceCommand(transcriptionText) {
        const text = transcriptionText.toLowerCase().trim();
        logger_1.logger.info(`[SpeechRecognitionService] 🎯 Parsing command from: "${transcriptionText}"`);
        const cleanText = text.replace(/^kanye\s+/i, '');
        logger_1.logger.debug(`[SpeechRecognitionService] Clean text after wake word removal: "${cleanText}"`);
        let result;
        if (cleanText.startsWith('play ')) {
            result = {
                command: 'play',
                parameters: [cleanText.substring(5).trim()]
            };
        }
        else if (cleanText.includes('skip') || cleanText.includes('next')) {
            result = {
                command: 'skip',
                parameters: []
            };
        }
        else if (cleanText.includes('stop') || cleanText.includes('quit')) {
            result = {
                command: 'stop',
                parameters: []
            };
        }
        else if (cleanText.includes('pause')) {
            result = {
                command: 'pause',
                parameters: []
            };
        }
        else if (cleanText.includes('resume') || cleanText.includes('continue')) {
            result = {
                command: 'resume',
                parameters: []
            };
        }
        else if (cleanText.includes('queue') || cleanText.includes('what\'s playing')) {
            result = {
                command: 'queue',
                parameters: []
            };
        }
        else {
            result = {
                command: 'play',
                parameters: [cleanText]
            };
        }
        logger_1.logger.info(`[SpeechRecognitionService] 🎯 Parsed command: ${result.command}${result.parameters.length > 0 ? ` with params: ["${result.parameters.join('", "')}"]` : ' (no params)'}`);
        return result;
    }
    getCostStats() {
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
    resetCostTracking() {
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
        logger_1.logger.info('[SpeechRecognitionService] 🔄 === COST TRACKING RESET ===');
        logger_1.logger.info(`[SpeechRecognitionService] 🔄 Previous session stats:`);
        logger_1.logger.info(`[SpeechRecognitionService] 🔄   - Total cost: $${previousStats.estimatedCost.toFixed(4)}`);
        logger_1.logger.info(`[SpeechRecognitionService] 🔄   - Requests: ${previousStats.totalRequests} (${previousStats.successfulTranscriptions} ✅, ${previousStats.failedTranscriptions} ❌)`);
        logger_1.logger.info(`[SpeechRecognitionService] 🔄   - Success rate: ${previousStats.successRate.toFixed(1)}%`);
        logger_1.logger.info(`[SpeechRecognitionService] 🔄   - Session duration: ${previousStats.sessionDurationMinutes.toFixed(1)} minutes`);
        logger_1.logger.info(`[SpeechRecognitionService] 🔄 New session started at ${new Date().toISOString()}`);
    }
    logCostSummary() {
        const stats = this.getCostStats();
        logger_1.logger.info('[SpeechRecognitionService] 💰 === WHISPER API COST SUMMARY ===');
        logger_1.logger.info(`[SpeechRecognitionService] 💰 Session Duration: ${stats.sessionDurationMinutes.toFixed(1)} minutes`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰 Total Requests: ${stats.totalRequests}`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰   - Successful: ${stats.successfulTranscriptions} ✅`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰   - Failed: ${stats.failedTranscriptions} ❌`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰   - Success Rate: ${stats.successRate.toFixed(1)}%`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰 Audio Processed: ${stats.totalMinutesProcessed.toFixed(2)} minutes`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰 Total Cost: $${stats.estimatedCost.toFixed(4)}`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰 Average Cost/Request: $${stats.averageCostPerRequest.toFixed(4)}`);
        logger_1.logger.info(`[SpeechRecognitionService] 💰 Average Response Time: ${stats.averageResponseTimeMs.toFixed(0)}ms`);
        if (stats.lastRequestTime > 0) {
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Last Request: ${new Date(stats.lastRequestTime).toISOString()}`);
        }
        if (stats.sessionDurationMinutes > 0 && stats.totalRequests > 0) {
            const requestsPerHour = (stats.totalRequests / stats.sessionDurationMinutes) * 60;
            const costPerHour = (stats.estimatedCost / stats.sessionDurationMinutes) * 60;
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Current Rate: ${requestsPerHour.toFixed(1)} requests/hour = $${costPerHour.toFixed(2)}/hour`);
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Projected Daily Cost (24h): $${(costPerHour * 24).toFixed(2)}`);
            logger_1.logger.info(`[SpeechRecognitionService] 💰 Projected Monthly Cost (30d): $${(costPerHour * 24 * 30).toFixed(2)}`);
        }
        logger_1.logger.info('[SpeechRecognitionService] 💰 ================================');
    }
    cleanup() {
        if (this.costSummaryInterval) {
            clearInterval(this.costSummaryInterval);
            this.costSummaryInterval = null;
            logger_1.logger.info('[SpeechRecognitionService] 🧹 Cleaned up periodic cost reporting');
        }
        if (this.costTracker.totalRequests > 0) {
            logger_1.logger.info('[SpeechRecognitionService] 📊 === FINAL COST REPORT (Service Shutdown) ===');
            this.logCostSummary();
        }
    }
    checkCostAlerts() {
        const now = Date.now();
        const timeSinceLastAlert = now - this.lastAlertTime;
        if (timeSinceLastAlert < 60 * 60 * 1000) {
            return;
        }
        const stats = this.getCostStats();
        if (stats.estimatedCost >= this.costAlertThresholds.total) {
            logger_1.logger.warn(`[SpeechRecognitionService] 🚨 COST ALERT: Total cost ($${stats.estimatedCost.toFixed(2)}) exceeds threshold ($${this.costAlertThresholds.total})!`);
            this.lastAlertTime = now;
            return;
        }
        if (stats.sessionDurationMinutes > 60) {
            const costPerHour = (stats.estimatedCost / stats.sessionDurationMinutes) * 60;
            if (costPerHour >= this.costAlertThresholds.hourly) {
                logger_1.logger.warn(`[SpeechRecognitionService] 🚨 COST ALERT: Hourly rate ($${costPerHour.toFixed(2)}/hour) exceeds threshold ($${this.costAlertThresholds.hourly}/hour)!`);
                this.lastAlertTime = now;
                return;
            }
        }
        if (stats.sessionDurationMinutes > 30 && stats.totalRequests > 0) {
            const requestsPerHour = (stats.totalRequests / stats.sessionDurationMinutes) * 60;
            const costPerHour = (stats.estimatedCost / stats.sessionDurationMinutes) * 60;
            const projectedDailyCost = costPerHour * 24;
            if (projectedDailyCost >= this.costAlertThresholds.daily) {
                logger_1.logger.warn(`[SpeechRecognitionService] 🚨 COST ALERT: Projected daily cost ($${projectedDailyCost.toFixed(2)}) exceeds threshold ($${this.costAlertThresholds.daily})!`);
                logger_1.logger.warn(`[SpeechRecognitionService] 🚨 Current rate: ${requestsPerHour.toFixed(1)} requests/hour`);
                this.lastAlertTime = now;
            }
        }
    }
}
exports.SpeechRecognitionService = SpeechRecognitionService;
//# sourceMappingURL=SpeechRecognitionService.js.map