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
            logger_1.logger.info(`[VoiceListenerService] 🎯 Starting voice listening for guild ${guildId} in channel ${channel.name}`);
            logger_1.logger.info(`[VoiceListenerService] Connection state: ${connection.state.status}`);
            logger_1.logger.info(`[VoiceListenerService] Members in channel: ${channel.members.size}`);
            const receiver = {
                connection,
                channel,
                activeUsers: new Map(),
                audioBuffer: new Map(),
                lastActivity: new Map()
            };
            this.receivers.set(guildId, receiver);
            const voiceReceiver = connection.receiver;
            if (!voiceReceiver) {
                logger_1.logger.error(`[VoiceListenerService] No voice receiver available for connection`);
                throw new Error('Voice receiver not available');
            }
            if (!voiceReceiver.speaking) {
                logger_1.logger.error(`[VoiceListenerService] No speaking detector available`);
                throw new Error('Speaking detector not available');
            }
            voiceReceiver.speaking.on('start', (userId) => {
                logger_1.logger.debug(`[VoiceListenerService] 🎤 Speaking START event for user ${userId}`);
                this.handleSpeakingStart(guildId, userId);
            });
            voiceReceiver.speaking.on('end', (userId) => {
                logger_1.logger.debug(`[VoiceListenerService] 🔇 Speaking END event for user ${userId}`);
                this.handleSpeakingEnd(guildId, userId);
            });
            this.setupUserAudioStreams(guildId, voiceReceiver);
            this.startCleanupRoutine(guildId);
            logger_1.logger.info(`[VoiceListenerService] ✅ Voice listening ACTIVE for guild ${guildId}`);
            logger_1.logger.info(`[VoiceListenerService] Registered receivers: ${this.receivers.size}`);
            this.emit('listeningStarted', { guildId, channelId: channel.id });
        }
        catch (error) {
            logger_1.logger.error(`[VoiceListenerService] ❌ Failed to start listening in guild ${guildId}:`, error);
            logger_1.logger.error(`[VoiceListenerService] Stack trace:`, error instanceof Error ? error.stack : 'No stack');
            throw error;
        }
    }
    setupUserAudioStreams(guildId, voiceReceiver) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        if (voiceReceiver.connection) {
            voiceReceiver.connection.on('stateChange', () => {
                setTimeout(() => this.refreshUserStreams(guildId), 1000);
            });
        }
        else {
            logger_1.logger.debug(`[VoiceListenerService] No connection object on voiceReceiver for monitoring state changes`);
        }
        this.refreshUserStreams(guildId);
    }
    refreshUserStreams(guildId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver) {
            logger_1.logger.warn(`[VoiceListenerService] No receiver found for guild ${guildId}`);
            return;
        }
        const voiceReceiver = receiver.connection.receiver;
        if (!voiceReceiver) {
            logger_1.logger.warn(`[VoiceListenerService] No voice receiver available for guild ${guildId}`);
            return;
        }
        logger_1.logger.info(`[VoiceListenerService] Refreshing user streams for guild ${guildId}`);
        logger_1.logger.info(`[VoiceListenerService] Channel members: ${receiver.channel.members.size}`);
        receiver.channel.members.forEach((member) => {
            if (member.user.bot) {
                logger_1.logger.debug(`[VoiceListenerService] Skipping bot user: ${member.user.tag}`);
                return;
            }
            const userId = member.user.id;
            if (!receiver.activeUsers.has(userId)) {
                logger_1.logger.info(`[VoiceListenerService] 👤 Setting up audio stream for user: ${member.user.tag} (${userId})`);
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
                logger_1.logger.info(`[VoiceListenerService] ✅ Started listening to user ${member.user.tag} in guild ${guildId}`);
            }
            else {
                logger_1.logger.debug(`[VoiceListenerService] User ${member.user.tag} already has active stream`);
            }
        });
        logger_1.logger.info(`[VoiceListenerService] Active users being monitored: ${receiver.activeUsers.size}`);
    }
    setupAudioStreamHandlers(guildId, userId, audioStream) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        let packetCount = 0;
        audioStream.on('data', (chunk) => {
            packetCount++;
            if (packetCount % 100 === 0) {
                logger_1.logger.debug(`[VoiceListenerService] 📊 Received ${packetCount} audio packets from user ${userId}`);
            }
            this.handleAudioData(guildId, userId, chunk);
        });
        audioStream.on('end', () => {
            logger_1.logger.info(`[VoiceListenerService] 🎬 Audio stream ended for user ${userId} - Total packets: ${packetCount}`);
            this.processAudioBuffer(guildId, userId);
        });
        audioStream.on('error', (error) => {
            logger_1.logger.error(`[VoiceListenerService] ❌ Audio stream error for user ${userId} in guild ${guildId}:`, error);
            logger_1.logger.error(`[VoiceListenerService] Error details:`, error.message);
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
        if (!userBuffer) {
            logger_1.logger.warn(`[VoiceListenerService] No buffer found for user ${userId}`);
            return;
        }
        userBuffer.push(chunk);
        receiver.lastActivity.set(userId, Date.now());
        const totalSize = userBuffer.reduce((sum, buf) => sum + buf.length, 0);
        if (totalSize > this.maxBufferSize) {
            logger_1.logger.warn(`[VoiceListenerService] ⚠️ Buffer overflow for user ${userId} (${totalSize} bytes), processing early`);
            this.processAudioBuffer(guildId, userId);
        }
    }
    processAudioBuffer(guildId, userId) {
        const receiver = this.receivers.get(guildId);
        if (!receiver)
            return;
        const userBuffer = receiver.audioBuffer.get(userId);
        if (!userBuffer || userBuffer.length === 0) {
            logger_1.logger.debug(`[VoiceListenerService] No audio buffer to process for user ${userId}`);
            return;
        }
        try {
            logger_1.logger.info(`[VoiceListenerService] 🎙️ Processing audio buffer for user ${userId} - Chunks: ${userBuffer.length}`);
            const combinedAudio = Buffer.concat(userBuffer);
            logger_1.logger.info(`[VoiceListenerService] Combined audio size: ${combinedAudio.length} bytes`);
            receiver.audioBuffer.set(userId, []);
            if (combinedAudio.length < 1600) {
                logger_1.logger.debug(`[VoiceListenerService] Audio too short (${combinedAudio.length} bytes), skipping`);
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
            logger_1.logger.info(`[VoiceListenerService] 🎯 Created audio segment: ${audioSegment.id}`);
            logger_1.logger.info(`[VoiceListenerService] Segment details - Duration: ${audioSegment.duration.toFixed(2)}s, Sample rate: ${audioSegment.sampleRate}Hz, Channels: ${audioSegment.channels}`);
            this.emit('audioSegment', audioSegment);
            logger_1.logger.info(`[VoiceListenerService] ✅ Emitted audio segment for processing`);
        }
        catch (error) {
            logger_1.logger.error(`[VoiceListenerService] ❌ Error processing audio buffer for user ${userId}:`, error);
            logger_1.logger.error(`[VoiceListenerService] Stack trace:`, error instanceof Error ? error.stack : 'No stack');
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
            logger_1.logger.info(`[VoiceListenerService] ✅ Voice listening stopped for guild ${guildId}`);
            logger_1.logger.info(`[VoiceListenerService] Cleaned up ${sessionsToRemove.length} sessions`);
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
        const listening = this.receivers.has(guildId);
        logger_1.logger.debug(`[VoiceListenerService] isListening check for guild ${guildId}: ${listening}`);
        logger_1.logger.debug(`[VoiceListenerService] Active receivers: ${Array.from(this.receivers.keys()).join(', ')}`);
        return listening;
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