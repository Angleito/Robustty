import { EventEmitter } from 'events';
import { KanyeResponseGenerator } from './KanyeResponseGenerator';
import { logger } from './logger';

export interface FoodTalkConfig {
  enabled: boolean;
  idlePeriodMinutes: number;
  minIntervalMinutes: number;
  maxIntervalMinutes: number;
  requiresTTS: boolean;
  requiresVoiceChannel: boolean;
}

export interface FoodTalkStats {
  totalMessages: number;
  lastFoodTalk: number;
  averageInterval: number;
  foodTalksByType: Record<string, number>;
}

export class AutomaticFoodTalkService extends EventEmitter {
  private config: FoodTalkConfig;
  private responseGenerator: KanyeResponseGenerator;
  private idleTimers: Map<string, NodeJS.Timeout> = new Map();
  private lastActivity: Map<string, number> = new Map();
  private lastFoodTalk: Map<string, number> = new Map();
  private stats: Map<string, FoodTalkStats> = new Map();
  private activeGuilds: Set<string> = new Set();

  constructor(config: Partial<FoodTalkConfig> = {}) {
    super();
    
    this.config = {
      enabled: config.enabled ?? true,
      idlePeriodMinutes: config.idlePeriodMinutes ?? 15,
      minIntervalMinutes: config.minIntervalMinutes ?? 10,
      maxIntervalMinutes: config.maxIntervalMinutes ?? 30,
      requiresTTS: config.requiresTTS ?? true,
      requiresVoiceChannel: config.requiresVoiceChannel ?? true
    };
    
    this.responseGenerator = new KanyeResponseGenerator();
    logger.info(`[AutomaticFoodTalk] Service initialized with config:`, this.config);
  }

  startGuildTracking(guildId: string, isTTSEnabled: boolean, isInVoiceChannel: boolean): void {
    if (!this.config.enabled) {
      logger.debug(`[AutomaticFoodTalk] Service disabled, skipping guild ${guildId}`);
      return;
    }

    if (this.config.requiresTTS && !isTTSEnabled) {
      logger.debug(`[AutomaticFoodTalk] TTS required but not enabled for guild ${guildId}`);
      return;
    }

    if (this.config.requiresVoiceChannel && !isInVoiceChannel) {
      logger.debug(`[AutomaticFoodTalk] Voice channel required but not connected for guild ${guildId}`);
      return;
    }

    this.activeGuilds.add(guildId);
    this.lastActivity.set(guildId, Date.now());
    
    if (!this.stats.has(guildId)) {
      this.stats.set(guildId, {
        totalMessages: 0,
        lastFoodTalk: 0,
        averageInterval: 0,
        foodTalksByType: {}
      });
    }

    this.scheduleNextFoodTalk(guildId);
    logger.info(`[AutomaticFoodTalk] Started tracking for guild ${guildId}`);
  }

  stopGuildTracking(guildId: string): void {
    this.activeGuilds.delete(guildId);
    
    const timer = this.idleTimers.get(guildId);
    if (timer) {
      clearTimeout(timer);
      this.idleTimers.delete(guildId);
    }
    
    logger.info(`[AutomaticFoodTalk] Stopped tracking for guild ${guildId}`);
  }

  updateActivity(guildId: string): void {
    if (!this.activeGuilds.has(guildId)) return;
    
    this.lastActivity.set(guildId, Date.now());
    
    // Clear existing timer and reschedule
    const existingTimer = this.idleTimers.get(guildId);
    if (existingTimer) {
      clearTimeout(existingTimer);
    }
    
    this.scheduleNextFoodTalk(guildId);
    logger.debug(`[AutomaticFoodTalk] Activity updated for guild ${guildId}, rescheduling food talk`);
  }

