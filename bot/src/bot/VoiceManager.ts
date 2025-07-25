import { 
  VoiceConnection, 
  AudioPlayer, 
  createAudioPlayer,
  joinVoiceChannel,
  entersState,
  VoiceConnectionStatus,
  AudioPlayerStatus,
  createAudioResource
} from '@discordjs/voice';
import { VoiceChannel } from 'discord.js';
import { EventEmitter } from 'events';
import { Track } from '../domain/types';
import { PlaybackStrategyManager } from '../services/PlaybackStrategyManager';
import { logger } from '../services/logger';

export class VoiceManager extends EventEmitter {
  private connections: Map<string, VoiceConnection> = new Map();
  private players: Map<string, AudioPlayer> = new Map();
  private currentTracks: Map<string, Track> = new Map();
  private playbackStrategy: PlaybackStrategyManager;
  private disconnectTimers: Map<string, NodeJS.Timeout> = new Map();
  private voiceChannels: Map<string, VoiceChannel> = new Map();
  private idleTimeoutMs: number;

  constructor(playbackStrategy: PlaybackStrategyManager) {
    super();
    this.playbackStrategy = playbackStrategy;
    // Default to 5 minutes, but allow override via environment variable
    this.idleTimeoutMs = parseInt(process.env.VOICE_IDLE_TIMEOUT_MS || '300000', 10);
    logger.info(`VoiceManager initialized with idle timeout: ${this.idleTimeoutMs}ms (${this.idleTimeoutMs / 1000 / 60} minutes)`);
  }

  async join(channel: VoiceChannel): Promise<VoiceConnection> {
    const guildId = channel.guild.id;
    logger.info(`[VoiceManager.join] Called with channel.guild.id: ${guildId}, type: ${typeof guildId}`);
    logger.info(`Joining voice channel ${channel.name} in guild ${guildId}`);
    
    const connection = joinVoiceChannel({
      channelId: channel.id,
      guildId: channel.guild.id,
      adapterCreator: channel.guild.voiceAdapterCreator as any
    });

    connection.on(VoiceConnectionStatus.Disconnected, async () => {
      try {
        await Promise.race([
          entersState(connection, VoiceConnectionStatus.Signalling, 5_000),
          entersState(connection, VoiceConnectionStatus.Connecting, 5_000)
        ]);
      } catch (error) {
        logger.warn(`Connection to guild ${guildId} permanently lost, cleaning up`);
        
        // Stop and cleanup player before destroying connection
        const player = this.players.get(guildId);
        if (player) {
          player.stop(true);
          this.players.delete(guildId);
        }
        
        connection.destroy();
        this.connections.delete(guildId);
        this.voiceChannels.delete(guildId);
        this.currentTracks.delete(guildId);
        this.clearDisconnectTimer(guildId);
      }
    });
    
    // Add additional connection state monitoring
    connection.on(VoiceConnectionStatus.Destroyed, () => {
      logger.info(`Voice connection destroyed for guild ${guildId}`);
      this.connections.delete(guildId);
      this.voiceChannels.delete(guildId);
      this.currentTracks.delete(guildId);
      this.clearDisconnectTimer(guildId);
    });

    logger.info(`[VoiceManager.join] Storing connection for guildId: ${guildId}, type: ${typeof guildId}`);
    this.connections.set(guildId, connection);
    this.voiceChannels.set(guildId, channel);
    logger.info(`Successfully joined and stored voice channel for guild ${guildId}`);
    
    if (!this.players.has(guildId)) {
      const player = createAudioPlayer();
      
      player.on(AudioPlayerStatus.Idle, () => {
        logger.info(`Player became idle for guild ${guildId}`);
        this.emit('finish');
        this.startDisconnectTimer(guildId);
      });

      player.on(AudioPlayerStatus.Buffering, () => {
        logger.info(`Player buffering for guild ${guildId}`);
      });

      player.on(AudioPlayerStatus.Playing, () => {
        logger.info(`Player started playing for guild ${guildId}`);
        this.clearDisconnectTimer(guildId);
      });

      player.on(AudioPlayerStatus.AutoPaused, () => {
        logger.warn(`Player auto-paused for guild ${guildId}`);
      });
      
      player.on('error', error => {
        logger.error('Audio player error:', error);
        
        // Clean up current track and resources
        const currentTrack = this.currentTracks.get(guildId);
        if (currentTrack) {
          logger.warn(`Cleaning up aborted track: ${currentTrack.title}`);
          this.currentTracks.delete(guildId);
        }
        
        // Reset player state
        if (player.state.status !== AudioPlayerStatus.Idle) {
          player.stop(true); // Force stop
        }
        
        this.emit('error', error);
        
        // Attempt recovery after short delay
        setTimeout(() => {
          this.emit('finish'); // Trigger next track or cleanup
        }, 1000);
      });
      
      logger.info(`[VoiceManager.join] Storing player for guildId: ${guildId}, type: ${typeof guildId}`);
      this.players.set(guildId, player);
      connection.subscribe(player);
    }

    this.clearDisconnectTimer(guildId);
    return connection;
  }

