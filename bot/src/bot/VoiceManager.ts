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
  private randomTalkTimers: Map<string, NodeJS.Timeout> = new Map();
  private randomTalkTriggered: Map<string, boolean> = new Map();
  private voiceChannels: Map<string, VoiceChannel> = new Map();
  private idleTimeoutMs: number;
  private connectionStates: Map<string, string> = new Map();

  constructor(playbackStrategy: PlaybackStrategyManager) {
    super();
    this.playbackStrategy = playbackStrategy;
    // Default to 5 minutes, but allow override via environment variable
    this.idleTimeoutMs = parseInt(process.env.VOICE_IDLE_TIMEOUT_MS || '300000', 10);
    logger.info(`🎵 VoiceManager initialized with idle timeout: ${this.idleTimeoutMs}ms (${this.idleTimeoutMs / 1000 / 60} minutes)`);
    
    // Log initial state
    this.logConnectionStatus();
  }

  private logConnectionStatus() {
    const activeConnections = this.connections.size;
    const activePlayers = this.players.size;
    const states = Array.from(this.connectionStates.entries())
      .map(([guildId, state]) => `${guildId}: ${state}`)
      .join(', ');
    
    logger.info(`📊 VoiceManager Status: ${activeConnections} connections, ${activePlayers} players | States: ${states || 'none'}`);
  }

  async join(channel: VoiceChannel): Promise<VoiceConnection> {
    const guildId = channel.guild.id;
    logger.info(`🎤 [JOIN] Starting voice channel join for guild ${guildId}`);
    logger.info(`📍 Channel: ${channel.name} (${channel.id}) | Members: ${channel.members.size}`);
    
    // Check if already connected
    const existingConnection = this.connections.get(guildId);
    if (existingConnection) {
      logger.warn(`⚠️ [JOIN] Already connected to guild ${guildId}, destroying old connection`);
      existingConnection.destroy();
    }
    
    const connection = joinVoiceChannel({
      channelId: channel.id,
      guildId: channel.guild.id,
      adapterCreator: channel.guild.voiceAdapterCreator as any
    });

    // Log initial state
    this.connectionStates.set(guildId, 'connecting');
    logger.info(`🔄 [CONNECTION] Guild ${guildId} state: connecting`);

    // Monitor all connection state changes
    connection.on(VoiceConnectionStatus.Ready, () => {
      this.connectionStates.set(guildId, 'ready');
      logger.info(`✅ [CONNECTION] Guild ${guildId} state: READY - Successfully connected!`);
      this.logConnectionStatus();
    });

    connection.on(VoiceConnectionStatus.Signalling, () => {
      this.connectionStates.set(guildId, 'signalling');
      logger.info(`📡 [CONNECTION] Guild ${guildId} state: SIGNALLING - Establishing connection...`);
    });

    connection.on(VoiceConnectionStatus.Connecting, () => {
      this.connectionStates.set(guildId, 'connecting');
      logger.info(`🔗 [CONNECTION] Guild ${guildId} state: CONNECTING - Setting up voice...`);
    });

    connection.on(VoiceConnectionStatus.Disconnected, async () => {
      this.connectionStates.set(guildId, 'disconnected');
      logger.warn(`🔌 [CONNECTION] Guild ${guildId} state: DISCONNECTED - Attempting recovery...`);
      
      try {
        logger.info(`🔄 [RECOVERY] Attempting to reconnect for guild ${guildId}...`);
        await Promise.race([
          entersState(connection, VoiceConnectionStatus.Signalling, 5_000),
          entersState(connection, VoiceConnectionStatus.Connecting, 5_000)
        ]);
        logger.info(`✅ [RECOVERY] Successfully recovered connection for guild ${guildId}`);
      } catch (error) {
        logger.error(`❌ [RECOVERY] Failed to recover connection for guild ${guildId}:`, error);
        logger.warn(`💀 [CONNECTION] Guild ${guildId} permanently lost, cleaning up resources`);
        
        // Stop and cleanup player before destroying connection
        const player = this.players.get(guildId);
        if (player) {
          logger.info(`🛑 [CLEANUP] Stopping audio player for guild ${guildId}`);
          player.stop(true);
          this.players.delete(guildId);
        }
        
        connection.destroy();
        this.connections.delete(guildId);
        this.voiceChannels.delete(guildId);
        this.currentTracks.delete(guildId);
        this.connectionStates.delete(guildId);
        this.clearDisconnectTimer(guildId);
        this.clearRandomTalkTimer(guildId);
        
        logger.info(`🧹 [CLEANUP] Completed cleanup for guild ${guildId}`);
        this.logConnectionStatus();
      }
    });
    
    // Add additional connection state monitoring
    connection.on(VoiceConnectionStatus.Destroyed, () => {
      this.connectionStates.set(guildId, 'destroyed');
      logger.info(`💥 [CONNECTION] Guild ${guildId} state: DESTROYED - Connection terminated`);
      this.connections.delete(guildId);
      this.voiceChannels.delete(guildId);
      this.currentTracks.delete(guildId);
      this.connectionStates.delete(guildId);
      this.clearDisconnectTimer(guildId);
      this.clearRandomTalkTimer(guildId);
      this.logConnectionStatus();
    });

    // Monitor connection errors
    connection.on('error', (error) => {
      logger.error(`🚨 [CONNECTION ERROR] Guild ${guildId}:`, error);
      logger.error(`Error details: ${JSON.stringify({
        message: error.message,
        stack: error.stack,
        state: this.connectionStates.get(guildId)
      })}`);
    });

    logger.info(`💾 [JOIN] Storing connection for guild ${guildId}`);
    this.connections.set(guildId, connection);
    this.voiceChannels.set(guildId, channel);
    logger.info(`✅ [JOIN] Successfully stored voice channel ${channel.name} for guild ${guildId}`);
    
    if (!this.players.has(guildId)) {
      logger.info(`🎵 [PLAYER] Creating new audio player for guild ${guildId}`);
      const player = createAudioPlayer();
      
      player.on(AudioPlayerStatus.Idle, () => {
        const track = this.currentTracks.get(guildId);
        logger.info(`⏸️ [PLAYER] Guild ${guildId} state: IDLE ${track ? `(finished: ${track.title})` : ''}`);
        this.emit('finish');
        this.startDisconnectTimer(guildId);
        this.startRandomTalkTimer(guildId);
      });

      player.on(AudioPlayerStatus.Buffering, () => {
        const track = this.currentTracks.get(guildId);
        logger.info(`⏳ [PLAYER] Guild ${guildId} state: BUFFERING ${track ? `(track: ${track.title})` : ''}`);
      });

      player.on(AudioPlayerStatus.Playing, () => {
        const track = this.currentTracks.get(guildId);
        logger.info(`▶️ [PLAYER] Guild ${guildId} state: PLAYING ${track ? `(track: ${track.title})` : '(TTS/unknown)'}`);
        this.clearDisconnectTimer(guildId);
        this.clearRandomTalkTimer(guildId);
      });

      player.on(AudioPlayerStatus.AutoPaused, () => {
        logger.warn(`⚠️ [PLAYER] Guild ${guildId} state: AUTO-PAUSED (connection issue?)`);
      });

      player.on(AudioPlayerStatus.Paused, () => {
        logger.info(`⏸️ [PLAYER] Guild ${guildId} state: PAUSED`);
      });
      
      player.on('error', error => {
        const currentTrack = this.currentTracks.get(guildId);
        logger.error(`🚨 [PLAYER ERROR] Guild ${guildId}:`, error);
        logger.error(`Error details: ${JSON.stringify({
          message: error.message,
          resource: error.resource?.metadata,
          track: currentTrack?.title || 'unknown',
          playerState: player.state.status
        })}`);
        
        // Clean up current track and resources
        if (currentTrack) {
          logger.warn(`🧹 [PLAYER ERROR] Cleaning up failed track: ${currentTrack.title}`);
          this.currentTracks.delete(guildId);
        }
        
        // Reset player state
        if (player.state.status !== AudioPlayerStatus.Idle) {
          logger.info(`🔄 [PLAYER ERROR] Force stopping player for guild ${guildId}`);
          player.stop(true); // Force stop
        }
        
        this.emit('error', error);
        
        // Attempt recovery after short delay
        setTimeout(() => {
          logger.info(`🔄 [PLAYER ERROR] Triggering finish event for recovery`);
          this.emit('finish'); // Trigger next track or cleanup
        }, 1000);
      });
      
      logger.info(`💾 [PLAYER] Storing player for guild ${guildId}`);
      this.players.set(guildId, player);
      connection.subscribe(player);
      logger.info(`🔌 [PLAYER] Subscribed player to connection for guild ${guildId}`);
    } else {
      logger.info(`♻️ [PLAYER] Reusing existing player for guild ${guildId}`);
    }

    this.clearDisconnectTimer(guildId);
    this.clearRandomTalkTimer(guildId);
    logger.info(`✅ [JOIN] Completed voice channel join for guild ${guildId}`);
    this.logConnectionStatus();
    return connection;
  }

  async leave(guildId: string) {
    logger.info(`👋 [LEAVE] Starting disconnect for guild ${guildId}`);
    
    const connection = this.connections.get(guildId);
    const player = this.players.get(guildId);
    const channel = this.voiceChannels.get(guildId);
    const track = this.currentTracks.get(guildId);
    
    logger.info(`📊 [LEAVE] Current state - Connection: ${connection ? 'exists' : 'none'}, Player: ${player ? 'exists' : 'none'}, Track: ${track?.title || 'none'}`);
    
    if (player) {
      logger.info(`🛑 [LEAVE] Stopping audio player for guild ${guildId}`);
      player.stop();
      this.players.delete(guildId);
      logger.info(`🗑️ [LEAVE] Audio player destroyed for guild ${guildId}`);
    }
    
    if (connection) {
      logger.info(`🔌 [LEAVE] Destroying voice connection for guild ${guildId}`);
      connection.destroy();
      this.connections.delete(guildId);
      logger.info(`💥 [LEAVE] Voice connection destroyed for guild ${guildId}`);
    }
    
    this.currentTracks.delete(guildId);
    this.voiceChannels.delete(guildId);
    this.connectionStates.delete(guildId);
    this.clearDisconnectTimer(guildId);
    this.clearRandomTalkTimer(guildId);
    
    logger.info(`✅ [LEAVE] Completed disconnect for guild ${guildId} ${channel ? `from ${channel.name}` : ''}`);
    this.logConnectionStatus();
  }

  async play(track: Track, guildId: string) {
    logger.info(`🎵 [PLAY] Starting playback for guild ${guildId}`);
    logger.info(`🎶 [PLAY] Track: "${track.title}" (${track.duration || 'unknown duration'})`);
    
    // Log current state
    this.logConnectionStatus();
    
    const connection = this.connections.get(guildId);
    if (!connection) {
      logger.error(`❌ [PLAY] No connection found for guild ${guildId}`);
      logger.error(`Available connections: ${Array.from(this.connections.keys()).join(', ')}`);
      throw new Error('Not connected to any voice channel');
    }
    
    const connectionState = this.connectionStates.get(guildId);
    logger.info(`📡 [PLAY] Connection state: ${connectionState || 'unknown'}`);
    
    const player = this.players.get(guildId);
    if (!player) {
      logger.error(`❌ [PLAY] No player found for guild ${guildId}`);
      logger.error(`Available players: ${Array.from(this.players.keys()).join(', ')}`);
      throw new Error('No audio player found');
    }
    
    logger.info(`🎵 [PLAY] Player state: ${player.state.status}`);
    
    this.clearDisconnectTimer(guildId);
    this.clearRandomTalkTimer(guildId);
    
    const channel = this.getVoiceChannel(guildId);
    if (!channel) {
      logger.error(`❌ [PLAY] No voice channel found for guild ${guildId}`);
      logger.error(`Available channels: ${Array.from(this.voiceChannels.keys()).join(', ')}`);
      throw new Error('Voice channel not found');
    }
    
    logger.info(`📍 [PLAY] Voice channel: ${channel.name} (${channel.members.size} members)`);
    
    logger.info(`🔄 [PLAY] Attempting playback with strategy...`);
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

    logger.info(`✅ [PLAY] Playback strategy succeeded, creating audio resource...`);

    try {
      const resource = createAudioResource(playbackResult.stream, {
        inlineVolume: true,
        metadata: {
          title: track.title,
          guildId: guildId
        }
      });

      logger.info(`📦 [PLAY] Audio resource created successfully`);

      // Add resource error handling
      resource.playStream.on('error', (error) => {
        logger.error(`🚨 [STREAM ERROR] Track "${track.title}" in guild ${guildId}:`, error);
        logger.error(`Stream error details: ${JSON.stringify({
          message: error.message,
          code: (error as any).code || 'unknown',
          syscall: (error as any).syscall || 'unknown'
        })}`);
        player.stop(true);
      });

      logger.info(`▶️ [PLAY] Sending audio resource to player...`);
      player.play(resource);
      
      // Store current track
      this.currentTracks.set(guildId, track);
      logger.info(`💾 [PLAY] Stored current track for guild ${guildId}`);
      
      logger.info(`✅ [PLAY] Successfully started playing "${track.title}" in guild ${guildId}`);
      this.logConnectionStatus();
      
    } catch (error) {
      logger.error(`❌ [PLAY] Failed to create audio resource for "${track.title}":`, error);
      logger.error(`Resource creation error details: ${JSON.stringify({
        message: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined
      })}`);
      
      try {
        playbackResult.stream.destroy();
        logger.info(`🧹 [PLAY] Cleaned up failed stream`);
      } catch (cleanupError) {
        logger.error(`❌ [PLAY] Failed to cleanup stream:`, cleanupError);
      }
      
      throw error;
    }
  }

  skip(guildId: string) {
    logger.info(`⏭️ [SKIP] Skipping track for guild ${guildId}`);
    
    const player = this.players.get(guildId);
    const track = this.currentTracks.get(guildId);
    
    if (player) {
      logger.info(`🛑 [SKIP] Stopping player for guild ${guildId} ${track ? `(current: ${track.title})` : ''}`);
      player.stop();
      logger.info(`✅ [SKIP] Player stopped successfully`);
    } else {
      logger.warn(`⚠️ [SKIP] No player found for guild ${guildId}`);
    }
  }

  stop() {
    logger.info(`🛑 [STOP] Stopping all voice connections (${this.connections.size} active)`);
    
    this.players.forEach((player, guildId) => {
      logger.info(`🛑 [STOP] Stopping player for guild ${guildId}`);
      player.stop();
    });
    
    this.connections.forEach((connection, guildId) => {
      logger.info(`👋 [STOP] Leaving voice channel for guild ${guildId}`);
      this.leave(guildId);
    });
    
    logger.info(`✅ [STOP] All voice connections stopped`);
  }

  isPlaying(guildId: string): boolean {
    const player = this.players.get(guildId);
    const isPlaying = player?.state.status === AudioPlayerStatus.Playing;
    const track = this.currentTracks.get(guildId);
    
    logger.info(`🎵 [IS_PLAYING] Guild ${guildId}: ${isPlaying ? 'YES' : 'NO'} ${track ? `(track: ${track.title})` : ''}`);
    
    return isPlaying;
  }

  async playTTS(stream: any, guildId: string, text: string) {
    logger.info(`🗣️ [TTS] Starting TTS playback for guild ${guildId}`);
    logger.info(`💬 [TTS] Text preview: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}"`);
    
    // Log current state
    this.logConnectionStatus();
    
    const connection = this.connections.get(guildId);
    if (!connection) {
      logger.error(`❌ [TTS] No connection found for guild ${guildId}`);
      throw new Error('Not connected to any voice channel');
    }
    
    const connectionState = this.connectionStates.get(guildId);
    logger.info(`📡 [TTS] Connection state: ${connectionState || 'unknown'}`);
    
    const player = this.players.get(guildId);
    if (!player) {
      logger.error(`❌ [TTS] No player found for guild ${guildId}`);
      throw new Error('No audio player found');
    }
    
    logger.info(`🎵 [TTS] Player state before TTS: ${player.state.status}`);
    
    this.clearDisconnectTimer(guildId);
    this.clearRandomTalkTimer(guildId);

    try {
      const resource = createAudioResource(stream, {
        inlineVolume: true,
        metadata: {
          title: `TTS: ${text.substring(0, 30)}...`,
          guildId: guildId,
          type: 'tts'
        }
      });

      logger.info(`📦 [TTS] Audio resource created successfully`);

      // Add resource error handling
      resource.playStream.on('error', (error) => {
        logger.error(`🚨 [TTS STREAM ERROR] Guild ${guildId}:`, error);
        player.stop(true);
      });

      logger.info(`▶️ [TTS] Sending TTS audio to player...`);
      player.play(resource);
      
      logger.info(`✅ [TTS] Successfully started TTS playback in guild ${guildId}`);
      this.logConnectionStatus();
      
    } catch (error) {
      logger.error(`❌ [TTS] Failed to play TTS audio:`, error);
      
      try {
        stream.destroy();
        logger.info(`🧹 [TTS] Cleaned up failed TTS stream`);
      } catch (cleanupError) {
        logger.error(`❌ [TTS] Failed to cleanup TTS stream:`, cleanupError);
      }
      
      throw error;
    }
  }

  getVoiceChannel(guildId: string): VoiceChannel | null {
    const channel = this.voiceChannels.get(guildId);
    
    if (channel) {
      logger.info(`📍 [GET_CHANNEL] Found voice channel for guild ${guildId}: ${channel.name}`);
    } else {
      logger.warn(`⚠️ [GET_CHANNEL] No voice channel found for guild ${guildId}`);
      logger.warn(`Available channels: ${Array.from(this.voiceChannels.keys()).join(', ')}`);
    }
    
    return channel || null;
  }

  private startDisconnectTimer(guildId: string) {
    this.clearDisconnectTimer(guildId);
    
    const timeoutSeconds = this.idleTimeoutMs / 1000;
    const timeoutMinutes = timeoutSeconds / 60;
    
    logger.info(`⏱️ [TIMER] Starting disconnect timer for guild ${guildId}`);
    logger.info(`⏰ [TIMER] Will auto-disconnect in ${timeoutSeconds}s (${timeoutMinutes}m) if idle`);
    
    const timer = setTimeout(() => {
      const channel = this.voiceChannels.get(guildId);
      logger.info(`⏰ [TIMER] Disconnect timer expired for guild ${guildId}`);
      logger.info(`🔌 [TIMER] Auto-disconnecting due to ${timeoutMinutes} minutes of inactivity`);
      
      if (channel) {
        logger.info(`👋 [TIMER] Leaving channel ${channel.name} in guild ${guildId}`);
      }
      
      this.leave(guildId);
    }, this.idleTimeoutMs);
    
    this.disconnectTimers.set(guildId, timer);
    logger.info(`✅ [TIMER] Timer set for guild ${guildId}`);
  }

  private clearDisconnectTimer(guildId: string) {
    const timer = this.disconnectTimers.get(guildId);
    if (timer) {
      logger.info(`🛑 [TIMER] Clearing disconnect timer for guild ${guildId} (activity detected)`);
      clearTimeout(timer);
      this.disconnectTimers.delete(guildId);
    }
  }

  private startRandomTalkTimer(guildId: string) {
    this.clearRandomTalkTimer(guildId);
    
    // Reset the random talk trigger flag for new idle period
    this.randomTalkTriggered.set(guildId, false);
    
    // Random delay between 30-90 minutes (within 1 hour window)
    const randomDelay = 1800000 + Math.random() * 3600000; // 30-90 minutes
    
    logger.info(`🎭 [RANDOM_TALK] Starting random talk timer for guild ${guildId}`);
    logger.info(`⏰ [RANDOM_TALK] Will randomly talk in ${Math.round(randomDelay / 60000)}m if still idle`);
    
    const timer = setTimeout(() => {
      // Check if still idle (not playing music) and hasn't talked yet this idle period
      const player = this.players.get(guildId);
      const isIdle = !player || player.state.status === 'idle';
      const hasTriggered = this.randomTalkTriggered.get(guildId);
      
      if (isIdle && !hasTriggered) {
        logger.info(`🎭 [RANDOM_TALK] Random talk timer expired for guild ${guildId} - emitting random talk event`);
        this.randomTalkTriggered.set(guildId, true);
        this.emit('idleRandomTalk', { guildId });
      } else if (hasTriggered) {
        logger.info(`🎭 [RANDOM_TALK] Guild ${guildId} already had random talk this idle period, skipping`);
      } else {
        logger.info(`🎭 [RANDOM_TALK] Guild ${guildId} no longer idle, skipping random talk`);
      }
    }, randomDelay);
    
    this.randomTalkTimers.set(guildId, timer);
    logger.info(`✅ [RANDOM_TALK] Random talk timer set for guild ${guildId}`);
  }

  private clearRandomTalkTimer(guildId: string) {
    const timer = this.randomTalkTimers.get(guildId);
    if (timer) {
      logger.info(`🛑 [RANDOM_TALK] Clearing random talk timer for guild ${guildId} (activity detected)`);
      clearTimeout(timer);
      this.randomTalkTimers.delete(guildId);
      this.randomTalkTriggered.delete(guildId);
    }
  }

  // Utility method to get complete status for a guild
  getGuildStatus(guildId: string): any {
    const connection = this.connections.get(guildId);
    const player = this.players.get(guildId);
    const channel = this.voiceChannels.get(guildId);
    const track = this.currentTracks.get(guildId);
    const connectionState = this.connectionStates.get(guildId);
    const hasTimer = this.disconnectTimers.has(guildId);
    const hasRandomTalkTimer = this.randomTalkTimers.has(guildId);
    const randomTalkTriggered = this.randomTalkTriggered.get(guildId) || false;

    const status = {
      guildId,
      connection: {
        exists: !!connection,
        state: connectionState || 'none',
        ping: connection?.ping || null
      },
      player: {
        exists: !!player,
        state: player?.state.status || 'none',
        canPlay: player?.state.status === AudioPlayerStatus.Idle || player?.state.status === AudioPlayerStatus.Playing
      },
      channel: {
        exists: !!channel,
        name: channel?.name || null,
        members: channel?.members.size || 0
      },
      currentTrack: track ? {
        title: track.title,
        duration: track.duration
      } : null,
      hasDisconnectTimer: hasTimer,
      hasRandomTalkTimer: hasRandomTalkTimer,
      randomTalkTriggered: randomTalkTriggered
    };

    logger.info(`📊 [STATUS] Guild ${guildId} full status:`, JSON.stringify(status, null, 2));
    
    return status;
  }

  // Method to handle connection health checks
  async checkConnectionHealth(guildId: string): Promise<boolean> {
    logger.info(`🏥 [HEALTH] Checking connection health for guild ${guildId}`);
    
    const connection = this.connections.get(guildId);
    const player = this.players.get(guildId);
    const state = this.connectionStates.get(guildId);
    
    if (!connection) {
      logger.warn(`❌ [HEALTH] No connection found for guild ${guildId}`);
      return false;
    }
    
    if (!player) {
      logger.warn(`❌ [HEALTH] No player found for guild ${guildId}`);
      return false;
    }
    
    const isHealthy = state === 'ready' && 
                     connection.state.status === VoiceConnectionStatus.Ready &&
                     (player.state.status === AudioPlayerStatus.Idle || 
                      player.state.status === AudioPlayerStatus.Playing ||
                      player.state.status === AudioPlayerStatus.Buffering);
    
    logger.info(`💚 [HEALTH] Guild ${guildId} health check: ${isHealthy ? 'HEALTHY' : 'UNHEALTHY'}`);
    logger.info(`📋 [HEALTH] Details - Connection: ${connection.state.status}, Player: ${player.state.status}, State: ${state}`);
    
    return isHealthy;
  }

}