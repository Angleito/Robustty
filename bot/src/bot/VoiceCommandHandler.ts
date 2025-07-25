import { VoiceChannel, User } from 'discord.js';
import { EventEmitter } from 'events';
import { createAudioResource, StreamType } from '@discordjs/voice';
import { VoiceCommand, AudioSegment, WakeWordResult, SpeechRecognitionResult } from '../domain/types';
import { VoiceListenerService } from '../services/VoiceListenerService';
import { WakeWordDetectionService } from '../services/WakeWordDetectionService';
import { SpeechRecognitionService } from '../services/SpeechRecognitionService';
import { AudioProcessingService } from '../services/AudioProcessingService';
import { TextToSpeechService } from '../services/TextToSpeechService';
import { KanyeResponseGenerator } from '../services/KanyeResponseGenerator';
import { logger } from '../services/logger';

export class VoiceCommandHandler extends EventEmitter {
  private voiceListener: VoiceListenerService;
  private wakeWordDetector: WakeWordDetectionService;
  private speechRecognition: SpeechRecognitionService;
  private textToSpeech: TextToSpeechService;
  private responseGenerator: KanyeResponseGenerator;
  private processingQueues: Map<string, AudioSegment[]> = new Map();
  private activeProcessing: Map<string, boolean> = new Map();
  private voiceConnections: Map<string, any> = new Map(); // Store voice connections for TTS

  constructor() {
    super();
    
    this.voiceListener = new VoiceListenerService();
    this.wakeWordDetector = new WakeWordDetectionService(0.7); // 70% confidence threshold
    this.speechRecognition = new SpeechRecognitionService();
    this.textToSpeech = new TextToSpeechService();
    this.responseGenerator = new KanyeResponseGenerator();
    
    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    // Handle audio segments from voice listener
    this.voiceListener.on('audioSegment', (segment: AudioSegment) => {
      this.handleAudioSegment(segment);
    });

    // Handle voice listening events
    this.voiceListener.on('speakingStart', (data: { guildId: string; userId: string }) => {
      logger.debug(`[VoiceCommandHandler] User ${data.userId} started speaking in guild ${data.guildId}`);
    });

    this.voiceListener.on('speakingEnd', (data: { guildId: string; userId: string }) => {
      logger.debug(`[VoiceCommandHandler] User ${data.userId} stopped speaking in guild ${data.guildId}`);
    });
  }

  async startListening(voiceChannel: VoiceChannel, connection: any): Promise<void> {
    try {
      await this.voiceListener.startListening(connection, voiceChannel);
      this.voiceConnections.set(voiceChannel.guild.id, connection);
      logger.info(`[VoiceCommandHandler] Started voice command listening in ${voiceChannel.name}`);
      
      // Play greeting if TTS is enabled
      await this.playTTSResponse(voiceChannel.guild.id, this.responseGenerator.generateGreeting());
    } catch (error) {
      logger.error('[VoiceCommandHandler] Failed to start listening:', error);
      throw error;
    }
  }

  async stopListening(guildId: string): Promise<void> {
    try {
      await this.voiceListener.stopListening(guildId);
      this.processingQueues.delete(guildId);
      this.activeProcessing.delete(guildId);
      this.voiceConnections.delete(guildId);
      logger.info(`[VoiceCommandHandler] Stopped voice command listening for guild ${guildId}`);
    } catch (error) {
      logger.error('[VoiceCommandHandler] Failed to stop listening:', error);
    }
  }

  private async handleAudioSegment(segment: AudioSegment): Promise<void> {
    const queueKey = `${segment.guildId}_${segment.userId}`;
    
    // Add segment to processing queue
    if (!this.processingQueues.has(queueKey)) {
      this.processingQueues.set(queueKey, []);
    }
    
    this.processingQueues.get(queueKey)!.push(segment);
    
    // Process queue if not already processing
    if (!this.activeProcessing.get(queueKey)) {
      this.processAudioQueue(queueKey);
    }
  }

  private async processAudioQueue(queueKey: string): Promise<void> {
    this.activeProcessing.set(queueKey, true);
    
    try {
      const queue = this.processingQueues.get(queueKey);
      if (!queue || queue.length === 0) {
        return;
      }

      while (queue.length > 0) {
        const segment = queue.shift()!;
        await this.processAudioSegment(segment);
      }
    } catch (error) {
      logger.error('[VoiceCommandHandler] Error processing audio queue:', error);
    } finally {
      this.activeProcessing.set(queueKey, false);
    }
  }

