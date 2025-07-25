import { VoiceCommandHandler } from '../bot/VoiceCommandHandler';
import { TextToSpeechService } from '../services/TextToSpeechService';
import { KanyeResponseGenerator } from '../services/KanyeResponseGenerator';
import { AutomaticFoodTalkService } from '../services/AutomaticFoodTalkService';
import { mockVoiceConnection, mockAudioStream } from './setup';
import { VoiceChannel } from 'discord.js';

// Mock dependencies
jest.mock('../services/TextToSpeechService');
jest.mock('../services/KanyeResponseGenerator');
jest.mock('../services/VoiceListenerService');
jest.mock('../services/WakeWordDetectionService');
jest.mock('../services/SpeechRecognitionService');
jest.mock('../services/AudioProcessingService');

// Mock Discord.js voice channel
const mockVoiceChannel = {
  id: 'voice-channel-123',
  name: 'Test Voice Channel',
  guild: { id: 'guild-123' },
  members: new Map()
} as unknown as VoiceChannel;

describe('Food Talk TTS Integration', () => {
  let voiceCommandHandler: VoiceCommandHandler;
  let mockTTSService: jest.Mocked<TextToSpeechService>;
  let mockResponseGenerator: jest.Mocked<KanyeResponseGenerator>;
  let automaticFoodTalkService: AutomaticFoodTalkService;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock TTS service
    mockTTSService = new TextToSpeechService() as jest.Mocked<TextToSpeechService>;
    mockTTSService.isEnabled.mockReturnValue(true);
    mockTTSService.generateSpeech.mockResolvedValue(mockAudioStream);
    
    // Mock response generator
    mockResponseGenerator = new KanyeResponseGenerator() as jest.Mocked<KanyeResponseGenerator>;
    mockResponseGenerator.generateRandomFoodTalk.mockReturnValue("Man nigga, watermelon is straight fire");
    
    // Create voice command handler
    voiceCommandHandler = new VoiceCommandHandler();
    
    // Replace private services with mocks
    (voiceCommandHandler as any).textToSpeech = mockTTSService;
    (voiceCommandHandler as any).responseGenerator = mockResponseGenerator;
    
    // Create automatic food talk service
    automaticFoodTalkService = new AutomaticFoodTalkService({
      enabled: true,
      idlePeriodMinutes: 1,
      minIntervalMinutes: 1,
      maxIntervalMinutes: 2,
      requiresTTS: true,
      requiresVoiceChannel: true
    });
  });

  describe('TTS Integration', () => {
    beforeEach(() => {
      // Set up voice connection
      (voiceCommandHandler as any).voiceConnections.set('guild-123', mockVoiceConnection);
    });

    it('should play TTS when food talk is triggered', async () => {
      const foodTalkMessage = "Man nigga, watermelon is straight fire";
      
      await voiceCommandHandler.speakResponse('guild-123', { command: 'food' });
      
      expect(mockTTSService.generateSpeech).toHaveBeenCalledWith(foodTalkMessage);
      expect(mockVoiceConnection.state.subscription.player.play).toHaveBeenCalled();
    });

    it('should not play TTS when TTS is disabled', async () => {
      mockTTSService.isEnabled.mockReturnValue(false);
      
      await voiceCommandHandler.speakResponse('guild-123', { command: 'food' });
      
      expect(mockTTSService.generateSpeech).not.toHaveBeenCalled();
      expect(mockVoiceConnection.state.subscription.player.play).not.toHaveBeenCalled();
    });

    it('should not play TTS when no voice connection exists', async () => {
      (voiceCommandHandler as any).voiceConnections.clear();
      
      await voiceCommandHandler.speakResponse('guild-123', { command: 'food' });
      
      expect(mockTTSService.generateSpeech).not.toHaveBeenCalled();
      expect(mockVoiceConnection.state.subscription.player.play).not.toHaveBeenCalled();
    });

    it('should handle TTS generation failures gracefully', async () => {
      mockTTSService.generateSpeech.mockResolvedValue(null);
      
      await expect(voiceCommandHandler.speakResponse('guild-123', { command: 'food' }))
        .resolves.not.toThrow();
        
      expect(mockVoiceConnection.state.subscription.player.play).not.toHaveBeenCalled();
    });

    it('should handle audio player errors gracefully', async () => {
      mockVoiceConnection.state.subscription.player.play.mockImplementation(() => {
        throw new Error('Player error');
      });
      
      await expect(voiceCommandHandler.speakResponse('guild-123', { command: 'food' }))
        .resolves.not.toThrow();
    });
  });

  describe('Food Talk Service TTS Requirements', () => {
    it('should not start tracking when TTS is required but disabled', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', false, true);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(false);
    });

    it('should start tracking when TTS is required and enabled', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
    });

    it('should allow tracking without TTS when not required', () => {
      automaticFoodTalkService.updateConfig({ requiresTTS: false });
      automaticFoodTalkService.startGuildTracking('guild-123', false, true);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
    });

    it('should handle TTS requirement changes dynamically', () => {
      // Start with TTS not required
      automaticFoodTalkService.updateConfig({ requiresTTS: false });
      automaticFoodTalkService.startGuildTracking('guild-123', false, true);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
      
      // Change to require TTS - should stop tracking existing guild
      automaticFoodTalkService.updateConfig({ requiresTTS: true });
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(false);
    });
  });

  describe('Voice Channel Requirements', () => {
    it('should not start tracking when voice channel is required but not connected', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, false);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(false);
    });

    it('should start tracking when voice channel is required and connected', () => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
    });

    it('should allow tracking without voice channel when not required', () => {
      automaticFoodTalkService.updateConfig({ requiresVoiceChannel: false });
      automaticFoodTalkService.startGuildTracking('guild-123', true, false);
      expect(automaticFoodTalkService.isGuildActive('guild-123')).toBe(true);
    });
  });

  describe('Integration with Voice Command Handler', () => {
    beforeEach(() => {
      (voiceCommandHandler as any).voiceConnections.set('guild-123', mockVoiceConnection);
    });

    it('should integrate food talk service with voice command handler', (done) => {
      automaticFoodTalkService.startGuildTracking('guild-123', true, true);
      
      automaticFoodTalkService.on('foodTalk', async (event) => {
        expect(event.guildId).toBe('guild-123');
        expect(event.message).toBe("Man nigga, watermelon is straight fire");
        expect(event.foodType).toBe('watermelon');
        
        // Simulate TTS response
        await voiceCommandHandler.speakResponse(event.guildId, { command: 'food' });
        
        expect(mockTTSService.generateSpeech).toHaveBeenCalledWith(event.message);
        done();
      });
      
      // Force trigger food talk
      automaticFoodTalkService.forceTriggerfoodTalk('guild-123');
    });

    it('should handle multiple food talk types with different TTS responses', async () => {
      const testCases = [
        { 
          mockReturn: "Man nigga, watermelon is straight fire",
          expectedCall: "Man nigga, watermelon is straight fire"
        },
        { 
          mockReturn: "Yo nigga, fried chicken is the ultimate comfort food",
          expectedCall: "Yo nigga, fried chicken is the ultimate comfort food"
        },
        { 
          mockReturn: "Kool-Aid the drink of champions nigga",
          expectedCall: "Kool-Aid the drink of champions nigga"
        }
      ];

      for (const testCase of testCases) {
        mockResponseGenerator.generateResponse.mockReturnValue(testCase.mockReturn);
        
        await voiceCommandHandler.speakResponse('guild-123', { command: 'food' });
        
        expect(mockTTSService.generateSpeech).toHaveBeenCalledWith(testCase.expectedCall);
        
        jest.clearAllMocks();
      }
    });
  });

  describe('TTS Service Configuration', () => {
    it('should respect TTS service enabled state', () => {
      expect(mockTTSService.isEnabled()).toBe(true);
      
      mockTTSService.isEnabled.mockReturnValue(false);
      expect(mockTTSService.isEnabled()).toBe(false);
    });

    it('should handle TTS service initialization failures', () => {
      const failingTTSService = new TextToSpeechService({ enabled: false });
      expect(failingTTSService.isEnabled()).toBe(false);
    });

    it('should handle missing API keys gracefully', () => {
      const originalEnv = process.env.ELEVENLABS_API_KEY;
      delete process.env.ELEVENLABS_API_KEY;
      
      const ttsService = new TextToSpeechService({ enabled: true });
      expect(ttsService.isEnabled()).toBe(false);
      
      // Restore environment
      if (originalEnv) {
        process.env.ELEVENLABS_API_KEY = originalEnv;
      }
    });
  });

  describe('Performance and Error Handling', () => {
    beforeEach(() => {
      (voiceCommandHandler as any).voiceConnections.set('guild-123', mockVoiceConnection);
    });

    it('should handle concurrent TTS requests', async () => {
      const promises = [
        voiceCommandHandler.speakResponse('guild-123', { command: 'food' }),
        voiceCommandHandler.speakResponse('guild-123', { command: 'food' }),
        voiceCommandHandler.speakResponse('guild-123', { command: 'food' })
      ];
      
      await Promise.all(promises);
      
      expect(mockTTSService.generateSpeech).toHaveBeenCalledTimes(3);
    });

    it('should handle TTS timeout gracefully', async () => {
      const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
      mockTTSService.generateSpeech.mockImplementation(() => delay(5000).then(() => mockAudioStream));
      
      // Should not hang indefinitely
      const startTime = Date.now();
      await voiceCommandHandler.speakResponse('guild-123', { command: 'food' });
      const endTime = Date.now();
      
      // Should complete in reasonable time
      expect(endTime - startTime).toBeLessThan(6000);
    });
  });
});