"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.VoiceManager = void 0;
const voice_1 = require("@discordjs/voice");
const events_1 = require("events");
const logger_1 = require("../services/logger");
class VoiceManager extends events_1.EventEmitter {
    connections = new Map();
    players = new Map();
    currentTracks = new Map();
    playbackStrategy;
    disconnectTimers = new Map();
    voiceChannels = new Map();
    idleTimeoutMs;
    connectionStates = new Map();
    constructor(playbackStrategy) {
        super();
        this.playbackStrategy = playbackStrategy;
        this.idleTimeoutMs = parseInt(process.env.VOICE_IDLE_TIMEOUT_MS || '300000', 10);
        logger_1.logger.info(`🎵 VoiceManager initialized with idle timeout: ${this.idleTimeoutMs}ms (${this.idleTimeoutMs / 1000 / 60} minutes)`);
        this.logConnectionStatus();
    }
    logConnectionStatus() {
        const activeConnections = this.connections.size;
        const activePlayers = this.players.size;
        const states = Array.from(this.connectionStates.entries())
            .map(([guildId, state]) => `${guildId}: ${state}`)
            .join(', ');
        logger_1.logger.info(`📊 VoiceManager Status: ${activeConnections} connections, ${activePlayers} players | States: ${states || 'none'}`);
    }
    async join(channel) {
        const guildId = channel.guild.id;
        logger_1.logger.info(`🎤 [JOIN] Starting voice channel join for guild ${guildId}`);
        logger_1.logger.info(`📍 Channel: ${channel.name} (${channel.id}) | Members: ${channel.members.size}`);
        const existingConnection = this.connections.get(guildId);
        if (existingConnection) {
            logger_1.logger.warn(`⚠️ [JOIN] Already connected to guild ${guildId}, destroying old connection`);
            existingConnection.destroy();
        }
        const connection = (0, voice_1.joinVoiceChannel)({
            channelId: channel.id,
            guildId: channel.guild.id,
            adapterCreator: channel.guild.voiceAdapterCreator
        });
        this.connectionStates.set(guildId, 'connecting');
        logger_1.logger.info(`🔄 [CONNECTION] Guild ${guildId} state: connecting`);
        connection.on(voice_1.VoiceConnectionStatus.Ready, () => {
            this.connectionStates.set(guildId, 'ready');
            logger_1.logger.info(`✅ [CONNECTION] Guild ${guildId} state: READY - Successfully connected!`);
            this.logConnectionStatus();
        });
        connection.on(voice_1.VoiceConnectionStatus.Signalling, () => {
            this.connectionStates.set(guildId, 'signalling');
            logger_1.logger.info(`📡 [CONNECTION] Guild ${guildId} state: SIGNALLING - Establishing connection...`);
        });
        connection.on(voice_1.VoiceConnectionStatus.Connecting, () => {
            this.connectionStates.set(guildId, 'connecting');
            logger_1.logger.info(`🔗 [CONNECTION] Guild ${guildId} state: CONNECTING - Setting up voice...`);
        });
        connection.on(voice_1.VoiceConnectionStatus.Disconnected, async () => {
            this.connectionStates.set(guildId, 'disconnected');
            logger_1.logger.warn(`🔌 [CONNECTION] Guild ${guildId} state: DISCONNECTED - Attempting recovery...`);
            try {
                logger_1.logger.info(`🔄 [RECOVERY] Attempting to reconnect for guild ${guildId}...`);
                await Promise.race([
                    (0, voice_1.entersState)(connection, voice_1.VoiceConnectionStatus.Signalling, 5_000),
                    (0, voice_1.entersState)(connection, voice_1.VoiceConnectionStatus.Connecting, 5_000)
                ]);
                logger_1.logger.info(`✅ [RECOVERY] Successfully recovered connection for guild ${guildId}`);
            }
            catch (error) {
                logger_1.logger.error(`❌ [RECOVERY] Failed to recover connection for guild ${guildId}:`, error);
                logger_1.logger.warn(`💀 [CONNECTION] Guild ${guildId} permanently lost, cleaning up resources`);
                const player = this.players.get(guildId);
                if (player) {
                    logger_1.logger.info(`🛑 [CLEANUP] Stopping audio player for guild ${guildId}`);
                    player.stop(true);
                    this.players.delete(guildId);
                }
                connection.destroy();
                this.connections.delete(guildId);
                this.voiceChannels.delete(guildId);
                this.currentTracks.delete(guildId);
                this.connectionStates.delete(guildId);
                this.clearDisconnectTimer(guildId);
                logger_1.logger.info(`🧹 [CLEANUP] Completed cleanup for guild ${guildId}`);
                this.logConnectionStatus();
            }
        });
        connection.on(voice_1.VoiceConnectionStatus.Destroyed, () => {
            this.connectionStates.set(guildId, 'destroyed');
            logger_1.logger.info(`💥 [CONNECTION] Guild ${guildId} state: DESTROYED - Connection terminated`);
            this.connections.delete(guildId);
            this.voiceChannels.delete(guildId);
            this.currentTracks.delete(guildId);
            this.connectionStates.delete(guildId);
            this.clearDisconnectTimer(guildId);
            this.logConnectionStatus();
        });
        connection.on('error', (error) => {
            logger_1.logger.error(`🚨 [CONNECTION ERROR] Guild ${guildId}:`, error);
            logger_1.logger.error(`Error details: ${JSON.stringify({
                message: error.message,
                stack: error.stack,
                state: this.connectionStates.get(guildId)
            })}`);
        });
        logger_1.logger.info(`💾 [JOIN] Storing connection for guild ${guildId}`);
        this.connections.set(guildId, connection);
        this.voiceChannels.set(guildId, channel);
        logger_1.logger.info(`✅ [JOIN] Successfully stored voice channel ${channel.name} for guild ${guildId}`);
        if (!this.players.has(guildId)) {
            logger_1.logger.info(`🎵 [PLAYER] Creating new audio player for guild ${guildId}`);
            const player = (0, voice_1.createAudioPlayer)();
            player.on(voice_1.AudioPlayerStatus.Idle, () => {
                const track = this.currentTracks.get(guildId);
                logger_1.logger.info(`⏸️ [PLAYER] Guild ${guildId} state: IDLE ${track ? `(finished: ${track.title})` : ''}`);
                this.emit('finish');
                this.startDisconnectTimer(guildId);
            });
            player.on(voice_1.AudioPlayerStatus.Buffering, () => {
                const track = this.currentTracks.get(guildId);
                logger_1.logger.info(`⏳ [PLAYER] Guild ${guildId} state: BUFFERING ${track ? `(track: ${track.title})` : ''}`);
            });
            player.on(voice_1.AudioPlayerStatus.Playing, () => {
                const track = this.currentTracks.get(guildId);
                logger_1.logger.info(`▶️ [PLAYER] Guild ${guildId} state: PLAYING ${track ? `(track: ${track.title})` : '(TTS/unknown)'}`);
                this.clearDisconnectTimer(guildId);
            });
            player.on(voice_1.AudioPlayerStatus.AutoPaused, () => {
                logger_1.logger.warn(`⚠️ [PLAYER] Guild ${guildId} state: AUTO-PAUSED (connection issue?)`);
            });
            player.on(voice_1.AudioPlayerStatus.Paused, () => {
                logger_1.logger.info(`⏸️ [PLAYER] Guild ${guildId} state: PAUSED`);
            });
            player.on('error', error => {
                const currentTrack = this.currentTracks.get(guildId);
                logger_1.logger.error(`🚨 [PLAYER ERROR] Guild ${guildId}:`, error);
                logger_1.logger.error(`Error details: ${JSON.stringify({
                    message: error.message,
                    resource: error.resource?.metadata,
                    track: currentTrack?.title || 'unknown',
                    playerState: player.state.status
                })}`);
                if (currentTrack) {
                    logger_1.logger.warn(`🧹 [PLAYER ERROR] Cleaning up failed track: ${currentTrack.title}`);
                    this.currentTracks.delete(guildId);
                }
                if (player.state.status !== voice_1.AudioPlayerStatus.Idle) {
                    logger_1.logger.info(`🔄 [PLAYER ERROR] Force stopping player for guild ${guildId}`);
                    player.stop(true);
                }
                this.emit('error', error);
                setTimeout(() => {
                    logger_1.logger.info(`🔄 [PLAYER ERROR] Triggering finish event for recovery`);
                    this.emit('finish');
                }, 1000);
            });
            logger_1.logger.info(`💾 [PLAYER] Storing player for guild ${guildId}`);
            this.players.set(guildId, player);
            connection.subscribe(player);
            logger_1.logger.info(`🔌 [PLAYER] Subscribed player to connection for guild ${guildId}`);
        }
        else {
            logger_1.logger.info(`♻️ [PLAYER] Reusing existing player for guild ${guildId}`);
        }
        this.clearDisconnectTimer(guildId);
        logger_1.logger.info(`✅ [JOIN] Completed voice channel join for guild ${guildId}`);
        this.logConnectionStatus();
        return connection;
    }
    async leave(guildId) {
        logger_1.logger.info(`👋 [LEAVE] Starting disconnect for guild ${guildId}`);
        const connection = this.connections.get(guildId);
        const player = this.players.get(guildId);
        const channel = this.voiceChannels.get(guildId);
        const track = this.currentTracks.get(guildId);
        logger_1.logger.info(`📊 [LEAVE] Current state - Connection: ${connection ? 'exists' : 'none'}, Player: ${player ? 'exists' : 'none'}, Track: ${track?.title || 'none'}`);
        if (player) {
            logger_1.logger.info(`🛑 [LEAVE] Stopping audio player for guild ${guildId}`);
            player.stop();
            this.players.delete(guildId);
            logger_1.logger.info(`🗑️ [LEAVE] Audio player destroyed for guild ${guildId}`);
        }
        if (connection) {
            logger_1.logger.info(`🔌 [LEAVE] Destroying voice connection for guild ${guildId}`);
            connection.destroy();
            this.connections.delete(guildId);
            logger_1.logger.info(`💥 [LEAVE] Voice connection destroyed for guild ${guildId}`);
        }
        this.currentTracks.delete(guildId);
        this.voiceChannels.delete(guildId);
        this.connectionStates.delete(guildId);
        this.clearDisconnectTimer(guildId);
        logger_1.logger.info(`✅ [LEAVE] Completed disconnect for guild ${guildId} ${channel ? `from ${channel.name}` : ''}`);
        this.logConnectionStatus();
    }
    async play(track, guildId) {
        logger_1.logger.info(`🎵 [PLAY] Starting playback for guild ${guildId}`);
        logger_1.logger.info(`🎶 [PLAY] Track: "${track.title}" (${track.duration || 'unknown duration'})`);
        this.logConnectionStatus();
        const connection = this.connections.get(guildId);
        if (!connection) {
            logger_1.logger.error(`❌ [PLAY] No connection found for guild ${guildId}`);
            logger_1.logger.error(`Available connections: ${Array.from(this.connections.keys()).join(', ')}`);
            throw new Error('Not connected to any voice channel');
        }
        const connectionState = this.connectionStates.get(guildId);
        logger_1.logger.info(`📡 [PLAY] Connection state: ${connectionState || 'unknown'}`);
        const player = this.players.get(guildId);
        if (!player) {
            logger_1.logger.error(`❌ [PLAY] No player found for guild ${guildId}`);
            logger_1.logger.error(`Available players: ${Array.from(this.players.keys()).join(', ')}`);
            throw new Error('No audio player found');
        }
        logger_1.logger.info(`🎵 [PLAY] Player state: ${player.state.status}`);
        this.clearDisconnectTimer(guildId);
        const channel = this.getVoiceChannel(guildId);
        if (!channel) {
            logger_1.logger.error(`❌ [PLAY] No voice channel found for guild ${guildId}`);
            logger_1.logger.error(`Available channels: ${Array.from(this.voiceChannels.keys()).join(', ')}`);
            throw new Error('Voice channel not found');
        }
        logger_1.logger.info(`📍 [PLAY] Voice channel: ${channel.name} (${channel.members.size} members)`);
        logger_1.logger.info(`🔄 [PLAY] Attempting playback with strategy...`);
        const playbackResult = await this.playbackStrategy.attemptPlayback({
            id: track.id,
            title: track.title,
            url: track.url,
            duration: track.duration,
            thumbnail: track.thumbnail,
            channel: ''
        }, channel);
        logger_1.logger.info(`✅ [PLAY] Playback strategy succeeded, creating audio resource...`);
        try {
            const resource = (0, voice_1.createAudioResource)(playbackResult.stream, {
                inlineVolume: true,
                metadata: {
                    title: track.title,
                    guildId: guildId
                }
            });
            logger_1.logger.info(`📦 [PLAY] Audio resource created successfully`);
            resource.playStream.on('error', (error) => {
                logger_1.logger.error(`🚨 [STREAM ERROR] Track "${track.title}" in guild ${guildId}:`, error);
                logger_1.logger.error(`Stream error details: ${JSON.stringify({
                    message: error.message,
                    code: error.code,
                    syscall: error.syscall
                })}`);
                player.stop(true);
            });
            logger_1.logger.info(`▶️ [PLAY] Sending audio resource to player...`);
            player.play(resource);
            this.currentTracks.set(guildId, track);
            logger_1.logger.info(`💾 [PLAY] Stored current track for guild ${guildId}`);
            logger_1.logger.info(`✅ [PLAY] Successfully started playing "${track.title}" in guild ${guildId}`);
            this.logConnectionStatus();
        }
        catch (error) {
            logger_1.logger.error(`❌ [PLAY] Failed to create audio resource for "${track.title}":`, error);
            logger_1.logger.error(`Resource creation error details: ${JSON.stringify({
                message: error.message,
                stack: error.stack
            })}`);
            try {
                playbackResult.stream.destroy();
                logger_1.logger.info(`🧹 [PLAY] Cleaned up failed stream`);
            }
            catch (cleanupError) {
                logger_1.logger.error(`❌ [PLAY] Failed to cleanup stream:`, cleanupError);
            }
            throw error;
        }
    }
    skip(guildId) {
        logger_1.logger.info(`[VoiceManager.skip] Called with guildId: ${guildId}, type: ${typeof guildId}`);
        const player = this.players.get(guildId);
        if (player) {
            player.stop();
        }
    }
    stop() {
        this.players.forEach(player => player.stop());
        this.connections.forEach((connection, guildId) => this.leave(guildId));
    }
    isPlaying(guildId) {
        logger_1.logger.info(`[VoiceManager.isPlaying] Called with guildId: ${guildId}, type: ${typeof guildId}`);
        const player = this.players.get(guildId);
        return player?.state.status === voice_1.AudioPlayerStatus.Playing;
    }
    getVoiceChannel(guildId) {
        logger_1.logger.info(`[VoiceManager.getVoiceChannel] Called with guildId: ${guildId}, type: ${typeof guildId}`);
        logger_1.logger.info(`[VoiceManager.getVoiceChannel] voiceChannels Map keys: ${Array.from(this.voiceChannels.keys()).join(', ')}`);
        return this.voiceChannels.get(guildId) || null;
    }
    startDisconnectTimer(guildId) {
        this.clearDisconnectTimer(guildId);
        logger_1.logger.info(`Starting disconnect timer for guild ${guildId} - will disconnect in ${this.idleTimeoutMs / 1000} seconds`);
        const timer = setTimeout(() => {
            logger_1.logger.info(`Auto-disconnecting from guild ${guildId} due to inactivity (timeout reached: ${this.idleTimeoutMs}ms)`);
            this.leave(guildId);
        }, this.idleTimeoutMs);
        this.disconnectTimers.set(guildId, timer);
    }
    clearDisconnectTimer(guildId) {
        const timer = this.disconnectTimers.get(guildId);
        if (timer) {
            logger_1.logger.info(`Clearing disconnect timer for guild ${guildId}`);
            clearTimeout(timer);
            this.disconnectTimers.delete(guildId);
        }
    }
}
exports.VoiceManager = VoiceManager;
//# sourceMappingURL=VoiceManager.js.map