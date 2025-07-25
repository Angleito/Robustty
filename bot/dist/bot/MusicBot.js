"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MusicBot = void 0;
const discord_js_1 = require("discord.js");
const logger_1 = require("../services/logger");
const CommandHandler_1 = require("./CommandHandler");
const ButtonHandler_1 = require("./ButtonHandler");
const VoiceManager_1 = require("./VoiceManager");
const QueueManager_1 = require("../domain/QueueManager");
const YouTubeService_1 = require("../services/YouTubeService");
const PlaybackStrategyManager_1 = require("../services/PlaybackStrategyManager");
const RedisClient_1 = require("../services/RedisClient");
const ErrorHandler_1 = require("../services/ErrorHandler");
const MonitoringService_1 = require("../services/MonitoringService");
const SearchResultHandler_1 = require("../services/SearchResultHandler");
class MusicBot {
    client;
    commandHandler;
    buttonHandler;
    voiceManager;
    queueManager;
    youtubeService;
    playbackStrategy;
    redis;
    errorHandler;
    monitoringService;
    searchResultHandler;
    constructor() {
        this.client = new discord_js_1.Client({
            intents: [
                discord_js_1.GatewayIntentBits.Guilds,
                discord_js_1.GatewayIntentBits.GuildVoiceStates,
                discord_js_1.GatewayIntentBits.GuildMessages
            ]
        });
        this.redis = new RedisClient_1.RedisClient();
        this.queueManager = new QueueManager_1.QueueManager();
        this.youtubeService = new YouTubeService_1.YouTubeService();
        this.errorHandler = new ErrorHandler_1.ErrorHandler(this.redis);
        this.playbackStrategy = new PlaybackStrategyManager_1.PlaybackStrategyManager(this.redis);
        this.voiceManager = new VoiceManager_1.VoiceManager(this.playbackStrategy);
        this.searchResultHandler = new SearchResultHandler_1.SearchResultHandler();
        this.commandHandler = new CommandHandler_1.CommandHandler(this);
        this.buttonHandler = new ButtonHandler_1.ButtonHandler(this);
        this.monitoringService = new MonitoringService_1.MonitoringService(this.client, this.redis);
    }
    async initialize() {
        await this.redis.connect();
        await this.commandHandler.registerCommands();
        this.client.on('ready', () => {
            logger_1.logger.info(`Logged in as ${this.client.user?.tag}`);
            this.monitoringService.start();
        });
        this.client.on('interactionCreate', async (interaction) => {
            if (interaction.isCommand()) {
                await this.commandHandler.handleCommand(interaction);
            }
            else if (interaction.isButton()) {
                await this.buttonHandler.handleButton(interaction);
            }
        });
    }
    async start() {
        await this.client.login(process.env.DISCORD_TOKEN);
    }
    async play(query, interaction) {
        logger_1.logger.info(`[MusicBot.play] Starting play command - guildId from interaction: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
        const member = interaction.guild?.members.cache.get(interaction.user.id);
        const voiceChannel = member?.voice.channel;
        if (!voiceChannel) {
            await interaction.editReply('You need to be in a voice channel!');
            return;
        }
        const videos = await this.searchYouTube(query);
        if (videos.length === 0) {
            await interaction.editReply('No results found for your search!');
            return;
        }
        const sessionId = await this.searchResultHandler.createSearchSession(interaction.user.id, interaction.guildId, query, videos);
        const embed = this.searchResultHandler.createSearchEmbed(query, videos);
        const buttons = this.searchResultHandler.createSelectionButtons(sessionId, videos.length);
        await interaction.editReply({
            embeds: [embed],
            components: [buttons]
        });
    }
    async playSelectedVideo(video, interaction) {
        const member = interaction.guild?.members.cache.get(interaction.user.id);
        const voiceChannel = member?.voice.channel;
        if (!voiceChannel) {
            await interaction.editReply('You need to be in a voice channel!');
            return;
        }
        const track = {
            id: video.id,
            title: video.title,
            url: video.url,
            duration: video.duration,
            thumbnail: video.thumbnail,
            requestedBy: interaction.user.id
        };
        await this.addToQueue(track);
        if (!this.voiceManager.isPlaying(interaction.guildId)) {
            logger_1.logger.info(`[MusicBot.playSelectedVideo] Before join - guildId: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
            await this.voiceManager.join(voiceChannel);
            logger_1.logger.info(`[MusicBot.playSelectedVideo] Before playNext - guildId: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
            await this.playNext(interaction.guildId);
        }
        await interaction.editReply({
            content: `Added to queue: **${track.title}**`,
            embeds: [],
            components: []
        });
    }
    async playSelectedVideoFromButton(video, guildId, userId) {
        try {
            const guild = this.client.guilds.cache.get(guildId);
            if (!guild) {
                return { success: false, message: 'Guild not found!' };
            }
            const member = guild.members.cache.get(userId);
            if (!member) {
                return { success: false, message: 'Member not found!' };
            }
            const voiceChannel = member.voice.channel;
            if (!voiceChannel) {
                return { success: false, message: 'You need to be in a voice channel!' };
            }
            const track = {
                id: video.id,
                title: video.title,
                url: video.url,
                duration: video.duration,
                thumbnail: video.thumbnail,
                requestedBy: userId
            };
            await this.addToQueue(track);
            if (!this.voiceManager.isPlaying(guildId)) {
                logger_1.logger.info(`[MusicBot.playSelectedVideoFromButton] Before join - guildId: ${guildId}`);
                await this.voiceManager.join(voiceChannel);
                logger_1.logger.info(`[MusicBot.playSelectedVideoFromButton] Before playNext - guildId: ${guildId}`);
                await this.playNext(guildId);
            }
            return { success: true, message: `🎵 Added to queue: **${track.title}**` };
        }
        catch (error) {
            logger_1.logger.error('Error playing selected video from button:', error);
            return { success: false, message: 'An error occurred while adding the song to queue' };
        }
    }
    async addToQueue(track) {
        await this.queueManager.add(track);
    }
    async skip(guildId) {
        logger_1.logger.info(`[MusicBot.skip] Called with guildId: ${guildId}, type: ${typeof guildId}`);
        await this.voiceManager.skip(guildId);
    }
    async stop(guildId) {
        if (!guildId) {
            logger_1.logger.error('[stop] Called with undefined guildId');
            return;
        }
        await this.voiceManager.leave(guildId);
        await this.queueManager.clear();
    }
    async searchYouTube(query) {
        return this.youtubeService.search(query);
    }
    async getPlaylist(playlistId) {
        return this.youtubeService.getPlaylist(playlistId);
    }
    async playNext(guildId) {
        logger_1.logger.info(`[MusicBot.playNext] Called with guildId: ${guildId}, type: ${typeof guildId}`);
        const track = await this.queueManager.getNext();
        if (!track) {
            await this.voiceManager.leave(guildId);
            return;
        }
        try {
            logger_1.logger.info(`[MusicBot.playNext] Before VoiceManager.play - guildId: ${guildId}, type: ${typeof guildId}`);
            await this.voiceManager.play(track, guildId);
            this.voiceManager.once('finish', () => this.playNext(guildId));
        }
        catch (error) {
            logger_1.logger.error('Playback error:', error);
            const video = {
                id: track.id,
                title: track.title,
                url: track.url,
                duration: track.duration,
                thumbnail: track.thumbnail,
                channel: ''
            };
            await this.errorHandler.handlePlaybackError(error, video);
            await this.playNext(guildId);
        }
    }
    getClient() {
        return this.client;
    }
    getQueueManager() {
        return this.queueManager;
    }
    getButtonHandler() {
        return this.buttonHandler;
    }
    getNekoPool() {
        return this.playbackStrategy.nekoPool;
    }
    getPlaybackStrategy() {
        return this.playbackStrategy;
    }
    getMonitoringService() {
        return this.monitoringService;
    }
    getErrorHandler() {
        return this.errorHandler;
    }
    getSearchResultHandler() {
        return this.searchResultHandler;
    }
}
exports.MusicBot = MusicBot;
//# sourceMappingURL=MusicBot.js.map