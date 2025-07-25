import { VoiceConnection, EndBehaviorType } from '@discordjs/voice';
import { User, VoiceChannel } from 'discord.js';
import { EventEmitter } from 'events';
import { AudioSegment, VoiceSession } from '../domain/types';
import { logger } from './logger';
import { AudioProcessingService } from './AudioProcessingService';

interface VoiceReceiver {
  connection: VoiceConnection;
  channel: VoiceChannel;
  activeUsers: Map<string, User>;
  audioBuffer: Map<string, Buffer[]>;
  lastActivity: Map<string, number>;
}

export class VoiceListenerService extends EventEmitter {
  private receivers: Map<string, VoiceReceiver> = new Map();
  private sessions: Map<string, VoiceSession> = new Map();
  private readonly bufferTimeout: number = 3000; // 3 seconds
  private readonly maxBufferSize: number = 1024 * 1024; // 1MB
  private cleanupIntervals: Map<string, NodeJS.Timeout> = new Map();

  constructor() {
    super();
    this.setupCleanupRoutine();
  }

  async startListening(connection: VoiceConnection, channel: VoiceChannel): Promise<void> {
    const guildId = channel.guild.id;
    
    try {
      logger.info(`[VoiceListenerService] 🎯 Starting voice listening for guild ${guildId} in channel ${channel.name}`);
      logger.info(`[VoiceListenerService] Connection state: ${connection.state.status}`);
      logger.info(`[VoiceListenerService] Members in channel: ${channel.members.size}`);

      // Create voice receiver
      const receiver: VoiceReceiver = {
        connection,
        channel,
        activeUsers: new Map(),
        audioBuffer: new Map(),
        lastActivity: new Map()
      };

      this.receivers.set(guildId, receiver);

      // Configure voice receiving
      const voiceReceiver = connection.receiver;
      
      if (!voiceReceiver) {
        logger.error(`[VoiceListenerService] No voice receiver available for connection`);
        throw new Error('Voice receiver not available');
      }
      
      if (!voiceReceiver.speaking) {
        logger.error(`[VoiceListenerService] No speaking detector available`);
        throw new Error('Speaking detector not available');
      }

      // Listen for speaking events
      voiceReceiver.speaking.on('start', (userId) => {
        logger.debug(`[VoiceListenerService] 🎤 Speaking START event for user ${userId}`);
        this.handleSpeakingStart(guildId, userId);
      });

      voiceReceiver.speaking.on('end', (userId) => {
        logger.debug(`[VoiceListenerService] 🔇 Speaking END event for user ${userId}`);
        this.handleSpeakingEnd(guildId, userId);
      });

      // Set up audio stream handling for each user
      this.setupUserAudioStreams(guildId, voiceReceiver);

      // Start cleanup routine for this guild
      this.startCleanupRoutine(guildId);

      logger.info(`[VoiceListenerService] ✅ Voice listening ACTIVE for guild ${guildId}`);
      logger.info(`[VoiceListenerService] Registered receivers: ${this.receivers.size}`);
      this.emit('listeningStarted', { guildId, channelId: channel.id });

    } catch (error) {
      logger.error(`[VoiceListenerService] ❌ Failed to start listening in guild ${guildId}:`, error);
      logger.error(`[VoiceListenerService] Stack trace:`, error instanceof Error ? error.stack : 'No stack');
      throw error;
    }
  }

  private setupUserAudioStreams(guildId: string, voiceReceiver: any): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    // Monitor for new users joining voice (if connection exists)
    if (voiceReceiver.connection) {
      voiceReceiver.connection.on('stateChange', () => {
        // Refresh user streams when connection state changes
        setTimeout(() => this.refreshUserStreams(guildId), 1000);
      });
    } else {
      logger.debug(`[VoiceListenerService] No connection object on voiceReceiver for monitoring state changes`);
    }