  private async processAudioSegment(segment: AudioSegment): Promise<void> {
    try {
      // COST OPTIMIZATION: Only run expensive processing after wake word detection
      
      // Step 1: Quick, local wake word detection (no API cost)
      const wakeWordResult = await this.detectWakeWord(segment);
      
      if (!wakeWordResult.detected) {
        // No wake word detected - stop here to save compute costs
        logger.debug(`[VoiceCommandHandler] No wake word detected for user ${segment.userId}, skipping expensive processing`);
        return;
      }

      logger.info(`[VoiceCommandHandler] 🎙️ Wake word "Kanye" detected! Starting full processing for user ${segment.userId} (confidence: ${wakeWordResult.confidence})`);
      
      // Update segment with wake word detection
      segment.isWakeWordDetected = true;
      segment.wakeWordConfidence = wakeWordResult.confidence;

      // Step 2: Now that wake word is confirmed, listen for the actual command
      // We need to capture additional audio after "Kanye" for the actual command
      await this.captureCommandAudio(segment);

    } catch (error) {
      logger.error('[VoiceCommandHandler] Error processing audio segment:', error);
    }
  }

  private async captureCommandAudio(wakeWordSegment: AudioSegment): Promise<void> {
    const queueKey = `${wakeWordSegment.guildId}_${wakeWordSegment.userId}`;
    
    // Set up a temporary listener for the command that follows "Kanye"
    logger.info(`[VoiceCommandHandler] 👂 Listening for command after wake word...`);
    
    // Create a temporary command capture session
    const commandCaptureTimeout = setTimeout(() => {
      logger.warn(`[VoiceCommandHandler] Command capture timeout for user ${wakeWordSegment.userId}`);
    }, 5000); // 5 second timeout for command

    // Store the session for command capture
    const sessionKey = `command_capture_${wakeWordSegment.guildId}_${wakeWordSegment.userId}`;
    
    // Set up temporary event listener for the next audio segments
    const commandAudioBuffer: Buffer[] = [];
    let commandStartTime = Date.now();
    
    const onNextAudio = async (nextSegment: AudioSegment) => {
      if (nextSegment.userId === wakeWordSegment.userId && 
          nextSegment.guildId === wakeWordSegment.guildId &&
          Date.now() - commandStartTime < 5000) { // Within 5 seconds
        
        commandAudioBuffer.push(nextSegment.audioData);
        
        // Check if we have enough audio for command processing (e.g., 2-3 seconds)
        const totalDuration = commandAudioBuffer.reduce((sum, buffer) => 
          sum + (buffer.length / (48000 * 2 * 2)), 0);
        
        if (totalDuration >= 1.5) { // At least 1.5 seconds of command audio
          clearTimeout(commandCaptureTimeout);
          this.voiceListener.removeListener('audioSegment', onNextAudio);
          
          // Combine all command audio
          const combinedCommandAudio = Buffer.concat(commandAudioBuffer);
          
          // Create command segment
          const commandSegment: AudioSegment = {
            ...wakeWordSegment,
            id: `command_${wakeWordSegment.id}`,
            audioData: combinedCommandAudio,
            duration: totalDuration,
            timestamp: Date.now()
          };
          
          // NOW process with expensive OpenAI API
          await this.processCommandWithWhisper(commandSegment);
        }
      }
    };

    // Listen for the next audio segments
    this.voiceListener.on('audioSegment', onNextAudio);
    
    // Cleanup after timeout
    setTimeout(() => {
      this.voiceListener.removeListener('audioSegment', onNextAudio);
    }, 6000);
  }

