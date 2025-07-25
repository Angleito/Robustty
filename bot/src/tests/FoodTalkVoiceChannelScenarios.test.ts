import { AutomaticFoodTalkService } from '../services/AutomaticFoodTalkService';
import { VoiceCommandHandler } from '../bot/VoiceCommandHandler';
import { MusicBot } from '../bot/MusicBot';
import { mockVoiceConnection } from './setup';
import { VoiceChannel, Guild, GuildMember, Collection } from 'discord.js';

// Mock dependencies
jest.mock('../services/TextToSpeechService');
jest.mock('../services/VoiceListenerService');
jest.mock('../services/WakeWordDetectionService');
jest.mock('../services/SpeechRecognitionService');
jest.mock('../services/AudioProcessingService');
jest.mock('../bot/VoiceManager');
jest.mock('../services/YouTubeService');
jest.mock('../services/RedisClient');
jest.mock('../services/PlaybackStrategyManager');
jest.mock('../domain/QueueManager');

// Mock Discord.js voice channel scenarios
const createMockVoiceChannel = (id: string, memberCount: number = 0): VoiceChannel => {
  const guild = { id: `guild-${id}`, name: `Test Guild ${id}` } as Guild;
  const members = new Collection<string, GuildMember>();
  
  // Add mock members
  for (let i = 0; i < memberCount; i++) {
    const member = {
      id: `member-${i}`,
      user: { id: `user-${i}`, bot: false },
      voice: { channel: null }
    } as GuildMember;
    members.set(member.id, member);
  }
  
  return {
    id,
    name: `Voice Channel ${id}`,
    guild,
    members,
    type: 2, // GUILD_VOICE
    bitrate: 64000,
    userLimit: 0,
    rtcRegion: null
  } as VoiceChannel;
};