  async leave(guildId: string) {
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

  async play(track: Track, guildId: string) {
    logger.info(`[VoiceManager.play] Called with guildId: ${guildId}, type: ${typeof guildId}`);
    logger.info(`Attempting to play track ${track.title} in guild ${guildId}`);
    
    logger.info(`[VoiceManager.play] Retrieving connection from map for guildId: ${guildId}`);
    logger.info(`[VoiceManager.play] connections Map keys: ${Array.from(this.connections.keys()).join(', ')}`);
    const connection = this.connections.get(guildId);
    if (!connection) {
      logger.error(`[VoiceManager.play] No connection found for guild ${guildId}, available keys: ${Array.from(this.connections.keys()).join(', ')}`);
      throw new Error('Not connected to any voice channel');
    }
    
    logger.info(`[VoiceManager.play] Retrieving player from map for guildId: ${guildId}`);
    logger.info(`[VoiceManager.play] players Map keys: ${Array.from(this.players.keys()).join(', ')}`);
    const player = this.players.get(guildId);
    if (!player) {
      logger.error(`[VoiceManager.play] No player found for guild ${guildId}, available keys: ${Array.from(this.players.keys()).join(', ')}`);
      throw new Error('No audio player found');
    }
    
    this.clearDisconnectTimer(guildId);
    
    logger.info(`[VoiceManager.play] Getting voice channel for guildId: ${guildId}`);
    const channel = this.getVoiceChannel(guildId);
    if (!channel) {
      logger.error(`[VoiceManager.play] No voice channel found for guild ${guildId}. Available guilds: ${Array.from(this.voiceChannels.keys()).join(', ')}`);
      throw new Error('Voice channel not found');
    }
    
    logger.info(`Voice channel found: ${channel.name}`);
    
    const playbackResult = await this.playbackStrategy.attemptPlayback(
      {
        id: track.id,
        title: track.title,
        url: track.url,
        duration: track.duration,
        thumbnail: track.thumbnail,
        channel: ''
      },
      channel
    );

    try {
      const resource = createAudioResource(playbackResult.stream, {
        inlineVolume: true,
        metadata: {
          title: track.title,
          guildId: guildId
        }
      });

      // Add resource error handling
      resource.playStream.on('error', (error) => {
        logger.error(`Stream error for ${track.title}:`, error);
        player.stop(true);
      });

      player.play(resource);
    } catch (error) {
      logger.error(`Failed to create audio resource for ${track.title}:`, error);
      playbackResult.stream.destroy();
      throw error;
    }
    logger.info(`[VoiceManager.play] Storing current track for guildId: ${guildId}, type: ${typeof guildId}`);
    this.currentTracks.set(guildId, track);
    logger.info(`Started playing ${track.title} in guild ${guildId}`);
  }

  skip(guildId: string) {
    logger.info(`[VoiceManager.skip] Called with guildId: ${guildId}, type: ${typeof guildId}`);
    const player = this.players.get(guildId);
    if (player) {
      player.stop();
    }
  }

  stop() {
    this.players.forEach(player => player.stop());
    this.connections.forEach((connection, guildId) => this.leave(guildId));
  }

  isPlaying(guildId: string): boolean {
    logger.info(`[VoiceManager.isPlaying] Called with guildId: ${guildId}, type: ${typeof guildId}`);
    const player = this.players.get(guildId);
    return player?.state.status === AudioPlayerStatus.Playing;
  }

  private getVoiceChannel(guildId: string): VoiceChannel | null {
    logger.info(`[VoiceManager.getVoiceChannel] Called with guildId: ${guildId}, type: ${typeof guildId}`);
    logger.info(`[VoiceManager.getVoiceChannel] voiceChannels Map keys: ${Array.from(this.voiceChannels.keys()).join(', ')}`);
    return this.voiceChannels.get(guildId) || null;
  }

  private startDisconnectTimer(guildId: string) {
    this.clearDisconnectTimer(guildId);
    
    logger.info(`Starting disconnect timer for guild ${guildId} - will disconnect in ${this.idleTimeoutMs / 1000} seconds`);
    const timer = setTimeout(() => {
      logger.info(`Auto-disconnecting from guild ${guildId} due to inactivity (timeout reached: ${this.idleTimeoutMs}ms)`);
      this.leave(guildId);
    }, this.idleTimeoutMs);
    
    this.disconnectTimers.set(guildId, timer);
  }

  private clearDisconnectTimer(guildId: string) {
    const timer = this.disconnectTimers.get(guildId);
    if (timer) {
      logger.info(`Clearing disconnect timer for guild ${guildId}`);
      clearTimeout(timer);
      this.disconnectTimers.delete(guildId);
    }
  }
}