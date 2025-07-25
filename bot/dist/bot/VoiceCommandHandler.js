"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.VoiceCommandHandler = void 0;
const events_1 = require("events");
const voice_1 = require("@discordjs/voice");
const VoiceListenerService_1 = require("../services/VoiceListenerService");
const WakeWordDetectionService_1 = require("../services/WakeWordDetectionService");
const SpeechRecognitionService_1 = require("../services/SpeechRecognitionService");
const AudioProcessingService_1 = require("../services/AudioProcessingService");
const TextToSpeechService_1 = require("../services/TextToSpeechService");
const KanyeResponseGenerator_1 = require("../services/KanyeResponseGenerator");
const logger_1 = require("../services/logger");
class VoiceCommandHandler extends events_1.EventEmitter {
    voiceListener;
    wakeWordDetector;
    speechRecognition;
    textToSpeech;
    responseGenerator;
    processingQueues = new Map();
    activeProcessing = new Map();
    voiceConnections = new Map();
    constructor() {
        super();
        this.voiceListener = new VoiceListenerService_1.VoiceListenerService();
        this.wakeWordDetector = new WakeWordDetectionService_1.WakeWordDetectionService(0.7);
        this.speechRecognition = new SpeechRecognitionService_1.SpeechRecognitionService();
        this.textToSpeech = new TextToSpeechService_1.TextToSpeechService();
        this.responseGenerator = new KanyeResponseGenerator_1.KanyeResponseGenerator();
        this.setupEventHandlers();
    }
    setupEventHandlers() {
        this.voiceListener.on('audioSegment', (segment) => {
            this.handleAudioSegment(segment);
        });
        this.voiceListener.on('speakingStart', (data) => {
            logger_1.logger.debug(`[VoiceCommandHandler] User ${data.userId} started speaking in guild ${data.guildId}`);
        });
        this.voiceListener.on('speakingEnd', (data) => {
            logger_1.logger.debug(`[VoiceCommandHandler] User ${data.userId} stopped speaking in guild ${data.guildId}`);
        });
    }
    async startListening(voiceChannel, connection) {
        try {
            await this.voiceListener.startListening(connection, voiceChannel);
            this.voiceConnections.set(voiceChannel.guild.id, connection);
            logger_1.logger.info(`[VoiceCommandHandler] Started voice command listening in ${voiceChannel.name}`);
            logger_1.logger.info(`[VoiceCommandHandler] TTS enabled: ${this.textToSpeech.isEnabled()}, attempting greeting`);
            const greeting = this.responseGenerator.generateGreeting();
            logger_1.logger.info(`[VoiceCommandHandler] Generated greeting: "${greeting}"`);
            await this.playTTSResponse(voiceChannel.guild.id, greeting);
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Failed to start listening:', error);
            throw error;
        }
    }
    async stopListening(guildId) {
        try {
            await this.voiceListener.stopListening(guildId);
            this.processingQueues.delete(guildId);
            this.activeProcessing.delete(guildId);
            this.voiceConnections.delete(guildId);
            logger_1.logger.info(`[VoiceCommandHandler] Stopped voice command listening for guild ${guildId}`);
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Failed to stop listening:', error);
        }
    }
    async handleAudioSegment(segment) {
        const queueKey = `${segment.guildId}_${segment.userId}`;
        if (!this.processingQueues.has(queueKey)) {
            this.processingQueues.set(queueKey, []);
        }
        this.processingQueues.get(queueKey).push(segment);
        if (!this.activeProcessing.get(queueKey)) {
            this.processAudioQueue(queueKey);
        }
    }
    async processAudioQueue(queueKey) {
        this.activeProcessing.set(queueKey, true);
        try {
            const queue = this.processingQueues.get(queueKey);
            if (!queue || queue.length === 0) {
                return;
            }
            while (queue.length > 0) {
                const segment = queue.shift();
                await this.processAudioSegment(segment);
            }
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Error processing audio queue:', error);
        }
        finally {
            this.activeProcessing.set(queueKey, false);
        }
    }
    async processAudioSegment(segment) {
        try {
            const wakeWordResult = await this.detectWakeWord(segment);
            if (!wakeWordResult.detected) {
                logger_1.logger.debug(`[VoiceCommandHandler] No wake word detected for user ${segment.userId}, skipping expensive processing`);
                return;
            }
            logger_1.logger.info(`[VoiceCommandHandler] 🎙️ Wake word "Kanye" detected! Starting full processing for user ${segment.userId} (confidence: ${wakeWordResult.confidence})`);
            segment.isWakeWordDetected = true;
            segment.wakeWordConfidence = wakeWordResult.confidence;
            await this.captureCommandAudio(segment);
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Error processing audio segment:', error);
        }
    }
    async captureCommandAudio(wakeWordSegment) {
        logger_1.logger.info(`[VoiceCommandHandler] 🎤 Playing acknowledgment for wake word detection...`);
        const acknowledgment = this.responseGenerator.generateAcknowledgment();
        await this.playTTSResponse(wakeWordSegment.guildId, acknowledgment);
        logger_1.logger.info(`[VoiceCommandHandler] 👂 Listening for command after wake word... (12 second timeout)`);
        const commandAudioBuffer = [];
        let commandStartTime = Date.now();
        let commandCaptureTimeout = null;
        const onNextAudio = async (nextSegment) => {
            if (nextSegment.userId === wakeWordSegment.userId &&
                nextSegment.guildId === wakeWordSegment.guildId &&
                Date.now() - commandStartTime < 12000) {
                const wakeWordCheck = await this.detectWakeWord(nextSegment);
                if (wakeWordCheck.detected) {
                    logger_1.logger.info(`[VoiceCommandHandler] 🔄 Wake word "kanye" detected again! Resetting command capture timer`);
                    this.voiceListener.removeListener('audioSegment', onNextAudio);
                    if (commandCaptureTimeout) {
                        clearTimeout(commandCaptureTimeout);
                    }
                    const newAcknowledgment = this.responseGenerator.generateAcknowledgment();
                    await this.playTTSResponse(wakeWordSegment.guildId, newAcknowledgment);
                    await this.captureCommandAudio(nextSegment);
                    return;
                }
                if (commandCaptureTimeout) {
                    clearTimeout(commandCaptureTimeout);
                }
                commandAudioBuffer.push(nextSegment.audioData);
                const totalDuration = commandAudioBuffer.reduce((sum, buffer) => sum + (buffer.length / (48000 * 2 * 2)), 0);
                if (totalDuration >= 1.5) {
                    this.voiceListener.removeListener('audioSegment', onNextAudio);
                    const combinedCommandAudio = Buffer.concat(commandAudioBuffer);
                    const commandSegment = {
                        ...wakeWordSegment,
                        id: `command_${wakeWordSegment.id}`,
                        audioData: combinedCommandAudio,
                        duration: totalDuration,
                        timestamp: Date.now()
                    };
                    await this.processCommandWithWhisper(commandSegment);
                    return;
                }
                commandCaptureTimeout = setTimeout(() => {
                    logger_1.logger.warn(`[VoiceCommandHandler] Command capture timeout for user ${wakeWordSegment.userId} (12 seconds elapsed)`);
                    this.voiceListener.removeListener('audioSegment', onNextAudio);
                }, 3000);
            }
        };
        this.voiceListener.on('audioSegment', onNextAudio);
        setTimeout(() => {
            if (commandAudioBuffer.length === 0) {
                logger_1.logger.warn(`[VoiceCommandHandler] No command audio received within 12 seconds for user ${wakeWordSegment.userId}`);
                this.voiceListener.removeListener('audioSegment', onNextAudio);
            }
        }, 12000);
    }
    async processCommandWithWhisper(segment) {
        try {
            logger_1.logger.info(`[VoiceCommandHandler] 💰 Processing command with OpenAI Whisper (this costs money!)`);
            const costStatsBefore = this.speechRecognition.getCostStats();
            logger_1.logger.info(`[VoiceCommandHandler] 💰 Current session cost before processing: $${costStatsBefore.estimatedCost.toFixed(4)}`);
            const recognitionResult = await this.processSpeechRecognition(segment);
            if (!recognitionResult.text || recognitionResult.confidence < 0.5) {
                logger_1.logger.warn(`[VoiceCommandHandler] Low confidence speech recognition: "${recognitionResult.text}" (${recognitionResult.confidence})`);
                return;
            }
            const voiceCommand = await this.parseVoiceCommand(segment, recognitionResult);
            if (voiceCommand) {
                logger_1.logger.info(`[VoiceCommandHandler] ✅ Voice command parsed: ${voiceCommand.command} with parameters: [${voiceCommand.parameters.join(', ')}]`);
                const ttsContext = {
                    command: voiceCommand.command,
                    songTitle: voiceCommand.parameters.join(' ') || undefined
                };
                if (voiceCommand.command === 'play') {
                    await this.playTTSResponse(segment.guildId, this.responseGenerator.generateResponse({
                        command: 'play',
                        songTitle: undefined
                    }));
                }
                else {
                    await this.playTTSResponse(segment.guildId, this.responseGenerator.generateResponse(ttsContext));
                }
                this.emit('voiceCommand', voiceCommand);
            }
            else {
                logger_1.logger.warn(`[VoiceCommandHandler] Could not parse valid command from: "${recognitionResult.text}"`);
                await this.playTTSResponse(segment.guildId, this.responseGenerator.generateResponse({ command: 'unknown' }));
            }
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Error processing command with Whisper:', error);
        }
    }
    async detectWakeWord(segment) {
        try {
            const processedAudio = AudioProcessingService_1.AudioProcessingService.normalizeAudioLevel(segment.audioData, 0.8);
            const result = await this.wakeWordDetector.detectWakeWord(processedAudio, 'kanye');
            return result;
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Wake word detection failed:', error);
            return {
                detected: false,
                confidence: 0,
                keyword: 'kanye',
                startTime: 0,
                endTime: 0
            };
        }
    }
    async processSpeechRecognition(segment) {
        try {
            const wavAudio = AudioProcessingService_1.AudioProcessingService.pcmToWav(segment.audioData, segment.sampleRate, segment.channels, 16);
            const result = await this.speechRecognition.transcribeAudio(wavAudio, 'en');
            return result;
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Speech recognition failed:', error);
            return {
                text: '',
                confidence: 0,
                isPartial: false,
                language: 'en',
                processingTimeMs: 0,
                alternatives: []
            };
        }
    }
    async parseVoiceCommand(segment, recognitionResult) {
        try {
            const { command, parameters } = this.speechRecognition.parseVoiceCommand(recognitionResult.text);
            if (!command) {
                return null;
            }
            const voiceCommand = {
                id: `voice_${segment.id}`,
                userId: segment.userId,
                guildId: segment.guildId,
                command,
                parameters,
                confidence: recognitionResult.confidence,
                timestamp: segment.timestamp,
                processingTimeMs: recognitionResult.processingTimeMs
            };
            return voiceCommand;
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] Failed to parse voice command:', error);
            return null;
        }
    }
    isListening(guildId) {
        return this.voiceListener.isListening(guildId);
    }
    getActiveGuilds() {
        return this.voiceListener.getActiveGuilds();
    }
    updateWakeWordThreshold(threshold) {
        this.wakeWordDetector.updateConfidenceThreshold(threshold);
        logger_1.logger.info(`[VoiceCommandHandler] Updated wake word threshold to ${threshold}`);
    }
    getSupportedCommands() {
        return ['play', 'skip', 'stop', 'pause', 'resume', 'queue'];
    }
    getProcessingStats() {
        const queuedSegments = Array.from(this.processingQueues.values())
            .reduce((total, queue) => total + queue.length, 0);
        const activeProcessingCount = Array.from(this.activeProcessing.values())
            .filter(active => active).length;
        return {
            activeGuilds: this.voiceListener.getActiveGuilds().length,
            queuedSegments,
            activeProcessing: activeProcessingCount,
            sessionCount: this.voiceListener.getSessionCount()
        };
    }
    createVoiceSession(guildId, userId, channelId) {
        return this.voiceListener.createVoiceSession(guildId, userId, channelId);
    }
    getActiveSession(guildId, userId) {
        return this.voiceListener.getActiveSession(guildId, userId);
    }
    getCostStats() {
        return this.speechRecognition.getCostStats();
    }
    logCostSummary() {
        this.speechRecognition.logCostSummary();
    }
    resetCostTracking() {
        this.speechRecognition.resetCostTracking();
    }
    getWakeWordStats() {
        return this.wakeWordDetector.getProcessingStats();
    }
    async healthCheck() {
        const services = {
            voiceListener: this.voiceListener !== null,
            wakeWordDetection: this.wakeWordDetector !== null,
            speechRecognition: this.speechRecognition.isServiceEnabled()
        };
        const stats = this.getProcessingStats();
        const costStats = this.getCostStats();
        const wakeWordStats = this.getWakeWordStats();
        const healthyServices = Object.values(services).filter(Boolean).length;
        const totalServices = Object.values(services).length;
        let status;
        if (healthyServices === totalServices) {
            status = 'healthy';
        }
        else if (healthyServices > 0) {
            status = 'degraded';
        }
        else {
            status = 'unhealthy';
        }
        return {
            status,
            services,
            stats,
            costOptimization: {
                wakeWordFirst: true,
                costTracking: costStats,
                wakeWordStats
            }
        };
    }
    async playTTSResponse(guildId, text) {
        logger_1.logger.info(`[VoiceCommandHandler] playTTSResponse called - guildId: ${guildId}, text: "${text}"`);
        if (!this.textToSpeech.isEnabled()) {
            logger_1.logger.warn('[VoiceCommandHandler] TTS disabled, skipping response');
            return;
        }
        logger_1.logger.info(`[VoiceCommandHandler] Looking for voice connection in guild ${guildId}`);
        logger_1.logger.info(`[VoiceCommandHandler] Available connections: ${Array.from(this.voiceConnections.keys()).join(', ')}`);
        const connection = this.voiceConnections.get(guildId);
        if (!connection) {
            logger_1.logger.error(`[VoiceCommandHandler] No voice connection for guild ${guildId}, cannot play TTS`);
            return;
        }
        logger_1.logger.info(`[VoiceCommandHandler] Voice connection found for guild ${guildId}`);
        try {
            logger_1.logger.info('[VoiceCommandHandler] Generating TTS audio stream...');
            const audioStream = await this.textToSpeech.generateSpeech(text);
            if (!audioStream) {
                logger_1.logger.error('[VoiceCommandHandler] Failed to generate TTS audio - audioStream is null');
                return;
            }
            logger_1.logger.info('[VoiceCommandHandler] TTS audio stream generated successfully');
            const resource = (0, voice_1.createAudioResource)(audioStream, {
                inputType: voice_1.StreamType.Arbitrary,
                inlineVolume: true
            });
            logger_1.logger.info(`[VoiceCommandHandler] Getting audio player from connection...`);
            logger_1.logger.info(`[VoiceCommandHandler] Connection state: ${connection.state.status}`);
            logger_1.logger.info(`[VoiceCommandHandler] Connection has subscription: ${!!connection.state.subscription}`);
            const player = connection.state.subscription?.player;
            if (player) {
                logger_1.logger.info(`[VoiceCommandHandler] Audio player found, current state: ${player.state.status}`);
                const wasPlaying = player.state.status === 'playing';
                player.play(resource);
                await new Promise((resolve) => {
                    const onIdle = () => {
                        player.off('idle', onIdle);
                        resolve(undefined);
                    };
                    player.on('idle', onIdle);
                });
                logger_1.logger.info(`[VoiceCommandHandler] ✅ TTS response played successfully: "${text}"`);
            }
        }
        catch (error) {
            logger_1.logger.error('[VoiceCommandHandler] ❌ Error playing TTS response:', error);
            logger_1.logger.error('[VoiceCommandHandler] Error details:', error instanceof Error ? error.stack : 'Unknown error');
        }
    }
    async speakResponse(guildId, context) {
        logger_1.logger.info(`[VoiceCommandHandler] speakResponse called - guildId: ${guildId}, context:`, context);
        const response = this.responseGenerator.generateResponse(context);
        logger_1.logger.info(`[VoiceCommandHandler] Generated response: "${response}"`);
        await this.playTTSResponse(guildId, response);
    }
}
exports.VoiceCommandHandler = VoiceCommandHandler;
//# sourceMappingURL=VoiceCommandHandler.js.map