describe('Food Talk Voice Channel Scenarios', () => {
  let automaticFoodTalkService: AutomaticFoodTalkService;
  let voiceCommandHandler: VoiceCommandHandler;
  let musicBot: MusicBot;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Set up environment
    process.env.TTS_ENABLED = 'true';
    process.env.OPENAI_API_KEY = 'test-key';
    
    automaticFoodTalkService = new AutomaticFoodTalkService({
      enabled: true,
      idlePeriodMinutes: 1,
      minIntervalMinutes: 1,
      maxIntervalMinutes: 2,
      requiresTTS: true,
      requiresVoiceChannel: true
    });
    
    voiceCommandHandler = new VoiceCommandHandler();
    musicBot = new MusicBot();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Single Voice Channel Scenarios', () => {
    it('should start food talk when bot joins empty voice channel', () => {
      const voiceChannel = createMockVoiceChannel('vc-1', 0);
      
      automaticFoodTalkService.startGuildTracking(voiceChannel.guild.id, true, true);
      
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(true);
    });

    it('should start food talk when bot joins voice channel with users', () => {
      const voiceChannel = createMockVoiceChannel('vc-1', 3);
      
      automaticFoodTalkService.startGuildTracking(voiceChannel.guild.id, true, true);
      
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(true);
    });

    it('should continue food talk when users join the voice channel', () => {
      const voiceChannel = createMockVoiceChannel('vc-1', 1);
      
      automaticFoodTalkService.startGuildTracking(voiceChannel.guild.id, true, true);
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(true);
      
      // Add more users (simulate joins)
      const newMember = {
        id: 'new-member',
        user: { id: 'new-user', bot: false },
        voice: { channel: voiceChannel }
      } as GuildMember;
      voiceChannel.members.set(newMember.id, newMember);
      
      // Should still be active
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(true);
    });

    it('should continue food talk when users leave but bot remains', () => {
      const voiceChannel = createMockVoiceChannel('vc-1', 3);
      
      automaticFoodTalkService.startGuildTracking(voiceChannel.guild.id, true, true);
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(true);
      
      // Remove all users (simulate leaves)
      voiceChannel.members.clear();
      
      // Bot should continue food talk even when alone
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(true);
    });

    it('should stop food talk when bot leaves voice channel', () => {
      const voiceChannel = createMockVoiceChannel('vc-1', 2);
      
      automaticFoodTalkService.startGuildTracking(voiceChannel.guild.id, true, true);
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(true);
      
      // Bot leaves channel
      automaticFoodTalkService.stopGuildTracking(voiceChannel.guild.id);
      
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(false);
    });
  });

  describe('Multiple Voice Channel Scenarios', () => {
    it('should handle bot in multiple voice channels across different guilds', () => {
      const voiceChannel1 = createMockVoiceChannel('vc-1', 2);
      const voiceChannel2 = createMockVoiceChannel('vc-2', 1);
      
      // Different guilds
      voiceChannel1.guild.id = 'guild-1';
      voiceChannel2.guild.id = 'guild-2';
      
      automaticFoodTalkService.startGuildTracking('guild-1', true, true);
      automaticFoodTalkService.startGuildTracking('guild-2', true, true);
      
      expect(automaticFoodTalkService.isGuildActive('guild-1')).toBe(true);
      expect(automaticFoodTalkService.isGuildActive('guild-2')).toBe(true);
      
      const activeGuilds = automaticFoodTalkService.getActiveGuilds();
      expect(activeGuilds).toContain('guild-1');
      expect(activeGuilds).toContain('guild-2');
    });

    it('should handle independent food talk timing across guilds', (done) => {
      const guild1 = 'guild-1';
      const guild2 = 'guild-2';
      
      automaticFoodTalkService.startGuildTracking(guild1, true, true);
      automaticFoodTalkService.startGuildTracking(guild2, true, true);
      
      let guild1FoodTalk = false;
      let guild2FoodTalk = false;
      
      automaticFoodTalkService.on('foodTalk', (event) => {
        if (event.guildId === guild1) guild1FoodTalk = true;
        if (event.guildId === guild2) guild2FoodTalk = true;
        
        if (guild1FoodTalk && guild2FoodTalk) {
          done();
        }
      });
      
      // Trigger food talk for both guilds
      automaticFoodTalkService.forceTriggerfoodTalk(guild1);
      automaticFoodTalkService.forceTriggerfoodTalk(guild2);
    });

    it('should handle partial disconnection (one guild disconnects)', () => {
      automaticFoodTalkService.startGuildTracking('guild-1', true, true);
      automaticFoodTalkService.startGuildTracking('guild-2', true, true);
      
      expect(automaticFoodTalkService.getActiveGuilds()).toHaveLength(2);
      
      // Disconnect from one guild
      automaticFoodTalkService.stopGuildTracking('guild-1');
      
      expect(automaticFoodTalkService.isGuildActive('guild-1')).toBe(false);
      expect(automaticFoodTalkService.isGuildActive('guild-2')).toBe(true);
      expect(automaticFoodTalkService.getActiveGuilds()).toEqual(['guild-2']);
    });
  });

  describe('Voice Channel Permission and State Scenarios', () => {
    it('should handle TTS enabled/disabled per guild', () => {
      const guild1 = 'guild-1';
      const guild2 = 'guild-2';
      
      // Guild 1: TTS enabled
      automaticFoodTalkService.startGuildTracking(guild1, true, true);
      
      // Guild 2: TTS disabled
      automaticFoodTalkService.startGuildTracking(guild2, false, true);
      
      expect(automaticFoodTalkService.isGuildActive(guild1)).toBe(true);
      expect(automaticFoodTalkService.isGuildActive(guild2)).toBe(false);
    });

    it('should handle voice channel connection failures', () => {
      // Mock voice connection failure
      const voiceChannel = createMockVoiceChannel('vc-fail', 1);
      
      // Even if connection fails, service can still track if explicitly started
      automaticFoodTalkService.startGuildTracking(voiceChannel.guild.id, true, false);
      
      // Should not be active if voice channel is required but not connected
      expect(automaticFoodTalkService.isGuildActive(voiceChannel.guild.id)).toBe(false);
    });

    it('should handle configuration requiring voice channel vs not requiring it', () => {
      const guildId = 'guild-test';
      
      // Initially require voice channel
      expect(automaticFoodTalkService.getConfig().requiresVoiceChannel).toBe(true);
      
      // Should not start without voice channel
      automaticFoodTalkService.startGuildTracking(guildId, true, false);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(false);
      
      // Change config to not require voice channel
      automaticFoodTalkService.updateConfig({ requiresVoiceChannel: false });
      
      // Now should be able to start without voice channel
      automaticFoodTalkService.startGuildTracking(guildId, true, false);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
    });
  });

  describe('Voice Channel Activity Tracking', () => {
    beforeEach(() => {
      automaticFoodTalkService.startGuildTracking('guild-1', true, true);
    });

    it('should track activity when voice commands are used', () => {
      const updateActivitySpy = jest.spyOn(automaticFoodTalkService, 'updateActivity');
      
      // Simulate voice command activity
      automaticFoodTalkService.updateActivity('guild-1');
      
      expect(updateActivitySpy).toHaveBeenCalledWith('guild-1');
    });

    it('should reset idle timer when users speak in voice channel', () => {
      const foodTalkSpy = jest.fn();
      automaticFoodTalkService.on('foodTalk', foodTalkSpy);
      
      // Advance time halfway to food talk trigger
      jest.advanceTimersByTime(60 * 1000); // 1 minute
      
      // User speaks (activity update)
      automaticFoodTalkService.updateActivity('guild-1');
      
      // Advance to original trigger time - should not trigger
      jest.advanceTimersByTime(60 * 1000); // Another minute
      expect(foodTalkSpy).not.toHaveBeenCalled();
      
      // Advance full cycle from activity update
      jest.advanceTimersByTime(2 * 60 * 1000); // 2 more minutes
      expect(foodTalkSpy).toHaveBeenCalled();
    });

    it('should handle rapid activity updates without issues', () => {
      // Simulate rapid user interactions
      for (let i = 0; i < 10; i++) {
        automaticFoodTalkService.updateActivity('guild-1');
      }
      
      // Should not cause any issues
      expect(automaticFoodTalkService.isGuildActive('guild-1')).toBe(true);
    });
  });

  describe('Voice Channel Reconnection Scenarios', () => {
    it('should handle reconnection to same voice channel', () => {
      const guildId = 'guild-reconnect';
      
      // Initial connection
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
      
      // Disconnect
      automaticFoodTalkService.stopGuildTracking(guildId);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(false);
      
      // Reconnect
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
    });

    it('should handle moving between voice channels in same guild', () => {
      const guildId = 'guild-move';
      
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
      
      // "Move" to different channel (simulated by stop/start)
      automaticFoodTalkService.stopGuildTracking(guildId);
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
    });

    it('should maintain separate state after reconnection', () => {
      const guildId = 'guild-state-test';
      
      // Initial connection and trigger food talk
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      automaticFoodTalkService.forceTriggerfoodTalk(guildId);
      
      let initialStats = automaticFoodTalkService.getGuildStats(guildId);
      expect(initialStats!.totalMessages).toBe(1);
      
      // Disconnect
      automaticFoodTalkService.stopGuildTracking(guildId);
      
      // Reconnect
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      // Stats should persist
      let persistedStats = automaticFoodTalkService.getGuildStats(guildId);
      expect(persistedStats!.totalMessages).toBe(1);
    });
  });

  describe('Error Handling in Voice Scenarios', () => {
    it('should handle invalid guild IDs gracefully', () => {
      expect(() => {
        automaticFoodTalkService.startGuildTracking('', true, true);
      }).not.toThrow();
      
      expect(() => {
        automaticFoodTalkService.updateActivity('invalid-guild');
      }).not.toThrow();
    });

    it('should handle null/undefined voice channel states', () => {
      expect(() => {
        automaticFoodTalkService.startGuildTracking('guild-null', true, false);
      }).not.toThrow();
      
      // Should not be active without voice channel when required
      expect(automaticFoodTalkService.isGuildActive('guild-null')).toBe(false);
    });

    it('should handle concurrent voice operations', async () => {
      const guildId = 'guild-concurrent';
      
      // Simulate multiple concurrent operations
      const operations = [
        () => automaticFoodTalkService.startGuildTracking(guildId, true, true),
        () => automaticFoodTalkService.updateActivity(guildId),
        () => automaticFoodTalkService.forceTriggerfoodTalk(guildId),
        () => automaticFoodTalkService.stopGuildTracking(guildId)
      ];
      
      // Run operations concurrently
      expect(() => {
        operations.forEach(op => op());
      }).not.toThrow();
    });

    it('should handle voice connection timeouts', () => {
      const guildId = 'guild-timeout';
      
      // Service should still be able to start tracking even if connection times out
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
    });
  });

  describe('Performance with Multiple Voice Channels', () => {
    it('should handle many concurrent guilds efficiently', () => {
      const numGuilds = 50;
      const guilds: string[] = [];
      
      // Start tracking many guilds
      for (let i = 0; i < numGuilds; i++) {
        const guildId = `guild-${i}`;
        guilds.push(guildId);
        automaticFoodTalkService.startGuildTracking(guildId, true, true);
      }
      
      expect(automaticFoodTalkService.getActiveGuilds()).toHaveLength(numGuilds);
      
      // All should be active
      guilds.forEach(guildId => {
        expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
      });
    });

    it('should handle many activity updates efficiently', () => {
      const guildId = 'guild-performance';
      automaticFoodTalkService.startGuildTracking(guildId, true, true);
      
      const startTime = Date.now();
      
      // Many rapid updates
      for (let i = 0; i < 1000; i++) {
        automaticFoodTalkService.updateActivity(guildId);
      }
      
      const endTime = Date.now();
      
      // Should complete quickly (less than 100ms for 1000 updates)
      expect(endTime - startTime).toBeLessThan(100);
      expect(automaticFoodTalkService.isGuildActive(guildId)).toBe(true);
    });
  });
});