    // Initial setup of user streams
    this.refreshUserStreams(guildId);
  }

  private refreshUserStreams(guildId: string): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) {
      logger.warn(`[VoiceListenerService] No receiver found for guild ${guildId}`);
      return;
    }

    const voiceReceiver = receiver.connection.receiver;
    if (!voiceReceiver) {
      logger.warn(`[VoiceListenerService] No voice receiver available for guild ${guildId}`);
      return;
    }
    
    logger.info(`[VoiceListenerService] Refreshing user streams for guild ${guildId}`);
    logger.info(`[VoiceListenerService] Channel members: ${receiver.channel.members.size}`);
    
    // Get all users in the voice channel
    receiver.channel.members.forEach((member) => {
      if (member.user.bot) {
        logger.debug(`[VoiceListenerService] Skipping bot user: ${member.user.tag}`);
        return;
      }
      
      const userId = member.user.id;
      if (!receiver.activeUsers.has(userId)) {
        logger.info(`[VoiceListenerService] 👤 Setting up audio stream for user: ${member.user.tag} (${userId})`);
        receiver.activeUsers.set(userId, member.user);
        receiver.audioBuffer.set(userId, []);
        receiver.lastActivity.set(userId, Date.now());

        // Create audio stream for this user
        const audioStream = voiceReceiver.subscribe(userId, {
          end: {
            behavior: EndBehaviorType.AfterSilence,
            duration: 1000 // 1 second of silence
          }
        });

        this.setupAudioStreamHandlers(guildId, userId, audioStream);
        logger.info(`[VoiceListenerService] ✅ Started listening to user ${member.user.tag} in guild ${guildId}`);
      } else {
        logger.debug(`[VoiceListenerService] User ${member.user.tag} already has active stream`);
      }
    });
    logger.info(`[VoiceListenerService] Active users being monitored: ${receiver.activeUsers.size}`);
  }

  private setupAudioStreamHandlers(guildId: string, userId: string, audioStream: any): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    let packetCount = 0;
    audioStream.on('data', (chunk: Buffer) => {
      packetCount++;
      if (packetCount % 100 === 0) {
        logger.debug(`[VoiceListenerService] 📊 Received ${packetCount} audio packets from user ${userId}`);
      }
      this.handleAudioData(guildId, userId, chunk);
    });

    audioStream.on('end', () => {
      logger.info(`[VoiceListenerService] 🎬 Audio stream ended for user ${userId} - Total packets: ${packetCount}`);
      this.processAudioBuffer(guildId, userId);
    });

    audioStream.on('error', (error: Error) => {
      logger.error(`[VoiceListenerService] ❌ Audio stream error for user ${userId} in guild ${guildId}:`, error);
      logger.error(`[VoiceListenerService] Error details:`, error.message);
    });
  }

  private handleSpeakingStart(guildId: string, userId: string): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    receiver.lastActivity.set(userId, Date.now());
    logger.debug(`[VoiceListenerService] User ${userId} started speaking in guild ${guildId}`);
    
    this.emit('speakingStart', { guildId, userId });
  }

  private handleSpeakingEnd(guildId: string, userId: string): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    receiver.lastActivity.set(userId, Date.now());
    logger.debug(`[VoiceListenerService] User ${userId} stopped speaking in guild ${guildId}`);
    
    this.emit('speakingEnd', { guildId, userId });
    
    // Process accumulated audio after a short delay
    setTimeout(() => {
      this.processAudioBuffer(guildId, userId);
    }, 500);
  }

  private handleAudioData(guildId: string, userId: string, chunk: Buffer): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    const userBuffer = receiver.audioBuffer.get(userId);
    if (!userBuffer) {
      logger.warn(`[VoiceListenerService] No buffer found for user ${userId}`);
      return;
    }

    // Add chunk to buffer
    userBuffer.push(chunk);
    receiver.lastActivity.set(userId, Date.now());

    // Check buffer size limits
    const totalSize = userBuffer.reduce((sum, buf) => sum + buf.length, 0);
    if (totalSize > this.maxBufferSize) {
      logger.warn(`[VoiceListenerService] ⚠️ Buffer overflow for user ${userId} (${totalSize} bytes), processing early`);
      this.processAudioBuffer(guildId, userId);
    }
  }

  private processAudioBuffer(guildId: string, userId: string): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    const userBuffer = receiver.audioBuffer.get(userId);
    if (!userBuffer || userBuffer.length === 0) {
      logger.debug(`[VoiceListenerService] No audio buffer to process for user ${userId}`);
      return;
    }

    try {
      logger.info(`[VoiceListenerService] 🎙️ Processing audio buffer for user ${userId} - Chunks: ${userBuffer.length}`);
      
      // Combine all audio chunks
      const combinedAudio = Buffer.concat(userBuffer);
      logger.info(`[VoiceListenerService] Combined audio size: ${combinedAudio.length} bytes`);
      
      // Clear the buffer
      receiver.audioBuffer.set(userId, []);

      // Skip if audio is too short (likely noise)
      if (combinedAudio.length < 1600) { // ~33ms at 48kHz stereo 16-bit
        logger.debug(`[VoiceListenerService] Audio too short (${combinedAudio.length} bytes), skipping`);
        return;
      }

      // Create audio segment
      const audioSegment: AudioSegment = {
        id: `${guildId}_${userId}_${Date.now()}`,
        guildId,
        userId,
        audioData: combinedAudio,
        duration: combinedAudio.length / (48000 * 2 * 2), // 48kHz stereo 16-bit
        sampleRate: 48000,
        channels: 2,
        timestamp: Date.now(),
        isWakeWordDetected: false
      };

      logger.info(`[VoiceListenerService] 🎯 Created audio segment: ${audioSegment.id}`);
      logger.info(`[VoiceListenerService] Segment details - Duration: ${audioSegment.duration.toFixed(2)}s, Sample rate: ${audioSegment.sampleRate}Hz, Channels: ${audioSegment.channels}`);
      
      // Emit audio segment for processing
      this.emit('audioSegment', audioSegment);
      logger.info(`[VoiceListenerService] ✅ Emitted audio segment for processing`);

    } catch (error) {
      logger.error(`[VoiceListenerService] ❌ Error processing audio buffer for user ${userId}:`, error);
      logger.error(`[VoiceListenerService] Stack trace:`, error instanceof Error ? error.stack : 'No stack');
    }
  }

  async stopListening(guildId: string): Promise<void> {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    try {
      logger.info(`[VoiceListenerService] Stopping voice listening for guild ${guildId}`);

      // Process any remaining audio buffers
      receiver.audioBuffer.forEach((buffer, userId) => {
        if (buffer.length > 0) {
          this.processAudioBuffer(guildId, userId);
        }
      });

      // Clean up resources
      this.receivers.delete(guildId);
      this.stopCleanupRoutine(guildId);

      // Remove any active sessions
      const sessionsToRemove = Array.from(this.sessions.entries())
        .filter(([_, session]) => session.guildId === guildId)
        .map(([sessionId]) => sessionId);

      sessionsToRemove.forEach(sessionId => {
        this.sessions.delete(sessionId);
      });

      logger.info(`[VoiceListenerService] ✅ Voice listening stopped for guild ${guildId}`);
      logger.info(`[VoiceListenerService] Cleaned up ${sessionsToRemove.length} sessions`);
      this.emit('listeningStopped', { guildId });

    } catch (error) {
      logger.error(`[VoiceListenerService] Error stopping voice listening for guild ${guildId}:`, error);
    }
  }

  createVoiceSession(guildId: string, userId: string, channelId: string): string {
    const sessionId = `voice_${guildId}_${userId}_${Date.now()}`;
    
    const session: VoiceSession = {
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
    logger.info(`[VoiceListenerService] Created voice session ${sessionId}`);
    
    return sessionId;
  }

  updateSessionState(sessionId: string, state: VoiceSession['currentState']): void {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.currentState = state;
      session.lastActivityAt = Date.now();
    }
  }

  getActiveSession(guildId: string, userId: string): VoiceSession | null {
    return Array.from(this.sessions.values())
      .find(session => 
        session.guildId === guildId && 
        session.userId === userId && 
        session.isActive
      ) || null;
  }

  private setupCleanupRoutine(): void {
    // Global cleanup every 30 seconds
    setInterval(() => {
      this.cleanupInactiveSessions();
    }, 30000);
  }

  private startCleanupRoutine(guildId: string): void {
    this.stopCleanupRoutine(guildId);
    
    const interval = setInterval(() => {
      this.cleanupGuildBuffers(guildId);
    }, 10000); // Every 10 seconds

    this.cleanupIntervals.set(guildId, interval);
  }

  private stopCleanupRoutine(guildId: string): void {
    const interval = this.cleanupIntervals.get(guildId);
    if (interval) {
      clearInterval(interval);
      this.cleanupIntervals.delete(guildId);
    }
  }

  private cleanupGuildBuffers(guildId: string): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    const now = Date.now();
    
    receiver.lastActivity.forEach((lastActivity, userId) => {
      if (now - lastActivity > this.bufferTimeout) {
        const buffer = receiver.audioBuffer.get(userId);
        if (buffer && buffer.length > 0) {
          logger.debug(`[VoiceListenerService] Cleaning up stale buffer for user ${userId}`);
          this.processAudioBuffer(guildId, userId);
        }
      }
    });
  }

  private cleanupInactiveSessions(): void {
    const now = Date.now();
    const sessionTimeout = 10 * 60 * 1000; // 10 minutes

    Array.from(this.sessions.entries()).forEach(([sessionId, session]) => {
      if (now - session.lastActivityAt > sessionTimeout) {
        logger.info(`[VoiceListenerService] Cleaning up inactive session ${sessionId}`);
        this.sessions.delete(sessionId);
      }
    });
  }

  isListening(guildId: string): boolean {
    const listening = this.receivers.has(guildId);
    logger.debug(`[VoiceListenerService] isListening check for guild ${guildId}: ${listening}`);
    logger.debug(`[VoiceListenerService] Active receivers: ${Array.from(this.receivers.keys()).join(', ')}`);
    return listening;
  }

  getActiveGuilds(): string[] {
    return Array.from(this.receivers.keys());
  }

  getSessionCount(): number {
    return this.sessions.size;
  }
}