  private async processCommandWithWhisper(segment: AudioSegment): Promise<void> {
    try {
      logger.info(`[VoiceCommandHandler] 💰 Processing command with OpenAI Whisper (this costs money!)`);
      
      // Step 2: Process speech recognition with Whisper API
      const recognitionResult = await this.processSpeechRecognition(segment);
      
      if (!recognitionResult.text || recognitionResult.confidence < 0.5) {
        logger.warn(`[VoiceCommandHandler] Low confidence speech recognition: "${recognitionResult.text}" (${recognitionResult.confidence})`);
        return;
      }

      // Step 3: Parse voice command
      const voiceCommand = await this.parseVoiceCommand(segment, recognitionResult);
      
      if (voiceCommand) {
        logger.info(`[VoiceCommandHandler] ✅ Voice command parsed: ${voiceCommand.command} with parameters: [${voiceCommand.parameters.join(', ')}]`);
        
        // Play TTS acknowledgment based on command
        const ttsContext = {
          command: voiceCommand.command,
          songTitle: voiceCommand.parameters.join(' ') || undefined
        };
        
        // For play commands, just acknowledge we're searching
        if (voiceCommand.command === 'play') {
          await this.playTTSResponse(segment.guildId, this.responseGenerator.generateResponse({ 
            command: 'play', 
            songTitle: undefined // Indicate we're searching
          }));
        } else {
          // For other commands, give immediate feedback
          await this.playTTSResponse(segment.guildId, this.responseGenerator.generateResponse(ttsContext));
        }
        
        // Emit voice command for handling by MusicBot
        this.emit('voiceCommand', voiceCommand);
      } else {
        logger.warn(`[VoiceCommandHandler] Could not parse valid command from: "${recognitionResult.text}"`);
        
        // Play "unknown command" response
        await this.playTTSResponse(segment.guildId, this.responseGenerator.generateResponse({ command: 'unknown' }));
      }

    } catch (error) {
      logger.error('[VoiceCommandHandler] Error processing command with Whisper:', error);
    }
  }

  private async detectWakeWord(segment: AudioSegment): Promise<WakeWordResult> {
    try {
      // Convert audio to appropriate format for wake word detection
      const processedAudio = AudioProcessingService.normalizeAudioLevel(segment.audioData, 0.8);
      
      // Detect "Kanye" wake word
      const result = await this.wakeWordDetector.detectWakeWord(processedAudio, 'kanye');
      
      return result;
    } catch (error) {
      logger.error('[VoiceCommandHandler] Wake word detection failed:', error);
      return {
        detected: false,
        confidence: 0,
        keyword: 'kanye',
        startTime: 0,
        endTime: 0
      };
    }
  }

  private async processSpeechRecognition(segment: AudioSegment): Promise<SpeechRecognitionResult> {
    try {
      // Convert PCM audio to WAV format for Whisper API
      const wavAudio = AudioProcessingService.pcmToWav(
        segment.audioData,
        segment.sampleRate,
        segment.channels,
        16
      );

      // Transcribe using OpenAI Whisper
      const result = await this.speechRecognition.transcribeAudio(wavAudio, 'en');
      
      return result;
    } catch (error) {
      logger.error('[VoiceCommandHandler] Speech recognition failed:', error);
      return {
        text: '',
        confidence: 0,
        isPartial: false,
        language: 'en',
        processingTimeMs: 0,
        alternatives: []
      };
    }
  }

  private async parseVoiceCommand(
    segment: AudioSegment,
    recognitionResult: SpeechRecognitionResult
  ): Promise<VoiceCommand | null> {
    try {
      const { command, parameters } = this.speechRecognition.parseVoiceCommand(recognitionResult.text);
      
      if (!command) {
        return null;
      }

      const voiceCommand: VoiceCommand = {
        id: `voice_${segment.id}`,
        userId: segment.userId,
        guildId: segment.guildId,
        command,
        parameters,
        confidence: recognitionResult.confidence,
        timestamp: segment.timestamp,
        processingTimeMs: recognitionResult.processingTimeMs
      };

      return voiceCommand;
    } catch (error) {
      logger.error('[VoiceCommandHandler] Failed to parse voice command:', error);
      return null;
    }
  }

  // Public methods for external control
  isListening(guildId: string): boolean {
    return this.voiceListener.isListening(guildId);
  }

  getActiveGuilds(): string[] {
    return this.voiceListener.getActiveGuilds();
  }

  updateWakeWordThreshold(threshold: number): void {
    this.wakeWordDetector.updateConfidenceThreshold(threshold);
    logger.info(`[VoiceCommandHandler] Updated wake word threshold to ${threshold}`);
  }

  getSupportedCommands(): string[] {
    return ['play', 'skip', 'stop', 'pause', 'resume', 'queue'];
  }

