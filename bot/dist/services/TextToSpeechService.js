"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TextToSpeechService = void 0;
const elevenlabs_js_1 = require("@elevenlabs/elevenlabs-js");
const stream_1 = require("stream");
const logger_1 = require("./logger");
class TextToSpeechService {
    client = null;
    voiceId;
    modelId;
    enabled;
    constructor(config = {}) {
        this.enabled = config.enabled ?? process.env.TTS_ENABLED === 'true';
        this.voiceId = config.voiceId ?? process.env.ELEVENLABS_VOICE_ID ?? 'ErXwobaYiN019PkySvjV';
        this.modelId = config.modelId ?? process.env.ELEVENLABS_MODEL_ID ?? 'eleven_monolingual_v1';
        if (this.enabled) {
            const apiKey = config.apiKey ?? process.env.ELEVENLABS_API_KEY;
            if (!apiKey) {
                logger_1.logger.warn('[TTS] ElevenLabs API key not provided, TTS will be disabled');
                this.enabled = false;
            }
            else {
                this.client = new elevenlabs_js_1.ElevenLabsClient({ apiKey });
                logger_1.logger.info('[TTS] Text-to-Speech service initialized with ElevenLabs');
            }
        }
        else {
            logger_1.logger.info('[TTS] Text-to-Speech service disabled');
        }
    }
    isEnabled() {
        return this.enabled && this.client !== null;
    }
    async generateSpeech(text) {
        if (!this.isEnabled() || !this.client) {
            logger_1.logger.debug('[TTS] Service disabled or not initialized, skipping TTS generation');
            return null;
        }
        try {
            logger_1.logger.info(`[TTS] Generating speech for text: "${text}"`);
            const audioStream = await this.client.textToSpeech.stream(this.voiceId, {
                modelId: this.modelId,
                text,
                voiceSettings: {
                    stability: 0.75,
                    similarityBoost: 0.85,
                    style: 0.5,
                    useSpeakerBoost: true
                }
            });
            const readable = stream_1.Readable.from(audioStream);
            logger_1.logger.info('[TTS] Speech generation successful');
            return readable;
        }
        catch (error) {
            logger_1.logger.error('[TTS] Failed to generate speech:', error);
            return null;
        }
    }
    async preloadVoice() {
        if (!this.isEnabled() || !this.client)
            return;
        try {
            await this.generateSpeech('Test');
            logger_1.logger.info('[TTS] Voice preloaded successfully');
        }
        catch (error) {
            logger_1.logger.error('[TTS] Failed to preload voice:', error);
        }
    }
    async getAvailableVoices() {
        if (!this.isEnabled() || !this.client)
            return [];
        try {
            const voices = await this.client.voices.getAll();
            return voices.voices;
        }
        catch (error) {
            logger_1.logger.error('[TTS] Failed to get available voices:', error);
            return [];
        }
    }
    setVoice(voiceId) {
        this.voiceId = voiceId;
        logger_1.logger.info(`[TTS] Voice changed to: ${voiceId}`);
    }
    setEnabled(enabled) {
        if (enabled && !this.client && process.env.ELEVENLABS_API_KEY) {
            this.client = new elevenlabs_js_1.ElevenLabsClient({ apiKey: process.env.ELEVENLABS_API_KEY });
        }
        this.enabled = enabled && this.client !== null;
        logger_1.logger.info(`[TTS] Service ${this.enabled ? 'enabled' : 'disabled'}`);
    }
}
exports.TextToSpeechService = TextToSpeechService;
//# sourceMappingURL=TextToSpeechService.js.map