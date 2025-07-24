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
    constructor(playbackStrategy) {
        super();
        this.playbackStrategy = playbackStrategy;
    }
    async join(channel) {
        const guildId = channel.guild.id;
        logger_1.logger.info(`[VoiceManager.join] Called with channel.guild.id: ${guildId}, type: ${typeof guildId}`);
        logger_1.logger.info(`Joining voice channel ${channel.name} in guild ${guildId}`);
        const connection = (0, voice_1.joinVoiceChannel)({
            channelId: channel.id,
            guildId: channel.guild.id,
            adapterCreator: channel.guild.voiceAdapterCreator
        });
        connection.on(voice_1.VoiceConnectionStatus.Disconnected, async () => {
            try {
                await Promise.race([
                    (0, voice_1.entersState)(connection, voice_1.VoiceConnectionStatus.Signalling, 5_000),
                    (0, voice_1.entersState)(connection, voice_1.VoiceConnectionStatus.Connecting, 5_000)
                ]);
            }
            catch (error) {
                connection.destroy();
                this.connections.delete(guildId);
                this.voiceChannels.delete(guildId);
            }
        });
        logger_1.logger.info(`[VoiceManager.join] Storing connection for guildId: ${guildId}, type: ${typeof guildId}`);
        this.connections.set(guildId, connection);
        this.voiceChannels.set(guildId, channel);
        logger_1.logger.info(`Successfully joined and stored voice channel for guild ${guildId}`);
        if (!this.players.has(guildId)) {
            const player = (0, voice_1.createAudioPlayer)();
            player.on(voice_1.AudioPlayerStatus.Idle, () => {
                this.emit('finish');
                this.startDisconnectTimer(guildId);
            });
            player.on('error', error => {
                logger_1.logger.error('Audio player error:', error);
                this.emit('error', error);
            });
            logger_1.logger.info(`[VoiceManager.join] Storing player for guildId: ${guildId}, type: ${typeof guildId}`);
            this.players.set(guildId, player);
            connection.subscribe(player);
        }
        this.clearDisconnectTimer(guildId);
        return connection;
    }
    async leave(guildId) {
        const connection = this.connections.get(guildId);
        const player = this.players.get(guildId);
        if (player) {
            player.stop();
            this.players.delete(guildId);
        }
        if (connection) {
            connection.destroy();
            this.connections.delete(guildId);
        }
        this.currentTracks.delete(guildId);
        this.voiceChannels.delete(guildId);
        this.clearDisconnectTimer(guildId);
    }
    async play(track, guildId) {
        logger_1.logger.info(`[VoiceManager.play] Called with guildId: ${guildId}, type: ${typeof guildId}`);
        logger_1.logger.info(`Attempting to play track ${track.title} in guild ${guildId}`);
        logger_1.logger.info(`[VoiceManager.play] Retrieving connection from map for guildId: ${guildId}`);
        logger_1.logger.info(`[VoiceManager.play] connections Map keys: ${Array.from(this.connections.keys()).join(', ')}`);
        const connection = this.connections.get(guildId);
        if (!connection) {
            logger_1.logger.error(`[VoiceManager.play] No connection found for guild ${guildId}, available keys: ${Array.from(this.connections.keys()).join(', ')}`);
            throw new Error('Not connected to any voice channel');
        }
        logger_1.logger.info(`[VoiceManager.play] Retrieving player from map for guildId: ${guildId}`);
        logger_1.logger.info(`[VoiceManager.play] players Map keys: ${Array.from(this.players.keys()).join(', ')}`);
        const player = this.players.get(guildId);
        if (!player) {
            logger_1.logger.error(`[VoiceManager.play] No player found for guild ${guildId}, available keys: ${Array.from(this.players.keys()).join(', ')}`);
            throw new Error('No audio player found');
        }
        this.clearDisconnectTimer(guildId);
        logger_1.logger.info(`[VoiceManager.play] Getting voice channel for guildId: ${guildId}`);
        const channel = this.getVoiceChannel(guildId);
        if (!channel) {
            logger_1.logger.error(`[VoiceManager.play] No voice channel found for guild ${guildId}. Available guilds: ${Array.from(this.voiceChannels.keys()).join(', ')}`);
            throw new Error('Voice channel not found');
        }
        logger_1.logger.info(`Voice channel found: ${channel.name}`);
        const playbackResult = await this.playbackStrategy.attemptPlayback({
            id: track.id,
            title: track.title,
            url: track.url,
            duration: track.duration,
            thumbnail: track.thumbnail,
            channel: ''
        }, channel);
        const resource = (0, voice_1.createAudioResource)(playbackResult.stream, {
            inlineVolume: true
        });
        player.play(resource);
        logger_1.logger.info(`[VoiceManager.play] Storing current track for guildId: ${guildId}, type: ${typeof guildId}`);
        this.currentTracks.set(guildId, track);
        logger_1.logger.info(`Started playing ${track.title} in guild ${guildId}`);
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
        const timer = setTimeout(() => {
            logger_1.logger.info(`Auto-disconnecting from guild ${guildId} due to inactivity`);
            this.leave(guildId);
        }, 5 * 60 * 1000);
        this.disconnectTimers.set(guildId, timer);
    }
    clearDisconnectTimer(guildId) {
        const timer = this.disconnectTimers.get(guildId);
        if (timer) {
            clearTimeout(timer);
            this.disconnectTimers.delete(guildId);
        }
    }
}
exports.VoiceManager = VoiceManager;
//# sourceMappingURL=VoiceManager.js.map