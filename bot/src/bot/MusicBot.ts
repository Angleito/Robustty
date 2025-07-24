import { Client, GatewayIntentBits, CommandInteraction, VoiceChannel } from 'discord.js';
import { logger } from '../services/logger';
import { CommandHandler } from './CommandHandler';
import { ButtonHandler } from './ButtonHandler';
import { VoiceManager } from './VoiceManager';
import { QueueManager } from '../domain/QueueManager';
import { YouTubeService } from '../services/YouTubeService';
import { PlaybackStrategyManager } from '../services/PlaybackStrategyManager';
import { RedisClient } from '../services/RedisClient';
import { ErrorHandler } from '../services/ErrorHandler';
import { MonitoringService } from '../services/MonitoringService';
import { Track, YouTubeVideo } from '../domain/types';

export class MusicBot {
  private client: Client;
  private commandHandler: CommandHandler;
  private buttonHandler: ButtonHandler;
  private voiceManager: VoiceManager;
  private queueManager: QueueManager;
  private youtubeService: YouTubeService;
  private playbackStrategy: PlaybackStrategyManager;
  private redis: RedisClient;
  private errorHandler: ErrorHandler;
  private monitoringService: MonitoringService;

  constructor() {
    this.client = new Client({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildVoiceStates,
        GatewayIntentBits.GuildMessages
      ]
    });
    
    this.redis = new RedisClient();
    this.queueManager = new QueueManager();
    this.youtubeService = new YouTubeService();
    this.errorHandler = new ErrorHandler(this.redis);
    this.playbackStrategy = new PlaybackStrategyManager(this.redis);
    this.voiceManager = new VoiceManager(this.playbackStrategy);
    this.commandHandler = new CommandHandler(this);
    this.buttonHandler = new ButtonHandler(this);
    this.monitoringService = new MonitoringService(this.client, this.redis);
  }

  async initialize() {
    await this.redis.connect();
    await this.commandHandler.registerCommands();
    
    this.client.on('ready', () => {
      logger.info(`Logged in as ${this.client.user?.tag}`);
      this.monitoringService.start();
    });
    
    this.client.on('interactionCreate', async (interaction) => {
      if (interaction.isCommand()) {
        await this.commandHandler.handleCommand(interaction);
      } else if (interaction.isButton()) {
        await this.buttonHandler.handleButton(interaction);
      }
    });
  }

  async start() {
    await this.client.login(process.env.DISCORD_TOKEN);
  }

  async play(query: string, interaction: CommandInteraction) {
    logger.info(`[MusicBot.play] Starting play command - guildId from interaction: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
    const member = interaction.guild?.members.cache.get(interaction.user.id);
    const voiceChannel = member?.voice.channel as VoiceChannel;
    
    if (!voiceChannel) {
      await interaction.editReply('You need to be in a voice channel!');
      return;
    }

    const videos = await this.searchYouTube(query);
    if (videos.length === 0) {
      await interaction.editReply('No results found!');
      return;
    }

    const track: Track = {
      id: videos[0].id,
      title: videos[0].title,
      url: videos[0].url,
      duration: videos[0].duration,
      thumbnail: videos[0].thumbnail,
      requestedBy: interaction.user.id
    };

    await this.addToQueue(track);
    
    if (!this.voiceManager.isPlaying(interaction.guildId!)) {
      logger.info(`[MusicBot.play] Before join - guildId: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
      await this.voiceManager.join(voiceChannel);
      logger.info(`[MusicBot.play] Before playNext - guildId: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
      await this.playNext(interaction.guildId!);
    }
    
    await interaction.editReply(`Added to queue: **${track.title}**`);
  }

  async addToQueue(track: Track) {
    await this.queueManager.add(track);
  }

  async skip(guildId: string) {
    logger.info(`[MusicBot.skip] Called with guildId: ${guildId}, type: ${typeof guildId}`);
    await this.voiceManager.skip(guildId);
  }

  async stop(guildId: string) {
    if (!guildId) {
      logger.error('[stop] Called with undefined guildId');
      return;
    }
    await this.voiceManager.leave(guildId);
    await this.queueManager.clear();
  }

  async searchYouTube(query: string): Promise<YouTubeVideo[]> {
    return this.youtubeService.search(query);
  }

  async getPlaylist(playlistId: string): Promise<YouTubeVideo[]> {
    return this.youtubeService.getPlaylist(playlistId);
  }

  private async playNext(guildId: string) {
    logger.info(`[MusicBot.playNext] Called with guildId: ${guildId}, type: ${typeof guildId}`);
    const track = await this.queueManager.getNext();
    if (!track) {
      await this.voiceManager.leave(guildId);
      return;
    }

    try {
      logger.info(`[MusicBot.playNext] Before VoiceManager.play - guildId: ${guildId}, type: ${typeof guildId}`);
      await this.voiceManager.play(track, guildId);
      this.voiceManager.once('finish', () => this.playNext(guildId));
    } catch (error) {
      logger.error('Playback error:', error);
      
      // Convert track to YouTubeVideo for error handling
      const video: YouTubeVideo = {
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
}