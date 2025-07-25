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
      logger.info(`[VoiceListenerService] Starting voice listening for guild ${guildId}`);

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

      // Listen for speaking events
      voiceReceiver.speaking.on('start', (userId) => {
        this.handleSpeakingStart(guildId, userId);
      });

      voiceReceiver.speaking.on('end', (userId) => {
        this.handleSpeakingEnd(guildId, userId);
      });

      // Set up audio stream handling for each user
      this.setupUserAudioStreams(guildId, voiceReceiver);

      // Start cleanup routine for this guild
      this.startCleanupRoutine(guildId);

      logger.info(`[VoiceListenerService] Voice listening active for guild ${guildId}`);
      this.emit('listeningStarted', { guildId, channelId: channel.id });

    } catch (error) {
      logger.error(`[VoiceListenerService] Failed to start listening in guild ${guildId}:`, error);
      throw error;
    }
  }

  private setupUserAudioStreams(guildId: string, voiceReceiver: any): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    // Monitor for new users joining voice
    voiceReceiver.connection.on('stateChange', () => {
      // Refresh user streams when connection state changes
      setTimeout(() => this.refreshUserStreams(guildId), 1000);
    });

    // Initial setup of user streams
    this.refreshUserStreams(guildId);
  }

  private refreshUserStreams(guildId: string): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    const voiceReceiver = receiver.connection.receiver;
    
    // Get all users in the voice channel
    receiver.channel.members.forEach((member) => {
      if (member.user.bot) return; // Skip bots
      
      const userId = member.user.id;
      if (!receiver.activeUsers.has(userId)) {
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
        logger.debug(`[VoiceListenerService] Started listening to user ${member.user.tag} in guild ${guildId}`);
      }
    });
  }

  private setupAudioStreamHandlers(guildId: string, userId: string, audioStream: any): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    audioStream.on('data', (chunk: Buffer) => {
      this.handleAudioData(guildId, userId, chunk);
    });

    audioStream.on('end', () => {
      this.processAudioBuffer(guildId, userId);
    });

    audioStream.on('error', (error: Error) => {
      logger.error(`[VoiceListenerService] Audio stream error for user ${userId} in guild ${guildId}:`, error);
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
    if (!userBuffer) return;

    // Add chunk to buffer
    userBuffer.push(chunk);
    receiver.lastActivity.set(userId, Date.now());

    // Check buffer size limits
    const totalSize = userBuffer.reduce((sum, buf) => sum + buf.length, 0);
    if (totalSize > this.maxBufferSize) {
      logger.warn(`[VoiceListenerService] Buffer overflow for user ${userId}, processing early`);
      this.processAudioBuffer(guildId, userId);
    }
  }

  private processAudioBuffer(guildId: string, userId: string): void {
    const receiver = this.receivers.get(guildId);
    if (!receiver) return;

    const userBuffer = receiver.audioBuffer.get(userId);
    if (!userBuffer || userBuffer.length === 0) return;

    try {
      // Combine all audio chunks
      const combinedAudio = Buffer.concat(userBuffer);
      
      // Clear the buffer
      receiver.audioBuffer.set(userId, []);

      // Skip if audio is too short (likely noise)
      if (combinedAudio.length < 1600) { // ~33ms at 48kHz stereo 16-bit
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

      logger.debug(`[VoiceListenerService] Processed audio segment: ${audioSegment.duration.toFixed(2)}s from user ${userId}`);
      
      // Emit audio segment for processing
      this.emit('audioSegment', audioSegment);

    } catch (error) {
      logger.error(`[VoiceListenerService] Error processing audio buffer for user ${userId}:`, error);
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

      logger.info(`[VoiceListenerService] Voice listening stopped for guild ${guildId}`);
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
    return this.receivers.has(guildId);
  }

  getActiveGuilds(): string[] {
    return Array.from(this.receivers.keys());
  }

  getSessionCount(): number {
    return this.sessions.size;
  }
}