  getProcessingStats(): {
    activeGuilds: number;
    queuedSegments: number;
    activeProcessing: number;
    sessionCount: number;
  } {
    const queuedSegments = Array.from(this.processingQueues.values())
      .reduce((total, queue) => total + queue.length, 0);
    
    const activeProcessingCount = Array.from(this.activeProcessing.values())
      .filter(active => active).length;

    return {
      activeGuilds: this.voiceListener.getActiveGuilds().length,
      queuedSegments,
      activeProcessing: activeProcessingCount,
      sessionCount: this.voiceListener.getSessionCount()
    };
  }

  // Create voice session for a user
  createVoiceSession(guildId: string, userId: string, channelId: string): string {
    return this.voiceListener.createVoiceSession(guildId, userId, channelId);
  }

  // Get active voice session for a user
  getActiveSession(guildId: string, userId: string) {
    return this.voiceListener.getActiveSession(guildId, userId);
  }

  // Cost tracking methods
  getCostStats() {
    return this.speechRecognition.getCostStats();
  }

  logCostSummary(): void {
    this.speechRecognition.logCostSummary();
  }

  resetCostTracking(): void {
    this.speechRecognition.resetCostTracking();
  }

  getWakeWordStats() {
    return this.wakeWordDetector.getProcessingStats();
  }

  // Health check method
  async healthCheck(): Promise<{
    status: 'healthy' | 'degraded' | 'unhealthy';
    services: {
      voiceListener: boolean;
      wakeWordDetection: boolean;
      speechRecognition: boolean;
    };
    stats: any;
    costOptimization: {
      wakeWordFirst: boolean;
      costTracking: any;
      wakeWordStats: any;
    };
  }> {
    const services = {
      voiceListener: this.voiceListener !== null,
      wakeWordDetection: this.wakeWordDetector !== null,
      speechRecognition: this.speechRecognition.isServiceEnabled()
    };

    const stats = this.getProcessingStats();
    const costStats = this.getCostStats();
    const wakeWordStats = this.getWakeWordStats();
    
    const healthyServices = Object.values(services).filter(Boolean).length;
    const totalServices = Object.values(services).length;
    
    let status: 'healthy' | 'degraded' | 'unhealthy';
    if (healthyServices === totalServices) {
      status = 'healthy';
    } else if (healthyServices > 0) {
      status = 'degraded';
    } else {
      status = 'unhealthy';
    }

    return {
      status,
      services,
      stats,
      costOptimization: {
        wakeWordFirst: true, // Always true in our optimized implementation
        costTracking: costStats,
        wakeWordStats
      }
    };
  }

  // TTS Response Method
  private async playTTSResponse(guildId: string, text: string): Promise<void> {
    if (!this.textToSpeech.isEnabled()) {
      logger.debug('[VoiceCommandHandler] TTS disabled, skipping response');
      return;
    }

    const connection = this.voiceConnections.get(guildId);
    if (!connection) {
      logger.warn(`[VoiceCommandHandler] No voice connection for guild ${guildId}, cannot play TTS`);
      return;
    }

    try {
      const audioStream = await this.textToSpeech.generateSpeech(text);
      if (!audioStream) {
        logger.warn('[VoiceCommandHandler] Failed to generate TTS audio');
        return;
      }

      const resource = createAudioResource(audioStream, {
        inputType: StreamType.Arbitrary,
        inlineVolume: true
      });

      // Get the audio player from the connection
      const player = connection.state.subscription?.player;
      if (player) {
        // Store current state
        const wasPlaying = player.state.status === 'playing';
        
        // Play TTS
        player.play(resource);
        
        // Wait for TTS to finish
        await new Promise((resolve) => {
          const onIdle = () => {
            player.off('idle', onIdle);
            resolve(undefined);
          };
          player.on('idle', onIdle);
        });

        logger.info(`[VoiceCommandHandler] TTS response played: "${text}"`);
      }
    } catch (error) {
      logger.error('[VoiceCommandHandler] Error playing TTS response:', error);
    }
  }

  // Public method to trigger TTS responses from outside
  async speakResponse(guildId: string, context: any): Promise<void> {
    const response = this.responseGenerator.generateResponse(context);
    await this.playTTSResponse(guildId, response);
  }
}