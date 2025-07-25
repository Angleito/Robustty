"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.VoiceListenerService = void 0;
const voice_1 = require("@discordjs/voice");
const events_1 = require("events");
const logger_1 = require("./logger");
class VoiceListenerService extends events_1.EventEmitter {
    receivers = new Map();
    sessions = new Map();
    bufferTimeout = 3000;
    maxBufferSize = 1024 * 1024;
    cleanupIntervals = new Map();
    constructor() {
        super();
        this.setupCleanupRoutine();
    }
    async startListening(connection, channel) {
        const guildId = channel.guild.id;
        try {
            logger_1.logger.info(`[VoiceListenerService] Starting voice listening for guild ${guildId}`);
            const receiver = {
                connection,
                channel,
                activeUsers: new Map(),
                audioBuffer: new Map(),
                lastActivity: new Map()
            };
            this.receivers.set(guildId, receiver);
            const voiceReceiver = connection.receiver;
            voiceReceiver.speaking.on('start', (userId) => {
                this.handleSpeakingStart(guildId, userId);
            });
            voiceReceiver.speaking.on('end', (userId) => {
                this.handleSpeakingEnd(guildId, userId);
            });
            this.setupUserAudioStreams(guildId, voiceReceiver);
            this.startCleanupRoutine(guildId);
            logger_1.logger.info(`[VoiceListenerService] Voice listening active for guild ${guildId}`);
            this.emit('listeningStarted', { guildId, channelId: channel.id });
        }
        catch (error) {
            logger_1.logger.error(`[VoiceListenerService] Failed to start listening in guild ${guildId}:`, error);
            throw error;
        }
    }
    setupUserAudioStreams(guildId, voiceReceiver) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        voiceReceiver.connection.on('stateChange', () => {
            setTimeout(() => this.refreshUserStreams(guildId), 1000);
        });
        this.refreshUserStreams(guildId);
    }
    refreshUserStreams(guildId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        const voiceReceiver = receiver.connection.receiver;
        receiver.channel.members.forEach((member) => {
            if (member.user.bot)
                return;
            const userId = member.user.id;
            if (!receiver.activeUsers.has(userId)) {
                receiver.activeUsers.set(userId, member.user);
                receiver.audioBuffer.set(userId, []);
                receiver.lastActivity.set(userId, Date.now());
                const audioStream = voiceReceiver.subscribe(userId, {
                    end: {
                        behavior: voice_1.EndBehaviorType.AfterSilence,
                        duration: 1000
                    }
                });
                this.setupAudioStreamHandlers(guildId, userId, audioStream);
                logger_1.logger.debug(`[VoiceListenerService] Started listening to user ${member.user.tag} in guild ${guildId}`);
            }
        });
    }
    setupAudioStreamHandlers(guildId, userId, audioStream) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        audioStream.on('data', (chunk) => {
            this.handleAudioData(guildId, userId, chunk);
        });
        audioStream.on('end', () => {
            this.processAudioBuffer(guildId, userId);
        });
        audioStream.on('error', (error) => {
            logger_1.logger.error(`[VoiceListenerService] Audio stream error for user ${userId} in guild ${guildId}:`, error);
        });
    }
    handleSpeakingStart(guildId, userId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        receiver.lastActivity.set(userId, Date.now());
        logger_1.logger.debug(`[VoiceListenerService] User ${userId} started speaking in guild ${guildId}`);
        this.emit('speakingStart', { guildId, userId });
    }
    handleSpeakingEnd(guildId, userId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        receiver.lastActivity.set(userId, Date.now());
        logger_1.logger.debug(`[VoiceListenerService] User ${userId} stopped speaking in guild ${guildId}`);
        this.emit('speakingEnd', { guildId, userId });
        setTimeout(() => {
            this.processAudioBuffer(guildId, userId);
        }, 500);
    }
    handleAudioData(guildId, userId, chunk) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        const userBuffer = receiver.audioBuffer.get(userId);
        if (!userBuffer)
            return;
        userBuffer.push(chunk);
        receiver.lastActivity.set(userId, Date.now());
        const totalSize = userBuffer.reduce((sum, buf) => sum + buf.length, 0);
        if (totalSize > this.maxBufferSize) {
            logger_1.logger.warn(`[VoiceListenerService] Buffer overflow for user ${userId}, processing early`);
            this.processAudioBuffer(guildId, userId);
        }
    }
    processAudioBuffer(guildId, userId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        const userBuffer = receiver.audioBuffer.get(userId);
        if (!userBuffer || userBuffer.length === 0)
            return;
        try {
            const combinedAudio = Buffer.concat(userBuffer);
            receiver.audioBuffer.set(userId, []);
            if (combinedAudio.length < 1600) {
                return;
            }
            const audioSegment = {
                id: `${guildId}_${userId}_${Date.now()}`,
                guildId,
                userId,
                audioData: combinedAudio,
                duration: combinedAudio.length / (48000 * 2 * 2),
                sampleRate: 48000,
                channels: 2,
                timestamp: Date.now(),
                isWakeWordDetected: false
            };
            logger_1.logger.debug(`[VoiceListenerService] Processed audio segment: ${audioSegment.duration.toFixed(2)}s from user ${userId}`);
            this.emit('audioSegment', audioSegment);
        }
        catch (error) {
            logger_1.logger.error(`[VoiceListenerService] Error processing audio buffer for user ${userId}:`, error);
        }
    }
    async stopListening(guildId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        try {
            logger_1.logger.info(`[VoiceListenerService] Stopping voice listening for guild ${guildId}`);
            receiver.audioBuffer.forEach((buffer, userId) => {
                if (buffer.length > 0) {
                    this.processAudioBuffer(guildId, userId);
                }
            });
            this.receivers.delete(guildId);
            this.stopCleanupRoutine(guildId);
            const sessionsToRemove = Array.from(this.sessions.entries())
                .filter(([_, session]) => session.guildId === guildId)
                .map(([sessionId]) => sessionId);
            sessionsToRemove.forEach(sessionId => {
                this.sessions.delete(sessionId);
            });
            logger_1.logger.info(`[VoiceListenerService] Voice listening stopped for guild ${guildId}`);
            this.emit('listeningStopped', { guildId });
        }
        catch (error) {
            logger_1.logger.error(`[VoiceListenerService] Error stopping voice listening for guild ${guildId}:`, error);
        }
    }
    createVoiceSession(guildId, userId, channelId) {
        const sessionId = `voice_${guildId}_${userId}_${Date.now()}`;
        const session = {
            sessionId,
            guildId,
            userId,
            channelId,
            isActive: true,
            startedAt: Date.now(),
            lastActivityAt: Date.now(),
            commandsProcessed: 0,
            currentState: 'idle'
        };
        this.sessions.set(sessionId, session);
        logger_1.logger.info(`[VoiceListenerService] Created voice session ${sessionId}`);
        return sessionId;
    }
    updateSessionState(sessionId, state) {
        const session = this.sessions.get(sessionId);
        if (session) {
            session.currentState = state;
            session.lastActivityAt = Date.now();
        }
    }
    getActiveSession(guildId, userId) {
        return Array.from(this.sessions.values())
            .find(session => session.guildId === guildId &&
            session.userId === userId &&
            session.isActive) || null;
    }
    setupCleanupRoutine() {
        setInterval(() => {
            this.cleanupInactiveSessions();
        }, 30000);
    }
    startCleanupRoutine(guildId) {
        this.stopCleanupRoutine(guildId);
        const interval = setInterval(() => {
            this.cleanupGuildBuffers(guildId);
        }, 10000);
        this.cleanupIntervals.set(guildId, interval);
    }
    stopCleanupRoutine(guildId) {
        const interval = this.cleanupIntervals.get(guildId);
        if (interval) {
            clearInterval(interval);
            this.cleanupIntervals.delete(guildId);
        }
    }
    cleanupGuildBuffers(guildId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        const now = Date.now();
        receiver.lastActivity.forEach((lastActivity, userId) => {
            if (now - lastActivity > this.bufferTimeout) {
                const buffer = receiver.audioBuffer.get(userId);
                if (buffer && buffer.length > 0) {
                    logger_1.logger.debug(`[VoiceListenerService] Cleaning up stale buffer for user ${userId}`);
                    this.processAudioBuffer(guildId, userId);
                }
            }
        });
    }
    cleanupInactiveSessions() {
        const now = Date.now();
        const sessionTimeout = 10 * 60 * 1000;
        Array.from(this.sessions.entries()).forEach(([sessionId, session]) => {
            if (now - session.lastActivityAt > sessionTimeout) {
                logger_1.logger.info(`[VoiceListenerService] Cleaning up inactive session ${sessionId}`);
                this.sessions.delete(sessionId);
            }
        });
    }
    isListening(guildId) {
        return this.receivers.has(guildId);
    }
    getActiveGuilds() {
        return Array.from(this.receivers.keys());
    }
    getSessionCount() {
        return this.sessions.size;
    }
}
exports.VoiceListenerService = VoiceListenerService;
//# sourceMappingURL=VoiceListenerService.js.map