import { Client, GatewayIntentBits, CommandInteraction, VoiceChannel, Message } from 'discord.js';
import { logger } from '../services/logger';
import { CommandHandler } from './CommandHandler';
import { ButtonHandler } from './ButtonHandler';
import { VoiceManager } from './VoiceManager';
import { VoiceCommandHandler } from './VoiceCommandHandler';
import { QueueManager } from '../domain/QueueManager';
import { YouTubeService } from '../services/YouTubeService';
import { PlaybackStrategyManager } from '../services/PlaybackStrategyManager';
import { RedisClient } from '../services/RedisClient';
import { ErrorHandler } from '../services/ErrorHandler';
import { MonitoringService } from '../services/MonitoringService';
import { SearchResultHandler } from '../services/SearchResultHandler';
import { KanyeResponseGenerator } from '../services/KanyeResponseGenerator';
import { Track, YouTubeVideo, VoiceCommand } from '../domain/types';

export class MusicBot {
  private client: Client;
  private commandHandler: CommandHandler;
  private buttonHandler: ButtonHandler;
  private voiceManager: VoiceManager;
  private voiceCommandHandler: VoiceCommandHandler | null = null;
  private queueManager: QueueManager;
  private youtubeService: YouTubeService;
  private playbackStrategy: PlaybackStrategyManager;
  private redis: RedisClient;
  private errorHandler: ErrorHandler;
  private monitoringService: MonitoringService;
  private searchResultHandler: SearchResultHandler;
  private kanyeResponseGenerator: KanyeResponseGenerator;

  constructor() {
    this.client = new Client({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildVoiceStates,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
      ]
    });
    
    this.redis = new RedisClient();
    this.queueManager = new QueueManager();
    this.youtubeService = new YouTubeService();
    this.errorHandler = new ErrorHandler(this.redis);
    this.playbackStrategy = new PlaybackStrategyManager(this.redis);
    this.voiceManager = new VoiceManager(this.playbackStrategy);
    this.searchResultHandler = new SearchResultHandler(this.redis);
    this.commandHandler = new CommandHandler(this);
    this.buttonHandler = new ButtonHandler(this);
    this.monitoringService = new MonitoringService(this.client, this.redis);
    this.kanyeResponseGenerator = new KanyeResponseGenerator();
    
    // Setup food talk event handling
    this.setupFoodTalkHandling();
    
    // Initialize voice commands if enabled OR if TTS is enabled (TTS requires voice commands)
    const voiceExplicitlyEnabled = process.env.ENABLE_VOICE_COMMANDS === 'true';
    const ttsEnabled = process.env.TTS_ENABLED === 'true';
    const voiceEnabled = voiceExplicitlyEnabled || ttsEnabled;
    
    if (voiceEnabled && process.env.OPENAI_API_KEY) {
      this.voiceCommandHandler = new VoiceCommandHandler();
      this.setupVoiceCommandHandling();
      logger.info('[MusicBot] Voice commands enabled' + (ttsEnabled ? ' (auto-enabled due to TTS)' : ''));
    } else if (voiceEnabled && !process.env.OPENAI_API_KEY) {
      logger.warn('[MusicBot] Voice commands requested but OPENAI_API_KEY not provided');
    } else {
      logger.info('[MusicBot] Voice commands disabled - Set ENABLE_VOICE_COMMANDS=true or TTS_ENABLED=true and provide OPENAI_API_KEY to enable');
    }
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

