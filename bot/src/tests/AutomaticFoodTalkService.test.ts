import { AutomaticFoodTalkService, FoodTalkConfig } from '../services/AutomaticFoodTalkService';
import { KanyeResponseGenerator } from '../services/KanyeResponseGenerator';

// Mock the KanyeResponseGenerator
jest.mock('../services/KanyeResponseGenerator');

describe('AutomaticFoodTalkService', () => {
  let service: AutomaticFoodTalkService;
  let mockResponseGenerator: jest.Mocked<KanyeResponseGenerator>;
  
  const testGuildId = 'test-guild-123';
  const defaultConfig: FoodTalkConfig = {
    enabled: true,
    idlePeriodMinutes: 1, // 1 minute for faster tests
    minIntervalMinutes: 1,
    maxIntervalMinutes: 2,
    requiresTTS: true,
    requiresVoiceChannel: true
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    mockResponseGenerator = new KanyeResponseGenerator() as jest.Mocked<KanyeResponseGenerator>;
    mockResponseGenerator.generateRandomFoodTalk.mockReturnValue("Man nigga, watermelon is straight fire");
    
    service = new AutomaticFoodTalkService(defaultConfig);
    // Replace the real generator with our mock
    (service as any).responseGenerator = mockResponseGenerator;
  });

  afterEach(() => {
    service.stopGuildTracking(testGuildId);
    jest.useRealTimers();
  });

  describe('Configuration and Initialization', () => {
    it('should initialize with default config when no config provided', () => {
      const defaultService = new AutomaticFoodTalkService();
      const config = defaultService.getConfig();
      
      expect(config.enabled).toBe(true);
      expect(config.idlePeriodMinutes).toBe(15);
      expect(config.minIntervalMinutes).toBe(10);
      expect(config.maxIntervalMinutes).toBe(30);
      expect(config.requiresTTS).toBe(true);
      expect(config.requiresVoiceChannel).toBe(true);
    });

    it('should allow config override', () => {
      const customConfig = {
        enabled: false,
        idlePeriodMinutes: 5,
        requiresTTS: false
      };
      
      const customService = new AutomaticFoodTalkService(customConfig);
      const config = customService.getConfig();
      
      expect(config.enabled).toBe(false);
      expect(config.idlePeriodMinutes).toBe(5);
      expect(config.requiresTTS).toBe(false);
      expect(config.requiresVoiceChannel).toBe(true); // default
    });

    it('should update config dynamically', () => {
      const newConfig = {
        idlePeriodMinutes: 20,
        requiresTTS: false
      };
      
      service.updateConfig(newConfig);
      const config = service.getConfig();
      
      expect(config.idlePeriodMinutes).toBe(20);
      expect(config.requiresTTS).toBe(false);
      expect(config.enabled).toBe(true); // unchanged
    });
  });

  describe('Guild Tracking', () => {
    it('should start tracking when conditions are met', () => {
      service.startGuildTracking(testGuildId, true, true);
      
      expect(service.isGuildActive(testGuildId)).toBe(true);
      expect(service.getActiveGuilds()).toContain(testGuildId);
    });

    it('should not start tracking when TTS is required but disabled', () => {
      service.startGuildTracking(testGuildId, false, true);
      
      expect(service.isGuildActive(testGuildId)).toBe(false);
      expect(service.getActiveGuilds()).not.toContain(testGuildId);
    });

    it('should not start tracking when voice channel is required but not connected', () => {
      service.startGuildTracking(testGuildId, true, false);
      
      expect(service.isGuildActive(testGuildId)).toBe(false);
      expect(service.getActiveGuilds()).not.toContain(testGuildId);
    });

    it('should not start tracking when service is disabled', () => {
      service.updateConfig({ enabled: false });
      service.startGuildTracking(testGuildId, true, true);
      
      expect(service.isGuildActive(testGuildId)).toBe(false);
    });

    it('should stop tracking guild', () => {
      service.startGuildTracking(testGuildId, true, true);
      expect(service.isGuildActive(testGuildId)).toBe(true);
      
      service.stopGuildTracking(testGuildId);
      expect(service.isGuildActive(testGuildId)).toBe(false);
    });
  });

  describe('Idle Period and Timing', () => {
    beforeEach(() => {
      service.startGuildTracking(testGuildId, true, true);
    });

    it('should schedule food talk after idle period', () => {
      const foodTalkSpy = jest.fn();
      service.on('foodTalk', foodTalkSpy);
      
      // Fast forward past idle period + min interval
      jest.advanceTimersByTime((defaultConfig.idlePeriodMinutes + defaultConfig.maxIntervalMinutes) * 60 * 1000);
      
      expect(foodTalkSpy).toHaveBeenCalledWith({
        guildId: testGuildId,
        message: "Man nigga, watermelon is straight fire",
        foodType: 'watermelon',
        timestamp: expect.any(Number)
      });
    });

    it('should reschedule food talk when activity occurs', () => {
      const foodTalkSpy = jest.fn();
      service.on('foodTalk', foodTalkSpy);
      
      // Advance halfway to trigger time
      jest.advanceTimersByTime(defaultConfig.idlePeriodMinutes * 30 * 1000);
      expect(foodTalkSpy).not.toHaveBeenCalled();
      
      // Update activity - should reschedule
      service.updateActivity(testGuildId);
      
      // Advance to original trigger time - should not trigger
      jest.advanceTimersByTime(defaultConfig.idlePeriodMinutes * 30 * 1000);
      expect(foodTalkSpy).not.toHaveBeenCalled();
      
      // Advance full cycle from activity update
      jest.advanceTimersByTime((defaultConfig.idlePeriodMinutes + defaultConfig.maxIntervalMinutes) * 60 * 1000);
      expect(foodTalkSpy).toHaveBeenCalled();
    });

    it('should respect minimum interval between food talks', () => {
      const foodTalkSpy = jest.fn();
      service.on('foodTalk', foodTalkSpy);
      
      // Trigger first food talk
      jest.advanceTimersByTime((defaultConfig.idlePeriodMinutes + defaultConfig.maxIntervalMinutes) * 60 * 1000);
      expect(foodTalkSpy).toHaveBeenCalledTimes(1);
      
      // Try to trigger again immediately - should not work due to min interval
      service.forceTriggerfoodTalk(testGuildId);
      expect(foodTalkSpy).toHaveBeenCalledTimes(1);
      
      // Advance past minimum interval
      jest.advanceTimersByTime(defaultConfig.minIntervalMinutes * 60 * 1000);
      service.forceTriggerfoodTalk(testGuildId);
      expect(foodTalkSpy).toHaveBeenCalledTimes(2);
    });

    it('should not trigger food talk if guild becomes inactive', () => {
      const foodTalkSpy = jest.fn();
      service.on('foodTalk', foodTalkSpy);
      
      // Stop tracking before timer fires
      jest.advanceTimersByTime(defaultConfig.idlePeriodMinutes * 30 * 1000);
      service.stopGuildTracking(testGuildId);
      
      // Advance past trigger time
      jest.advanceTimersByTime((defaultConfig.idlePeriodMinutes + defaultConfig.maxIntervalMinutes) * 60 * 1000);
      expect(foodTalkSpy).not.toHaveBeenCalled();
    });
  });

  describe('Food Talk Generation', () => {
    beforeEach(() => {
      service.startGuildTracking(testGuildId, true, true);
    });

    it('should generate different types of food talk', () => {
      const testCases = [
        { message: "Man nigga, watermelon is straight fire", expectedType: 'watermelon' },
        { message: "Yo nigga, fried chicken is the ultimate comfort food", expectedType: 'friedChicken' },
        { message: "Kool-Aid the drink of champions nigga", expectedType: 'koolAid' },
        { message: "Food talk got me hungry now nigga", expectedType: 'general' }
      ];

      testCases.forEach(({ message, expectedType }) => {
        mockResponseGenerator.generateRandomFoodTalk.mockReturnValue(message);
        
        const foodTalkSpy = jest.fn();
        service.on('foodTalk', foodTalkSpy);
        
        service.forceTriggerfoodTalk(testGuildId);
        
        expect(foodTalkSpy).toHaveBeenCalledWith({
          guildId: testGuildId,
          message,
          foodType: expectedType,
          timestamp: expect.any(Number)
        });
        
        service.removeAllListeners('foodTalk');
      });
    });

    it('should call KanyeResponseGenerator for food talk generation', () => {
      service.forceTriggerfoodTalk(testGuildId);
      
      expect(mockResponseGenerator.generateRandomFoodTalk).toHaveBeenCalled();
    });
  });

  describe('Statistics Tracking', () => {
    beforeEach(() => {
      service.startGuildTracking(testGuildId, true, true);
    });

    it('should initialize stats for new guild', () => {
      const stats = service.getGuildStats(testGuildId);
      
      expect(stats).toEqual({
        totalMessages: 0,
        lastFoodTalk: 0,
        averageInterval: 0,
        foodTalksByType: {}
      });
    });

    it('should update stats when food talk occurs', () => {
      mockResponseGenerator.generateRandomFoodTalk.mockReturnValue("Man nigga, watermelon is straight fire");
      
      service.forceTriggerfoodTalk(testGuildId);
      
      const stats = service.getGuildStats(testGuildId);
      expect(stats!.totalMessages).toBe(1);
      expect(stats!.lastFoodTalk).toBeGreaterThan(0);
      expect(stats!.foodTalksByType.watermelon).toBe(1);
    });

    it('should track multiple food talk types', () => {
      // Watermelon talk
      mockResponseGenerator.generateRandomFoodTalk.mockReturnValue("Man nigga, watermelon is straight fire");
      service.forceTriggerfoodTalk(testGuildId);
      
      // Wait past minimum interval
      jest.advanceTimersByTime(defaultConfig.minIntervalMinutes * 60 * 1000);
      
      // Chicken talk
      mockResponseGenerator.generateRandomFoodTalk.mockReturnValue("Yo nigga, fried chicken is the ultimate comfort food");
      service.forceTriggerfoodTalk(testGuildId);
      
      const stats = service.getGuildStats(testGuildId);
      expect(stats!.totalMessages).toBe(2);
      expect(stats!.foodTalksByType.watermelon).toBe(1);
      expect(stats!.foodTalksByType.friedChicken).toBe(1);
    });

    it('should return null stats for non-existent guild', () => {
      const stats = service.getGuildStats('non-existent-guild');
      expect(stats).toBeNull();
    });

    it('should return all stats', () => {
      const secondGuildId = 'test-guild-456';
      service.startGuildTracking(secondGuildId, true, true);
      
      service.forceTriggerfoodTalk(testGuildId);
      service.forceTriggerfoodTalk(secondGuildId);
      
      const allStats = service.getAllStats();
      expect(allStats.has(testGuildId)).toBe(true);
      expect(allStats.has(secondGuildId)).toBe(true);
      expect(allStats.get(testGuildId)!.totalMessages).toBe(1);
      expect(allStats.get(secondGuildId)!.totalMessages).toBe(1);
    });

    it('should clear stats', () => {
      service.forceTriggerfoodTalk(testGuildId);
      
      let stats = service.getGuildStats(testGuildId);
      expect(stats!.totalMessages).toBe(1);
      
      service.clearStats();
      
      stats = service.getGuildStats(testGuildId);
      expect(stats).toBeNull();
    });
  });

  describe('Activity Tracking', () => {
    beforeEach(() => {
      service.startGuildTracking(testGuildId, true, true);
    });

    it('should update last activity timestamp', () => {
      const beforeUpdate = Date.now();
      service.updateActivity(testGuildId);
      
      // Access private lastActivity map for testing
      const lastActivity = (service as any).lastActivity.get(testGuildId);
      expect(lastActivity).toBeGreaterThanOrEqual(beforeUpdate);
    });

    it('should allow manual setting of last activity for testing', () => {
      const testTimestamp = Date.now() - 10000;
      service.setLastActivity(testGuildId, testTimestamp);
      
      const lastActivity = (service as any).lastActivity.get(testGuildId);
      expect(lastActivity).toBe(testTimestamp);
    });

    it('should not trigger food talk if not idle long enough', () => {
      const foodTalkSpy = jest.fn();
      service.on('foodTalk', foodTalkSpy);
      
      // Set recent activity
      service.updateActivity(testGuildId);
      
      // Try to force trigger - should not work because not idle long enough
      service.forceTriggerfoodTalk(testGuildId);
      expect(foodTalkSpy).not.toHaveBeenCalled();
      
      // Set old activity
      const oldTimestamp = Date.now() - (defaultConfig.idlePeriodMinutes + 1) * 60 * 1000;
      service.setLastActivity(testGuildId, oldTimestamp);
      
      // Now it should work
      service.forceTriggerfoodTalk(testGuildId);
      expect(foodTalkSpy).toHaveBeenCalled();
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle multiple guilds independently', () => {
      const guild1 = 'guild-1';
      const guild2 = 'guild-2';
      
      service.startGuildTracking(guild1, true, true);
      service.startGuildTracking(guild2, true, true);
      
      expect(service.getActiveGuilds()).toEqual(expect.arrayContaining([guild1, guild2]));
      
      service.stopGuildTracking(guild1);
      
      expect(service.isGuildActive(guild1)).toBe(false);
      expect(service.isGuildActive(guild2)).toBe(true);
    });

    it('should handle configuration changes affecting active guilds', () => {
      service.startGuildTracking(testGuildId, true, true);
      expect(service.isGuildActive(testGuildId)).toBe(true);
      
      // Disable service - should stop all tracking
      service.updateConfig({ enabled: false });
      expect(service.isGuildActive(testGuildId)).toBe(false);
    });

    it('should handle food talk generation failure gracefully', () => {
      mockResponseGenerator.generateRandomFoodTalk.mockImplementation(() => {
        throw new Error('Generation failed');
      });
      
      const foodTalkSpy = jest.fn();
      service.on('foodTalk', foodTalkSpy);
      
      // Should not crash the service
      expect(() => service.forceTriggerfoodTalk(testGuildId)).not.toThrow();
      expect(foodTalkSpy).not.toHaveBeenCalled();
    });

    it('should handle edge case of zero or negative timing values', () => {
      const edgeConfig = {
        idlePeriodMinutes: 0,
        minIntervalMinutes: 0,
        maxIntervalMinutes: 0
      };
      
      service.updateConfig(edgeConfig);
      service.startGuildTracking(testGuildId, true, true);
      
      const foodTalkSpy = jest.fn();
      service.on('foodTalk', foodTalkSpy);
      
      // Should still work with minimal timing
      jest.advanceTimersByTime(1000); // 1 second
      expect(foodTalkSpy).toHaveBeenCalled();
    });
  });
});