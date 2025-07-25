import { MusicBot } from '../../bot/MusicBot';
import { AutomaticFoodTalkService } from '../../services/AutomaticFoodTalkService';
import { VoiceCommandHandler } from '../../bot/VoiceCommandHandler';
import { TextToSpeechService } from '../../services/TextToSpeechService';
import { mockVoiceConnection } from '../setup';

// Mock all external dependencies
jest.mock('../../services/TextToSpeechService');
jest.mock('../../services/VoiceListenerService');
jest.mock('../../services/WakeWordDetectionService');
jest.mock('../../services/SpeechRecognitionService');
jest.mock('../../services/AudioProcessingService');
jest.mock('../../bot/VoiceManager');
jest.mock('../../services/YouTubeService');
jest.mock('../../services/RedisClient');
jest.mock('../../services/PlaybackStrategyManager');
jest.mock('../../domain/QueueManager');
jest.mock('../../services/ErrorHandler');
jest.mock('../../services/MonitoringService');
jest.mock('../../services/SearchResultHandler');

describe('Automatic Food Talk Integration Tests', () => {
  let musicBot: MusicBot;
  let automaticFoodTalkService: AutomaticFoodTalkService;
  let mockTTSService: jest.Mocked<TextToSpeechService>;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Set up environment for full integration
    process.env.TTS_ENABLED = 'true';
    process.env.OPENAI_API_KEY = 'test-openai-key';
    process.env.ELEVENLABS_API_KEY = 'test-elevenlabs-key';
    process.env.ELEVENLABS_VOICE_ID = 'test-voice-id';
    
    // Mock TTS service
    mockTTSService = new TextToSpeechService() as jest.Mocked<TextToSpeechService>;
    mockTTSService.isEnabled.mockReturnValue(true);
    mockTTSService.generateSpeech.mockResolvedValue({
      pipe: jest.fn(),
      on: jest.fn(),
      destroy: jest.fn()
    } as any);
    
    // Initialize services
    automaticFoodTalkService = new AutomaticFoodTalkService({
      enabled: true,
      idlePeriodMinutes: 1,
      minIntervalMinutes: 1,
      maxIntervalMinutes: 2,
      requiresTTS: true,
      requiresVoiceChannel: true
    });
    
    musicBot = new MusicBot();
    
    // Mock voice command handler with TTS integration
    const mockVoiceCommandHandler = {
      speakResponse: jest.fn().mockResolvedValue(undefined),
      startListening: jest.fn().mockResolvedValue(undefined),
      stopListening: jest.fn().mockResolvedValue(undefined),
      isListening: jest.fn().mockReturnValue(false)
    };
    (musicBot as any).voiceCommandHandler = mockVoiceCommandHandler;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('End-to-End Food Talk Flow', () => {
    it('should complete full automatic food talk cycle with TTS', async () => {
      const guildId = 'integration-guild-1';
      const foodTalkEvents: any[] = [];
      
      // Set up event monitoring
      automaticFoodTalkService.on('foodTalk', (event) => {
        foodTalkEvents.push(event);
      });
      
      // Start tracking with TTS and voice channel enabled
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
      
      // Fast forward past idle period to trigger food talk
      jest.advanceTimersByTime(3 * 60 * 1000); // 3 minutes
      
      // Verify food talk was triggered
      expect(foodTalkEvents).toHaveLength(1);
      expect(foodTalkEvents[0].guildId).toBe(guildId);
      expect(foodTalkEvents[0].message).toBeTruthy();
      
      // Simulate TTS response to the food talk
      const mockVoiceCommandHandler = (musicBot as any).voiceCommandHandler;
      await mockVoiceCommandHandler.speakResponse(guildId, { 
        command: 'food',
        message: foodTalkEvents[0].message 
      });
      
      expect(mockVoiceCommandHandler.speakResponse).toHaveBeenCalledWith(
        guildId,
        expect.objectContaining({ command: 'food' })
      );
    });

    it('should handle multiple guilds with different configurations', async () => {
      const guild1 = 'guild-tts-enabled';
      const guild2 = 'guild-tts-disabled';
      const guild3 = 'guild-no-voice';
      
      const foodTalkEvents: any[] = [];
      automaticFoodTalkService.on('foodTalk', (event) => {
        foodTalkEvents.push(event);
      });
      
      // Guild 1: TTS enabled, in voice channel
      automaticFoodTalkService.startGuildTracking(guild1, true, true);
      
      // Guild 2: TTS disabled, in voice channel
      automaticFoodTalkService.startGuildTracking(guild2, false, true);
      
      // Guild 3: TTS enabled, not in voice channel
      automaticFoodTalkService.startGuildTracking(guild3, true, false);
      
      // Only guild1 should be active
      expect(automaticFoodTalkService.isGuildActive(guild1)).toBe(true);
      expect(automaticFoodTalkService.isGuildActive(guild2)).toBe(false);
      expect(automaticFoodTalkService.isGuildActive(guild3)).toBe(false);
      
      // Trigger food talk
      jest.advanceTimersByTime(3 * 60 * 1000);
      
      // Only guild1 should have food talk events
      const guild1Events = foodTalkEvents.filter(e => e.guildId === guild1);
      expect(guild1Events).toHaveLength(1);
      
      const guild2Events = foodTalkEvents.filter(e => e.guildId === guild2);
      const guild3Events = foodTalkEvents.filter(e => e.guildId === guild3);
      expect(guild2Events).toHaveLength(0);
      expect(guild3Events).toHaveLength(0);
    });

    it('should respect minimum intervals between food talks', async () => {
      const guildId = 'interval-test-guild';
      const foodTalkEvents: any[] = [];
      
      automaticFoodTalkService.on('foodTalk', (event) => {
        foodTalkEvents.push(event);
      });
      
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      // Force first food talk
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      expect(foodTalkEvents).toHaveLength(1);
      
      // Try to force another immediately - should be blocked by minimum interval
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      expect(foodTalkEvents).toHaveLength(1);
      
      // Advance past minimum interval
      jest.advanceTimersByTime(60 * 1000); // 1 minute
      
      // Now should allow another food talk
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      expect(foodTalkEvents).toHaveLength(2);
    });
  });

  describe('Activity-Based Food Talk Triggering', () => {
    it('should reschedule food talk when activity occurs', async () => {
      const guildId = 'activity-guild';
      const foodTalkEvents: any[] = [];
      
      automaticFoodTalkService.on('foodTalk', (event) => {
        foodTalkEvents.push(event);
      });
      
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      // Advance halfway to trigger time
      jest.advanceTimersByTime(90 * 1000); // 1.5 minutes
      expect(foodTalkEvents).toHaveLength(0);
      
      // Update activity - should reschedule
      automaticFoodTalkService.updateActivity(guildId);
      
      // Advance to original trigger time - should not trigger
      jest.advanceTimersByTime(90 * 1000); // Another 1.5 minutes
      expect(foodTalkEvents).toHaveLength(0);
      
      // Advance full cycle from activity update
      jest.advanceTimersByTime(60 * 1000); // 1 more minute
      expect(foodTalkEvents).toHaveLength(1);
    });

    it('should track different types of user activity', async () => {
      const guildId = 'multi-activity-guild';
      
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      // Simulate various activities
      const activities = [
        () => automaticFoodTalkService.updateActivity(guildId), // Voice activity
        () => automaticFoodTalkService.updateActivity(guildId), // Music command
        () => automaticFoodTalkService.updateActivity(guildId), // Chat message
      ];
      
      activities.forEach((activity, index) => {
        activity();
        
        // Each activity should reset the timer
        const lastActivity = (automaticFoodTalkService as any).lastActivity.get(guildId);
        expect(lastActivity).toBeGreaterThan(0);
      });
    });
  });

  describe('TTS and Voice Integration', () => {
    it('should integrate with voice command handler for TTS output', async () => {
      const guildId = 'tts-integration-guild';
      
      // Set up voice connection
      const mockVoiceCommandHandler = (musicBot as any).voiceCommandHandler;
      
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      automaticFoodTalkService.on('foodTalk', async (event) => {
        // Simulate sending food talk to TTS
        await mockVoiceCommandHandler.speakResponse(event.guildId, {
          command: 'food',
          message: event.message
        });
      });
      
      // Trigger food talk
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      
      // Wait for async operations
      await new Promise(resolve => setTimeout(resolve, 0));
      
      expect(mockVoiceCommandHandler.speakResponse).toHaveBeenCalledWith(
        guildId,
        expect.objectContaining({
          command: 'food',
          message: expect.any(String)
        })
      );
    });

    it('should handle TTS failures gracefully', async () => {
      const guildId = 'tts-failure-guild';
      
      const mockVoiceCommandHandler = (musicBot as any).voiceCommandHandler;
      mockVoiceCommandHandler.speakResponse.mockRejectedValue(new Error('TTS failed'));
      
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      automaticFoodTalkService.on('foodTalk', async (event) => {
        try {
          await mockVoiceCommandHandler.speakResponse(event.guildId, {
            command: 'food',
            message: event.message
          });
        } catch (error) {
          // Should handle TTS errors gracefully
          expect(error.message).toBe('TTS failed');
        }
      });
      
      expect(() => {
        automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      }).not.toThrow();
    });
  });

  describe('Configuration Management', () => {
    it('should dynamically update configuration and affect active guilds', () => {
      const guild1 = 'config-guild-1';
      const guild2 = 'config-guild-2';
      
      // Start with default config
      automaticFoodTalkService.startGuildTracking(guild1, true, true);
      automaticFoodTalkService.startGuildTracking(guild2, false, true);
      
      expect(automaticFoodTalkService.isGuildActive(guild1)).toBe(true);
      expect(automaticFoodTalkService.isGuildActive(guild2)).toBe(false); // TTS required but disabled
      
      // Change config to not require TTS
      automaticFoodTalkService.updateConfig({ requiresTTS: false });
      
      // Existing guild1 should be stopped due to config change
      expect(automaticFoodTalkService.isGuildActive(guild1)).toBe(false);
      
      // Now guild2 should be able to start
      automaticFoodTalkService.startGuildTracking(guild2, false, true);
      expect(automaticFoodTalkService.isGuildActive(guild2)).toBe(true);
    });

    it('should validate configuration values', () => {
      const config = automaticFoodTalkService.getConfig();
      
      expect(config.enabled).toBe(true);
      expect(config.idlePeriodMinutes).toBeGreaterThan(0);
      expect(config.minIntervalMinutes).toBeGreaterThan(0);
      expect(config.maxIntervalMinutes).toBeGreaterThanOrEqual(config.minIntervalMinutes);
    });
  });

  describe('Statistics and Monitoring', () => {
    it('should track comprehensive statistics across multiple food talks', () => {
      const guildId = 'stats-guild';
      
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      // Trigger multiple food talks with delays
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      jest.advanceTimersByTime(60 * 1000); // Wait minimum interval
      
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      jest.advanceTimersByTime(60 * 1000);
      
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      
      const stats = automaticFoodTalkService.getGuildStats(guildId);
      expect(stats!.totalMessages).toBe(3);
      expect(stats!.lastFoodTalk).toBeGreaterThan(0);
      expect(Object.keys(stats!.foodTalksByType)).toContain('watermelon');
    });

    it('should provide aggregated statistics across all guilds', () => {
      const guilds = ['stats-1', 'stats-2', 'stats-3'];
      
      guilds.forEach(guildId => {
        automaticFoodTalkService.startGuildTracking(guildId, true, true);
        automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      });
      
      const allStats = automaticFoodTalkService.getAllStats();
      expect(allStats.size).toBe(3);
      
      guilds.forEach(guildId => {
        expect(allStats.has(guildId)).toBe(true);
        expect(allStats.get(guildId)!.totalMessages).toBe(1);
      });
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should handle service disable/enable cycles', () => {
      const guildId = 'enable-disable-guild';
      
      // Start with service enabled
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
      
      // Disable service
      automaticFoodTalkService.updateConfig({ enabled: false });
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(false);
      
      // Re-enable service
      automaticFoodTalkService.updateConfig({ enabled: true });
      
      // Need to restart tracking
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
    });

    it('should handle memory cleanup when guilds are removed', () => {
      const guildIds = Array.from({ length: 10 }, (_, i) => `cleanup-guild-${i}`);
      
      // Start tracking all guilds
      guildIds.forEach(guildId => {
        automaticFoodTalkService.startGuildTracking(guildId, true, true);
      });
      
      expect(automaticFoodTalkService.getActiveGuilds()).toHaveLength(10);
      
      // Stop tracking half of them
      guildIds.slice(0, 5).forEach(guildId => {
        automaticFoodTalkService.stopGuildTracking(guildId);
      });
      
      expect(automaticFoodTalkService.getActiveGuilds()).toHaveLength(5);
      
      // Verify only the remaining guilds are active
      guildIds.slice(5).forEach(guildId => {
        expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
      });
    });

    it('should handle concurrent operations safely', () => {
      const guildId = 'concurrent-guild';
      
      // Perform multiple operations concurrently
      const operations = Array.from({ length: 100 }, (_, i) => {
        if (i % 4 === 0) return () => automaticFoodTalkService.startGuildTracking(guildId, true, true);
        if (i % 4 === 1) return () => automaticFoodTalkService.updateActivity(guildId);
        if (i % 4 === 2) return () => automaticFoodTalkService.forceTriggerfoodTalk(guildId);
        return () => automaticFoodTalkService.stopGuildTracking(guildId);
      });
      
      expect(() => {
        operations.forEach(op => op());
      }).not.toThrow();
    });
  });
});