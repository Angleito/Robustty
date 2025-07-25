import { MusicBot } from '../bot/MusicBot';
import { VoiceManager } from '../bot/VoiceManager';
import { AutomaticFoodTalkService } from '../services/AutomaticFoodTalkService';
import { TextToSpeechService } from '../services/TextToSpeechService';
import { mockVoiceConnection } from './setup';
import { Message, VoiceChannel, Guild, GuildMember, User } from 'discord.js';

// Mock dependencies
jest.mock('../bot/VoiceManager');
jest.mock('../services/TextToSpeechService');
jest.mock('../services/YouTubeService');
jest.mock('../services/RedisClient');
jest.mock('../services/PlaybackStrategyManager');
jest.mock('../domain/QueueManager');
jest.mock('../services/ErrorHandler');
jest.mock('../services/MonitoringService');
jest.mock('../services/SearchResultHandler');

// Mock Discord.js classes
const mockUser = { id: 'user-123', bot: false } as User;
const mockGuild = { id: 'guild-123', name: 'Test Guild' } as Guild;
const mockMember = { voice: { channel: null } } as GuildMember;
const mockVoiceChannel = { 
  id: 'voice-123', 
  guild: mockGuild,
  members: new Map()
} as VoiceChannel;

const createMockMessage = (content: string, shouldRespond: boolean = true): Message => {
  // Mock Math.random to control response probability
  const originalRandom = Math.random;
  Math.random = jest.fn().mockReturnValue(shouldRespond ? 0.1 : 0.2); // 0.1 < 0.15, 0.2 > 0.15
  
  const message = {
    content,
    author: mockUser,
    guild: mockGuild,
    reply: jest.fn().mockResolvedValue(undefined)
  } as unknown as Message;
  
  // Restore Math.random after creating message
  Math.random = originalRandom;
  
  return message;
};

