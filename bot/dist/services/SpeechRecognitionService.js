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
    costTracker = {
        totalRequests: 0,
        totalMinutesProcessed: 0,
        estimatedCost: 0,
        lastRequestTime: 0
    };
    constructor() {
        const apiKey = process.env.OPENAI_API_KEY;
        this.isEnabled = !!apiKey;
        if (this.isEnabled) {
            this.openai = new openai_1.default({
                apiKey: apiKey
            });
            logger_1.logger.info('[SpeechRecognitionService] 💰 OpenAI Whisper API enabled - will track costs');
        }
        else {
            logger_1.logger.warn('OpenAI API key not provided. Speech recognition will be disabled.');
        }
    }
    async transcribeAudio(audioBuffer, language = 'en') {
        if (!this.isEnabled || !this.openai) {
            throw new Error('Speech recognition is disabled. OpenAI API key not configured.');
        }
        const startTime = Date.now();
        try {
            const audioDurationMinutes = audioBuffer.length / (48000 * 2 * 2 * 60);
            const estimatedCost = audioDurationMinutes * 0.006;
            logger_1.logger.info(`[SpeechRecognitionService] 🚨 PROCESSING WITH WHISPER API - Duration: ${audioDurationMinutes.toFixed(2)}min, Est. Cost: $${estimatedCost.toFixed(4)}`);
            const tempFilePath = (0, path_1.join)((0, os_1.tmpdir)(), `voice_${Date.now()}.wav`);
            (0, fs_1.writeFileSync)(tempFilePath, audioBuffer);
            const transcription = await this.openai.audio.transcriptions.create({
                file: (0, fs_1.createReadStream)(tempFilePath),
                model: 'whisper-1',
                language: language,
                response_format: 'verbose_json',
                temperature: 0.0
            });
            (0, fs_1.unlinkSync)(tempFilePath);
            const processingTime = Date.now() - startTime;
            this.costTracker.totalRequests++;
            this.costTracker.totalMinutesProcessed += audioDurationMinutes;
            this.costTracker.estimatedCost += estimatedCost;
            this.costTracker.lastRequestTime = Date.now();
            const result = {
                text: transcription.text,
                confidence: 0.95,
                isPartial: false,
                language: transcription.language || language,
                processingTimeMs: processingTime,
                alternatives: []
            };
            logger_1.logger.info(`[SpeechRecognitionService] ✅ SUCCESS: "${result.text}" in ${processingTime}ms | Total Cost So Far: $${this.costTracker.estimatedCost.toFixed(4)}`);
            return result;
        }
        catch (error) {
            const processingTime = Date.now() - startTime;
            logger_1.logger.error('[SpeechRecognitionService] ❌ TRANSCRIPTION FAILED (cost still incurred):', error);
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
        const cleanText = text.replace(/^kanye\s+/i, '');
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
        return {
            command: 'play',
            parameters: [cleanText]
        };
    }
    getCostStats() {
        return {
            ...this.costTracker,
            averageCostPerRequest: this.costTracker.totalRequests > 0
                ? this.costTracker.estimatedCost / this.costTracker.totalRequests
                : 0
        };
    }
    resetCostTracking() {
        this.costTracker = {
            totalRequests: 0,
            totalMinutesProcessed: 0,
            estimatedCost: 0,
            lastRequestTime: 0
        };
        logger_1.logger.info('[SpeechRecognitionService] Cost tracking reset');
    }
    logCostSummary() {
        const stats = this.getCostStats();
        logger_1.logger.info(`[SpeechRecognitionService] 💰 COST SUMMARY:
      - Total Requests: ${stats.totalRequests}
      - Total Minutes: ${stats.totalMinutesProcessed.toFixed(2)}
      - Estimated Cost: $${stats.estimatedCost.toFixed(4)}
      - Avg Cost/Request: $${stats.averageCostPerRequest.toFixed(4)}
      - Last Request: ${new Date(stats.lastRequestTime).toISOString()}`);
    }
}
exports.SpeechRecognitionService = SpeechRecognitionService;
//# sourceMappingURL=SpeechRecognitionService.js.map