  private scheduleNextFoodTalk(guildId: string): void {
    const lastTalk = this.lastFoodTalk.get(guildId) || 0;
    const now = Date.now();
    const timeSinceLastTalk = now - lastTalk;
    const minInterval = this.config.minIntervalMinutes * 60 * 1000;
    
    // Don't schedule if we recently had food talk
    if (timeSinceLastTalk < minInterval) {
      const remainingTime = minInterval - timeSinceLastTalk;
      logger.debug(`[AutomaticFoodTalk] Recent food talk for guild ${guildId}, waiting ${Math.round(remainingTime / 1000 / 60)} more minutes`);
      
      setTimeout(() => this.scheduleNextFoodTalk(guildId), remainingTime);
      return;
    }

    const idlePeriod = this.config.idlePeriodMinutes * 60 * 1000;
    const minIntervalMs = this.config.minIntervalMinutes * 60 * 1000;
    const maxIntervalMs = this.config.maxIntervalMinutes * 60 * 1000;
    
    // Random interval between min and max
    const randomInterval = Math.random() * (maxIntervalMs - minIntervalMs) + minIntervalMs;
    const totalDelay = idlePeriod + randomInterval;

    const timer = setTimeout(() => {
      this.triggerFoodTalk(guildId);
    }, totalDelay);

    this.idleTimers.set(guildId, timer);
    
    const delayMinutes = Math.round(totalDelay / 1000 / 60);
    logger.debug(`[AutomaticFoodTalk] Scheduled food talk for guild ${guildId} in ${delayMinutes} minutes`);
  }

  private triggerFoodTalk(guildId: string): void {
    if (!this.activeGuilds.has(guildId)) {
      logger.debug(`[AutomaticFoodTalk] Guild ${guildId} no longer active, skipping food talk`);
      return;
    }

    const lastActivity = this.lastActivity.get(guildId) || 0;
    const idlePeriod = this.config.idlePeriodMinutes * 60 * 1000;
    const timeSinceActivity = Date.now() - lastActivity;

    // Only trigger if we've been idle long enough
    if (timeSinceActivity < idlePeriod) {
      logger.debug(`[AutomaticFoodTalk] Not idle long enough for guild ${guildId}, rescheduling`);
      this.scheduleNextFoodTalk(guildId);
      return;
    }

    const foodTalk = this.responseGenerator.generateRandomFoodTalk();
    const foodType = this.extractFoodType(foodTalk);
    
    // Update stats
    const stats = this.stats.get(guildId)!;
    stats.totalMessages++;
    stats.lastFoodTalk = Date.now();
    stats.foodTalksByType[foodType] = (stats.foodTalksByType[foodType] || 0) + 1;
    
    this.lastFoodTalk.set(guildId, Date.now());

    logger.info(`[AutomaticFoodTalk] Triggered food talk for guild ${guildId}: "${foodTalk}"`);
    
    this.emit('foodTalk', {
      guildId,
      message: foodTalk,
      foodType,
      timestamp: Date.now()
    });

    // Schedule next food talk
    this.scheduleNextFoodTalk(guildId);
  }

  private extractFoodType(message: string): string {
    if (message.includes('watermelon')) return 'watermelon';
    if (message.includes('chicken')) return 'friedChicken';
    if (message.includes('Kool-Aid') || message.includes('kool aid')) return 'koolAid';
    return 'general';
  }

  getGuildStats(guildId: string): FoodTalkStats | null {
    return this.stats.get(guildId) || null;
  }

  getAllStats(): Map<string, FoodTalkStats> {
    return new Map(this.stats);
  }

  getActiveGuilds(): string[] {
    return Array.from(this.activeGuilds);
  }

  isGuildActive(guildId: string): boolean {
    return this.activeGuilds.has(guildId);
  }

  updateConfig(newConfig: Partial<FoodTalkConfig>): void {
    this.config = { ...this.config, ...newConfig };
    logger.info(`[AutomaticFoodTalk] Config updated:`, this.config);
    
    // Restart all active guilds with new config
    const activeGuilds = Array.from(this.activeGuilds);
    activeGuilds.forEach(guildId => {
      this.stopGuildTracking(guildId);
      // Guild will need to re-register with current TTS/voice status
    });
  }

  getConfig(): FoodTalkConfig {
    return { ...this.config };
  }

  // Test methods for unit testing
  forceTriggerfoodTalk(guildId: string): void {
    if (this.activeGuilds.has(guildId)) {
      this.triggerFoodTalk(guildId);
    }
  }

  setLastActivity(guildId: string, timestamp: number): void {
    this.lastActivity.set(guildId, timestamp);
  }

  clearStats(): void {
    this.stats.clear();
    this.lastFoodTalk.clear();
  }
}