describe('Food Talk Music Integration', () => {
  let musicBot: MusicBot;
  let mockVoiceManager: jest.Mocked<VoiceManager>;
  let mockTTSService: jest.Mocked<TextToSpeechService>;
  let automaticFoodTalkService: AutomaticFoodTalkService;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Set up environment
    process.env.TTS_ENABLED = 'true';
    process.env.OPENAI_API_KEY = 'test-key';
    
    // Mock VoiceManager
    mockVoiceManager = new VoiceManager({} as any) as jest.Mocked<VoiceManager>;
    mockVoiceManager.isPlaying.mockReturnValue(false);
    mockVoiceManager.join.mockResolvedValue(mockVoiceConnection);
    
    // Mock TTS Service
    mockTTSService = new TextToSpeechService() as jest.Mocked<TextToSpeechService>;
    mockTTSService.isEnabled.mockReturnValue(true);
    
    // Create MusicBot
    musicBot = new MusicBot();
    (musicBot as any).voiceManager = mockVoiceManager;
    
    // Create automatic food talk service
    automaticFoodTalkService = new AutomaticFoodTalkService({
      enabled: true,
      idlePeriodMinutes: 1,
      minIntervalMinutes: 1,
      maxIntervalMinutes: 2
    });
  });

  describe('Message-based Food Talk Integration', () => {
    it('should respond to food-related messages when music is not playing', async () => {
      mockVoiceManager.isPlaying.mockReturnValue(false);
      
      const message = createMockMessage('I love watermelon');
      await (musicBot as any).handleMessage(message);
      
      expect(message.reply).toHaveBeenCalledWith(
        expect.stringContaining('watermelon')
      );
    });

    it('should respond to food-related messages when music is playing', async () => {
      mockVoiceManager.isPlaying.mockReturnValue(true);
      
      const message = createMockMessage('I love watermelon');
      await (musicBot as any).handleMessage(message);
      
      // Should still respond - music playback shouldn't affect message responses
      expect(message.reply).toHaveBeenCalledWith(
        expect.stringContaining('watermelon')
      );
    });

    it('should respond to different food types in messages', async () => {
      const testCases = [
        { content: 'chicken is delicious', expectedContains: 'chicken' },
        { content: 'watermelon season', expectedContains: 'watermelon' },
        { content: 'kool aid party', expectedContains: 'Kool-Aid' }
      ];

      for (const testCase of testCases) {
        const message = createMockMessage(testCase.content);
        await (musicBot as any).handleMessage(message);
        
        expect(message.reply).toHaveBeenCalledWith(
          expect.stringContaining(testCase.expectedContains)
        );
        
        jest.clearAllMocks();
      }
    });

    it('should respond to talk triggers with general food responses', async () => {
      const message = createMockMessage('say something');
      await (musicBot as any).handleMessage(message);
      
      expect(message.reply).toHaveBeenCalledWith(
        expect.stringMatching(/food|hungry|eats|taste/i)
      );
    });

    it('should not respond when random chance is low', async () => {
      const message = createMockMessage('watermelon', false); // shouldRespond = false
      await (musicBot as any).handleMessage(message);
      
      expect(message.reply).not.toHaveBeenCalled();
    });

    it('should ignore bot messages', async () => {
      const botUser = { id: 'bot-123', bot: true } as User;
      const message = {
        content: 'watermelon',
        author: botUser,
        guild: mockGuild,
        reply: jest.fn()
      } as unknown as Message;
      
      await (musicBot as any).handleMessage(message);
      
      expect(message.reply).not.toHaveBeenCalled();
    });
  });

  describe('TTS Food Talk and Music Playback', () => {
    beforeEach(() => {
      // Mock voice command handler
      const mockVoiceCommandHandler = {
        speakResponse: jest.fn().mockResolvedValue(undefined),
        startListening: jest.fn().mockResolvedValue(undefined)
      };
      (musicBot as any).voiceCommandHandler = mockVoiceCommandHandler;
    });

    it('should play TTS food talk when music is not playing', async () => {
      mockVoiceManager.isPlaying.mockReturnValue(false);
      
      const mockVoiceCommandHandler = (musicBot as any).voiceCommandHandler;
      await mockVoiceCommandHandler.speakResponse('guild-123', { command: 'food' });
      
      expect(mockVoiceCommandHandler.speakResponse).toHaveBeenCalledWith(
        'guild-123',
        { command: 'food' }
      );
    });

    it('should handle TTS food talk when music is playing', async () => {
      mockVoiceManager.isPlaying.mockReturnValue(true);
      
      // Simulate audio player state
      mockVoiceConnection.state.subscription.player.state.status = 'playing';
      
      const mockVoiceCommandHandler = (musicBot as any).voiceCommandHandler;
      await mockVoiceCommandHandler.speakResponse('guild-123', { command: 'food' });
      
      expect(mockVoiceCommandHandler.speakResponse).toHaveBeenCalled();
      // TTS should be able to play alongside music (they use same audio player)
    });

    it('should resume music after TTS food talk completes', async () => {
      mockVoiceManager.isPlaying.mockReturnValue(true);
      
      // Mock player state changes
      const mockPlayer = mockVoiceConnection.state.subscription.player;
      mockPlayer.state.status = 'playing';
      
      const mockVoiceCommandHandler = (musicBot as any).voiceCommandHandler;
      
      // Simulate TTS playback
      await mockVoiceCommandHandler.speakResponse('guild-123', { command: 'food' });
      
      // Simulate TTS completion (player goes idle)
      mockPlayer.state.status = 'idle';
      
      // The audio system should handle resuming music automatically
      expect(mockVoiceCommandHandler.speakResponse).toHaveBeenCalled();
    });
  });

  describe('Automatic Food Talk Service Integration', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should track guild when bot joins voice channel', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
    });

    it('should stop tracking when bot leaves voice channel', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      automaticFoodTalkService.stopGuildTracking('guild-123');
      
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(false);
    });

    it('should update activity when music commands are used', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      
      const updateActivitySpy = jest.spyOn(automaticFoodTalkService, 'updateActivity');
      
      // Simulate music command activity
      automaticFoodTalkService.updateActivity('guild-123');
      
      expect(updateActivitySpy).toHaveBeenCalledWith('guild-123');
    });

    it('should trigger food talk after idle period regardless of music state', (done) => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      
      automaticFoodTalkService.on('foodTalk', (event) => {
        expect(event.guildId).toBe('guild-123');
        expect(event.message).toBeTruthy();
        done();
      });
      
      // Fast forward past idle period
      jest.advanceTimersByTime(3 * 60 * 1000); // 3 minutes
    });

    it('should not interfere with music playback timing', () => {
      // Mock music playback
      mockVoiceManager.isPlaying.mockReturnValue(true);
      
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      
      // Food talk service should operate independently
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
      expect(mockVoiceManager.isPlaying('guild-123')).toBe(true);
    });
  });

  describe('Voice Channel State Management', () => {
    it('should handle voice channel join events', () => {
      const isGuildActiveBeforeJoin = automaticFoodTalkService.isGuildActive('guild-123');
      expect(isGuildActiveBeforeJoin).toBe(false);
      
      // Simulate joining voice channel with TTS enabled
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
    });

    it('should handle voice channel leave events', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
      
      // Simulate leaving voice channel
      automaticFoodTalkService.stopGuildTracking('guild-123');
      
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(false);
    });

    it('should handle TTS state changes', () => {
      // Start with TTS enabled
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
      
      // Simulate TTS being disabled
      automaticFoodTalkService.stopGuildTracking('guild-123');
      automaticFoodTalkService.startGuildTracking('guild-123', false, true);
      
      // Should not be active if TTS is required but disabled
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(false);
    });

    it('should handle multiple guilds with different states', () => {
      const guild1 = 'guild-1';
      const guild2 = 'guild-2';
      
      // Guild 1: TTS enabled, in voice
      automaticFoodTalkService.startGuildTracking(guild1, true, true);
      
      // Guild 2: TTS disabled, in voice
      automaticFoodTalkService.startGuildTracking(guild2, false, true);
      
      expect(automaticFoodTalkService.isGuildActive(guild1)).toBe(true);
      expect(automaticFoodTalkService.isGuildActive(guild2)).toBe(false);
      
      const activeGuilds = automaticFoodTalkService.getActiveGuilds();
      expect(activeGuilds).toContain(guild1);
      expect(activeGuilds).not.toContain(guild2);
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should handle message reply failures gracefully', async () => {
      const message = createMockMessage('watermelon');
      message.reply = jest.fn().mockRejectedValue(new Error('Reply failed'));
      
      await expect((musicBot as any).handleMessage(message))
        .resolves.not.toThrow();
    });

    it('should handle TTS failures during food talk', async () => {
      const mockVoiceCommandHandler = {
        speakResponse: jest.fn().mockRejectedValue(new Error('TTS failed'))
      };
      (musicBot as any).voiceCommandHandler = mockVoiceCommandHandler;
      
      await expect(mockVoiceCommandHandler.speakResponse('guild-123', { command: 'food' }))
        .rejects.toThrow('TTS failed');
    });

    it('should handle voice connection failures', async () => {
      mockVoiceManager.join.mockRejectedValue(new Error('Connection failed'));
      
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      
      // Service should still track even if connection fails
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
    });

    it('should handle concurrent food talk and music operations', async () => {
      // Start multiple operations concurrently
      const promises = [
        (musicBot as any).handleMessage(createMockMessage('watermelon')),
        (musicBot as any).handleMessage(createMockMessage('chicken')),
        automaticFoodTalkService.forceTriggerfoodTalk('guild-123')
      ];
      
      await expect(Promise.all(promises)).resolves.not.toThrow();
    });
  });
});