    this.client.on('messageCreate', async (message) => {
      await this.handleMessage(message);
    });
  }

  async start() {
    await this.client.login(process.env.DISCORD_TOKEN);
  }

  private async handleMessage(message: Message): Promise<void> {
    try {
      // Ignore messages from bots (including our own)
      if (message.author.bot) return;

      // Only respond with a small random chance to avoid spam
      const shouldRespond = Math.random() < 0.15; // 15% chance
      if (!shouldRespond) return;

      const content = message.content.toLowerCase();
      
      // Check for food-related keywords
      const foodKeywords = {
        watermelon: ['watermelon', 'melon'],
        friedChicken: ['chicken', 'fried chicken', 'kfc', 'popeyes'],
        koolAid: ['kool aid', 'koolaid', 'kool-aid']
      };

      // Check for talk/chat triggers
      const talkTriggers = ['talk', 'chat', 'say something', 'speak'];
      const shouldTalk = talkTriggers.some(trigger => content.includes(trigger));

      let response = '';

      // Check for specific food mentions
      for (const [foodType, keywords] of Object.entries(foodKeywords)) {
        if (keywords.some(keyword => content.includes(keyword))) {
          response = this.kanyeResponseGenerator.generateFoodResponse(foodType as 'watermelon' | 'friedChicken' | 'koolAid');
          break;
        }
      }

      // If no specific food found but user wants to talk, use general food response
      if (!response && shouldTalk) {
        response = this.kanyeResponseGenerator.generateFoodResponse('general');
      }

      // Send response if we have one
      if (response) {
        logger.info(`[MusicBot] Responding to message in ${message.guild?.name || 'DM'}: "${content}"`);
        await message.reply(response);
      }
    } catch (error) {
      logger.error('[MusicBot] Error handling message:', error);
    }
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
      await interaction.editReply('No results found for your search!');
      return;
    }

    // Create search session and show selection interface (limit to 4 results for button constraints)
    const displayVideos = videos.slice(0, 4);
    const sessionId = await this.searchResultHandler.createSearchSession(
      interaction.user.id,
      interaction.guildId!,
      query,
      displayVideos
    );

    const embed = this.searchResultHandler.createSearchEmbed(query, displayVideos);
    const buttons = this.searchResultHandler.createSelectionButtons(sessionId, displayVideos.length);

    await interaction.editReply({
      embeds: [embed],
      components: [buttons]
    });
  }

  async playSelectedVideo(video: YouTubeVideo, interaction: CommandInteraction) {
    const member = interaction.guild?.members.cache.get(interaction.user.id);
    const voiceChannel = member?.voice.channel as VoiceChannel;
    
    if (!voiceChannel) {
      await interaction.editReply('You need to be in a voice channel!');
      return;
    }

    const track: Track = {
      id: video.id,
      title: video.title,
      url: video.url,
      duration: video.duration,
      thumbnail: video.thumbnail,
      requestedBy: interaction.user.id
    };

    await this.addToQueue(track);
    
    if (!this.voiceManager.isPlaying(interaction.guildId!)) {
      logger.info(`[MusicBot.playSelectedVideo] Before join - guildId: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
      const connection = await this.voiceManager.join(voiceChannel);
      
      // Automatically start voice listening when we join (if voice commands are enabled)
      if (this.voiceCommandHandler) {
        logger.info(`[MusicBot] Starting voice listening automatically`);
        await this.voiceCommandHandler.startListening(voiceChannel, connection);
      }
      
      logger.info(`[MusicBot.playSelectedVideo] Before playNext - guildId: ${interaction.guildId}, type: ${typeof interaction.guildId}`);
      await this.playNext(interaction.guildId!);
    }
    
    await interaction.editReply({
      content: `Added to queue: **${track.title}**`,
      embeds: [],
      components: []
    });
  }

  async playSelectedVideoFromButton(video: YouTubeVideo, guildId: string, userId: string): Promise<{ success: boolean; message: string }> {
    try {
      // Get guild and member
      const guild = this.client.guilds.cache.get(guildId);
      if (!guild) {
        return { success: false, message: 'Guild not found!' };
      }

      const member = guild.members.cache.get(userId);
      if (!member) {
        return { success: false, message: 'Member not found!' };
      }

      const voiceChannel = member.voice.channel as VoiceChannel;
      if (!voiceChannel) {
        return { success: false, message: 'You need to be in a voice channel!' };
      }

      const track: Track = {
        id: video.id,
        title: video.title,
        url: video.url,
        duration: video.duration,
        thumbnail: video.thumbnail,
        requestedBy: userId
      };

      await this.addToQueue(track);
      
      if (!this.voiceManager.isPlaying(guildId)) {
        logger.info(`[MusicBot.playSelectedVideoFromButton] Before join - guildId: ${guildId}`);
        const connection = await this.voiceManager.join(voiceChannel);
        
        // Automatically start voice listening when we join (if voice commands are enabled)
        if (this.voiceCommandHandler) {
          logger.info(`[MusicBot] Starting voice listening automatically`);
          await this.voiceCommandHandler.startListening(voiceChannel, connection);
        }
        
        logger.info(`[MusicBot.playSelectedVideoFromButton] Before playNext - guildId: ${guildId}`);
        await this.playNext(guildId);
      }
      
      return { success: true, message: `🎵 Added to queue: **${track.title}**` };
    } catch (error) {
      logger.error('Error playing selected video from button:', error);
      return { success: false, message: 'An error occurred while adding the song to queue' };
    }
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
      // Don't leave the voice channel here - let the idle timer handle disconnection
      logger.info(`[MusicBot.playNext] No tracks in queue for guild ${guildId}, staying connected`);
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

  getKanyeResponseGenerator() {
    return this.kanyeResponseGenerator;
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

  isVoiceCommandsEnabled(): boolean {
    return this.voiceCommandHandler !== null;
  }

  private setupVoiceCommandHandling(): void {
    if (!this.voiceCommandHandler) return;
    
    this.voiceCommandHandler.on('voiceCommand', async (voiceCommand: VoiceCommand) => {
      await this.handleVoiceCommand(voiceCommand);
    });
  }

  private setupFoodTalkHandling(): void {
    // Keep food talk event for backward compatibility
    this.voiceManager.on('idleFoodTalk', async (data: { guildId: string }) => {
      await this.handleIdleFoodTalk(data.guildId);
    });
    
    // New random talk event handler
    this.voiceManager.on('idleRandomTalk', async (data: { guildId: string }) => {
      await this.handleIdleRandomTalk(data.guildId);
    });
  }

  private async handleIdleFoodTalk(guildId: string): Promise<void> {
    try {
      // Only proceed if TTS is enabled and voice commands are active
      if (!this.voiceCommandHandler) {
        logger.info(`🍗 [FOOD_TALK] Guild ${guildId}: No voice command handler, skipping food talk`);
        return;
      }

      // Check if we're still connected to voice channel
      const voiceChannel = this.voiceManager.getVoiceChannel(guildId);
      if (!voiceChannel) {
        logger.info(`🍗 [FOOD_TALK] Guild ${guildId}: Not in voice channel, skipping food talk`);
        return;
      }

      // Double-check that we're actually idle (not playing music)
      if (this.voiceManager.isPlaying(guildId)) {
        logger.info(`🍗 [FOOD_TALK] Guild ${guildId}: Music is playing, skipping food talk`);
        return;
      }

      // Generate random food talk
      const foodTalk = this.kanyeResponseGenerator.generateRandomFoodTalk();
      logger.info(`🍗 [FOOD_TALK] Guild ${guildId}: Generated food talk: "${foodTalk}"`);

      // Send through TTS system
      await this.voiceCommandHandler.speakResponse(guildId, { 
        command: 'food'
      });
      
      logger.info(`🍗 [FOOD_TALK] Guild ${guildId}: Successfully sent food talk via TTS`);
    } catch (error) {
      logger.error(`🍗 [FOOD_TALK] Guild ${guildId}: Error during food talk:`, error);
    }
  }

  private async handleIdleRandomTalk(guildId: string): Promise<void> {
    try {
      // Only proceed if TTS is enabled and voice commands are active
      if (!this.voiceCommandHandler) {
        logger.info(`🎭 [RANDOM_TALK] Guild ${guildId}: No voice command handler, skipping random talk`);
        return;
      }

      const voiceChannel = this.voiceManager.getVoiceChannel(guildId);
      if (!voiceChannel) {
        logger.info(`🎭 [RANDOM_TALK] Guild ${guildId}: Not in voice channel, skipping random talk`);
        return;
      }

      // Generate random talk (includes food, music, life, thoughts, vibes)
      const randomTalk = this.kanyeResponseGenerator.generateRandomTalk();
      logger.info(`🎭 [RANDOM_TALK] Guild ${guildId}: Generated random talk: "${randomTalk}"`);

      // Send through TTS system by calling the private playTTSResponse method
      // We need to access the private method, so we'll use the same approach as food talk
      await (this.voiceCommandHandler as any).playTTSResponse(guildId, randomTalk);
      
      logger.info(`🎭 [RANDOM_TALK] Guild ${guildId}: Successfully sent random talk via TTS`);
    } catch (error) {
      logger.error(`🎭 [RANDOM_TALK] Guild ${guildId}: Error during random talk:`, error);
    }
  }

  private async handleVoiceCommand(voiceCommand: VoiceCommand): Promise<void> {
    try {
      logger.info(`[MusicBot] Processing voice command: ${voiceCommand.command} from user ${voiceCommand.userId}`);

      const guild = this.client.guilds.cache.get(voiceCommand.guildId);
      if (!guild) {
        logger.error(`[MusicBot] Guild ${voiceCommand.guildId} not found`);
        return;
      }

      const member = guild.members.cache.get(voiceCommand.userId);
      if (!member) {
        logger.error(`[MusicBot] Member ${voiceCommand.userId} not found in guild ${voiceCommand.guildId}`);
        return;
      }

      const voiceChannel = member.voice.channel as VoiceChannel;
      if (!voiceChannel) {
        logger.warn(`[MusicBot] User ${voiceCommand.userId} not in a voice channel`);
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
          logger.warn(`[MusicBot] Unknown voice command: ${voiceCommand.command}`);
      }
    } catch (error) {
      logger.error('[MusicBot] Error handling voice command:', error);
    }
  }

  private async handleVoicePlayCommand(voiceCommand: VoiceCommand, voiceChannel: VoiceChannel): Promise<void> {
    const query = voiceCommand.parameters.join(' ');
    if (!query) {
      logger.warn('[MusicBot] Voice play command received without query');
      return;
    }

    try {
      const videos = await this.searchYouTube(query);
      if (videos.length === 0) {
        logger.info(`[MusicBot] No results found for voice query: "${query}"`);
        
        // Send TTS error response
        if (this.voiceCommandHandler) {
          await this.voiceCommandHandler.speakResponse(voiceCommand.guildId, {
            command: 'play',
            error: 'not found'
          });
        }
        return;
      }

      // For voice commands, automatically select the first result
      const selectedVideo = videos[0];
      const track: Track = {
        id: selectedVideo.id,
        title: selectedVideo.title,
        url: selectedVideo.url,
        duration: selectedVideo.duration,
        thumbnail: selectedVideo.thumbnail,
        requestedBy: voiceCommand.userId
      };

      await this.addToQueue(track);
      
      if (!this.voiceManager.isPlaying(voiceCommand.guildId)) {
        // Start voice listening when we join the channel
        const connection = await this.voiceManager.join(voiceChannel);
        if (this.voiceCommandHandler) {
          await this.voiceCommandHandler.startListening(voiceChannel, connection);
        }
        await this.playNext(voiceCommand.guildId);
      }

      logger.info(`[MusicBot] Voice command added track: ${track.title}`);
      
      // Send TTS confirmation with song title
      logger.info(`[MusicBot] Checking if TTS response should be sent...`);
      if (this.voiceCommandHandler) {
        logger.info(`[MusicBot] VoiceCommandHandler exists, sending TTS response for song: ${track.title}`);
        await this.voiceCommandHandler.speakResponse(voiceCommand.guildId, {
          command: 'play',
          songTitle: track.title
        });
      } else {
        logger.warn(`[MusicBot] No VoiceCommandHandler available for TTS response`);
      }
    } catch (error) {
      logger.error('[MusicBot] Error handling voice play command:', error);
    }
  }

  private async handleVoiceSkipCommand(voiceCommand: VoiceCommand): Promise<void> {
    try {
      await this.skip(voiceCommand.guildId);
      logger.info(`[MusicBot] Voice command skipped track in guild ${voiceCommand.guildId}`);
    } catch (error) {
      logger.error('[MusicBot] Error handling voice skip command:', error);
    }
  }

  private async handleVoiceStopCommand(voiceCommand: VoiceCommand): Promise<void> {
    try {
      if (this.voiceCommandHandler) {
        await this.voiceCommandHandler.stopListening(voiceCommand.guildId);
      }
      await this.stop(voiceCommand.guildId);
      logger.info(`[MusicBot] Voice command stopped playback in guild ${voiceCommand.guildId}`);
    } catch (error) {
      logger.error('[MusicBot] Error handling voice stop command:', error);
    }
  }

  private async handleVoicePauseCommand(voiceCommand: VoiceCommand): Promise<void> {
    // Note: Current VoiceManager doesn't have pause functionality
    // This would need to be implemented in VoiceManager
    logger.info(`[MusicBot] Voice pause command received (not implemented)`);
  }

  private async handleVoiceResumeCommand(voiceCommand: VoiceCommand): Promise<void> {
    // Note: Current VoiceManager doesn't have resume functionality
    // This would need to be implemented in VoiceManager
    logger.info(`[MusicBot] Voice resume command received (not implemented)`);
  }

  private async handleVoiceQueueCommand(voiceCommand: VoiceCommand): Promise<void> {
    // For voice commands, we could potentially announce the queue via TTS
    // For now, just log it
    const queue = this.queueManager.getQueue();
    logger.info(`[MusicBot] Voice queue command - ${queue.length} tracks in queue`);
  }

  // Method to enable voice commands in a voice channel
  async enableVoiceCommands(voiceChannel: VoiceChannel): Promise<void> {
    if (!this.voiceCommandHandler) {
      throw new Error('Voice commands are not enabled. Set ENABLE_VOICE_COMMANDS=true and provide OPENAI_API_KEY.');
    }
    
    try {
      if (!this.voiceManager.isPlaying(voiceChannel.guild.id)) {
        const connection = await this.voiceManager.join(voiceChannel);
        await this.voiceCommandHandler.startListening(voiceChannel, connection);
      }
      logger.info(`[MusicBot] Voice commands enabled in ${voiceChannel.name}`);
    } catch (error) {
      logger.error('[MusicBot] Failed to enable voice commands:', error);
      throw error;
    }
  }

  // Method to disable voice commands in a guild
  async disableVoiceCommands(guildId: string): Promise<void> {
    if (!this.voiceCommandHandler) {
      logger.warn('[MusicBot] Voice commands are not enabled, nothing to disable');
      return;
    }
    
    try {
      await this.voiceCommandHandler.stopListening(guildId);
      logger.info(`[MusicBot] Voice commands disabled for guild ${guildId}`);
    } catch (error) {
      logger.error('[MusicBot] Failed to disable voice commands:', error);
    }
  }

  // Check if voice commands are active in a guild
  isVoiceCommandsActive(guildId: string): boolean {
    if (!this.voiceCommandHandler) return false;
    return this.voiceCommandHandler.isListening(guildId);
  }

  // Cost monitoring methods for voice commands
  getVoiceCostStats() {
    if (!this.voiceCommandHandler) {
      return {
        totalRequests: 0,
        totalMinutesProcessed: 0,
        estimatedCost: 0,
        averageCostPerRequest: 0,
        lastRequestTime: 0
      };
    }
    return this.voiceCommandHandler.getCostStats();
  }

  logVoiceCostSummary(): void {
    if (!this.voiceCommandHandler) {
      logger.info('[MusicBot] Voice commands not enabled - no costs to report');
      return;
    }
    this.voiceCommandHandler.logCostSummary();
  }

  resetVoiceCostTracking(): void {
    if (!this.voiceCommandHandler) return;
    this.voiceCommandHandler.resetCostTracking();
  }

  async getVoiceHealthCheck() {
    if (!this.voiceCommandHandler) {
      return {
        status: 'disabled',
        message: 'Voice commands not enabled',
        services: {
          voiceListener: false,
          wakeWordDetection: false,
          speechRecognition: false
        },
        stats: {},
        costOptimization: {}
      };
    }
    return this.voiceCommandHandler.healthCheck();
  }
}