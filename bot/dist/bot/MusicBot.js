"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MusicBot = void 0;
const discord_js_1 = require("discord.js");
const logger_1 = require("../services/logger");
const CommandHandler_1 = require("./CommandHandler");
const ButtonHandler_1 = require("./ButtonHandler");
const VoiceManager_1 = require("./VoiceManager");
const VoiceCommandHandler_1 = require("./VoiceCommandHandler");
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
    voiceCommandHandler;
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
                discord_js_1.GatewayIntentBits.GuildMessages,
                discord_js_1.GatewayIntentBits.MessageContent
            ]
        });
        this.redis = new RedisClient_1.RedisClient();
        this.queueManager = new QueueManager_1.QueueManager();
        this.youtubeService = new YouTubeService_1.YouTubeService();
        this.errorHandler = new ErrorHandler_1.ErrorHandler(this.redis);
        this.playbackStrategy = new PlaybackStrategyManager_1.PlaybackStrategyManager(this.redis);
        this.voiceManager = new VoiceManager_1.VoiceManager(this.playbackStrategy);
        this.voiceCommandHandler = new VoiceCommandHandler_1.VoiceCommandHandler();
        this.searchResultHandler = new SearchResultHandler_1.SearchResultHandler();
        this.commandHandler = new CommandHandler_1.CommandHandler(this);
        this.buttonHandler = new ButtonHandler_1.ButtonHandler(this);
        this.monitoringService = new MonitoringService_1.MonitoringService(this.client, this.redis);
        this.setupVoiceCommandHandling();
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
    getVoiceCommandHandler() {
        return this.voiceCommandHandler;
    }
    setupVoiceCommandHandling() {
        this.voiceCommandHandler.on('voiceCommand', async (voiceCommand) => {
            await this.handleVoiceCommand(voiceCommand);
        });
    }
    async handleVoiceCommand(voiceCommand) {
        try {
            logger_1.logger.info(`[MusicBot] Processing voice command: ${voiceCommand.command} from user ${voiceCommand.userId}`);
            const guild = this.client.guilds.cache.get(voiceCommand.guildId);
            if (!guild) {
                logger_1.logger.error(`[MusicBot] Guild ${voiceCommand.guildId} not found`);
                return;
            }
            const member = guild.members.cache.get(voiceCommand.userId);
            if (!member) {
                logger_1.logger.error(`[MusicBot] Member ${voiceCommand.userId} not found in guild ${voiceCommand.guildId}`);
                return;
            }
            const voiceChannel = member.voice.channel;
            if (!voiceChannel) {
                logger_1.logger.warn(`[MusicBot] User ${voiceCommand.userId} not in a voice channel`);
                return;
            }
            switch (voiceCommand.command) {
                case 'play':
                    await this.handleVoicePlayCommand(voiceCommand, voiceChannel);
                    break;
                case 'skip':
                    await this.handleVoiceSkipCommand(voiceCommand);
                    break;
                case 'stop':
                    await this.handleVoiceStopCommand(voiceCommand);
                    break;
                case 'pause':
                    await this.handleVoicePauseCommand(voiceCommand);
                    break;
                case 'resume':
                    await this.handleVoiceResumeCommand(voiceCommand);
                    break;
                case 'queue':
                    await this.handleVoiceQueueCommand(voiceCommand);
                    break;
                default:
                    logger_1.logger.warn(`[MusicBot] Unknown voice command: ${voiceCommand.command}`);
            }
        }
        catch (error) {
            logger_1.logger.error('[MusicBot] Error handling voice command:', error);
        }
    }
    async handleVoicePlayCommand(voiceCommand, voiceChannel) {
        const query = voiceCommand.parameters.join(' ');
        if (!query) {
            logger_1.logger.warn('[MusicBot] Voice play command received without query');
            return;
        }
        try {
            const videos = await this.searchYouTube(query);
            if (videos.length === 0) {
                logger_1.logger.info(`[MusicBot] No results found for voice query: "${query}"`);
                return;
            }
            const selectedVideo = videos[0];
            const track = {
                id: selectedVideo.id,
                title: selectedVideo.title,
                url: selectedVideo.url,
                duration: selectedVideo.duration,
                thumbnail: selectedVideo.thumbnail,
                requestedBy: voiceCommand.userId
            };
            await this.addToQueue(track);
            if (!this.voiceManager.isPlaying(voiceCommand.guildId)) {
                const connection = await this.voiceManager.join(voiceChannel);
                await this.voiceCommandHandler.startListening(voiceChannel, connection);
                await this.playNext(voiceCommand.guildId);
            }
            logger_1.logger.info(`[MusicBot] Voice command added track: ${track.title}`);
        }
        catch (error) {
            logger_1.logger.error('[MusicBot] Error handling voice play command:', error);
        }
    }
    async handleVoiceSkipCommand(voiceCommand) {
        try {
            await this.skip(voiceCommand.guildId);
            logger_1.logger.info(`[MusicBot] Voice command skipped track in guild ${voiceCommand.guildId}`);
        }
        catch (error) {
            logger_1.logger.error('[MusicBot] Error handling voice skip command:', error);
        }
    }
    async handleVoiceStopCommand(voiceCommand) {
        try {
            await this.voiceCommandHandler.stopListening(voiceCommand.guildId);
            await this.stop(voiceCommand.guildId);
            logger_1.logger.info(`[MusicBot] Voice command stopped playback in guild ${voiceCommand.guildId}`);
        }
        catch (error) {
            logger_1.logger.error('[MusicBot] Error handling voice stop command:', error);
        }
    }
    async handleVoicePauseCommand(voiceCommand) {
        logger_1.logger.info(`[MusicBot] Voice pause command received (not implemented)`);
    }
    async handleVoiceResumeCommand(voiceCommand) {
        logger_1.logger.info(`[MusicBot] Voice resume command received (not implemented)`);
    }
    async handleVoiceQueueCommand(voiceCommand) {
        const queue = this.queueManager.getQueue();
        logger_1.logger.info(`[MusicBot] Voice queue command - ${queue.length} tracks in queue`);
    }
    async enableVoiceCommands(voiceChannel) {
        try {
            if (!this.voiceManager.isPlaying(voiceChannel.guild.id)) {
                const connection = await this.voiceManager.join(voiceChannel);
                await this.voiceCommandHandler.startListening(voiceChannel, connection);
            }
            logger_1.logger.info(`[MusicBot] Voice commands enabled in ${voiceChannel.name}`);
        }
        catch (error) {
            logger_1.logger.error('[MusicBot] Failed to enable voice commands:', error);
            throw error;
        }
    }
    async disableVoiceCommands(guildId) {
        try {
            await this.voiceCommandHandler.stopListening(guildId);
            logger_1.logger.info(`[MusicBot] Voice commands disabled for guild ${guildId}`);
        }
        catch (error) {
            logger_1.logger.error('[MusicBot] Failed to disable voice commands:', error);
        }
    }
    isVoiceCommandsActive(guildId) {
        return this.voiceCommandHandler.isListening(guildId);
    }
    getVoiceCostStats() {
        return this.voiceCommandHandler.getCostStats();
    }
    logVoiceCostSummary() {
        this.voiceCommandHandler.logCostSummary();
    }
    resetVoiceCostTracking() {
        this.voiceCommandHandler.resetCostTracking();
    }
    async getVoiceHealthCheck() {
        return this.voiceCommandHandler.healthCheck();
    }
}
exports.MusicBot = MusicBot;
//# sourceMappingURL=MusicBot.js.map