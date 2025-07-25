"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AutomaticFoodTalkService = void 0;
const events_1 = require("events");
const KanyeResponseGenerator_1 = require("./KanyeResponseGenerator");
const logger_1 = require("./logger");
class AutomaticFoodTalkService extends events_1.EventEmitter {
    config;
    responseGenerator;
    idleTimers = new Map();
    lastActivity = new Map();
    lastFoodTalk = new Map();
    stats = new Map();
    activeGuilds = new Set();
    constructor(config = {}) {
        super();
        this.config = {
            enabled: config.enabled ?? true,
            idlePeriodMinutes: config.idlePeriodMinutes ?? 15,
            minIntervalMinutes: config.minIntervalMinutes ?? 10,
            maxIntervalMinutes: config.maxIntervalMinutes ?? 30,
            requiresTTS: config.requiresTTS ?? true,
            requiresVoiceChannel: config.requiresVoiceChannel ?? true
        };
        this.responseGenerator = new KanyeResponseGenerator_1.KanyeResponseGenerator();
        logger_1.logger.info(`[AutomaticFoodTalk] Service initialized with config:`, this.config);
    }
    startGuildTracking(guildId, isTTSEnabled, isInVoiceChannel) {
        if (!this.config.enabled) {
            logger_1.logger.debug(`[AutomaticFoodTalk] Service disabled, skipping guild ${guildId}`);
            return;
        }
        if (this.config.requiresTTS && !isTTSEnabled) {
            logger_1.logger.debug(`[AutomaticFoodTalk] TTS required but not enabled for guild ${guildId}`);
            return;
        }
        if (this.config.requiresVoiceChannel && !isInVoiceChannel) {
            logger_1.logger.debug(`[AutomaticFoodTalk] Voice channel required but not connected for guild ${guildId}`);
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
        logger_1.logger.info(`[AutomaticFoodTalk] Started tracking for guild ${guildId}`);
    }
    stopGuildTracking(guildId) {
        this.activeGuilds.delete(guildId);
        const timer = this.idleTimers.get(guildId);
        if (timer) {
            clearTimeout(timer);
            this.idleTimers.delete(guildId);
        }
        logger_1.logger.info(`[AutomaticFoodTalk] Stopped tracking for guild ${guildId}`);
    }
    updateActivity(guildId) {
        if (!this.activeGuilds.has(guildId))
            return;
        this.lastActivity.set(guildId, Date.now());
        const existingTimer = this.idleTimers.get(guildId);
        if (existingTimer) {
            clearTimeout(existingTimer);
        }
        this.scheduleNextFoodTalk(guildId);
        logger_1.logger.debug(`[AutomaticFoodTalk] Activity updated for guild ${guildId}, rescheduling food talk`);
    }
    scheduleNextFoodTalk(guildId) {
        const lastTalk = this.lastFoodTalk.get(guildId) || 0;
        const now = Date.now();
        const timeSinceLastTalk = now - lastTalk;
        const minInterval = this.config.minIntervalMinutes * 60 * 1000;
        if (timeSinceLastTalk < minInterval) {
            const remainingTime = minInterval - timeSinceLastTalk;
            logger_1.logger.debug(`[AutomaticFoodTalk] Recent food talk for guild ${guildId}, waiting ${Math.round(remainingTime / 1000 / 60)} more minutes`);
            setTimeout(() => this.scheduleNextFoodTalk(guildId), remainingTime);
            return;
        }
        const idlePeriod = this.config.idlePeriodMinutes * 60 * 1000;
        const minIntervalMs = this.config.minIntervalMinutes * 60 * 1000;
        const maxIntervalMs = this.config.maxIntervalMinutes * 60 * 1000;
        const randomInterval = Math.random() * (maxIntervalMs - minIntervalMs) + minIntervalMs;
        const totalDelay = idlePeriod + randomInterval;
        const timer = setTimeout(() => {
            this.triggerFoodTalk(guildId);
        }, totalDelay);
        this.idleTimers.set(guildId, timer);
        const delayMinutes = Math.round(totalDelay / 1000 / 60);
        logger_1.logger.debug(`[AutomaticFoodTalk] Scheduled food talk for guild ${guildId} in ${delayMinutes} minutes`);
    }
    triggerFoodTalk(guildId) {
        if (!this.activeGuilds.has(guildId)) {
            logger_1.logger.debug(`[AutomaticFoodTalk] Guild ${guildId} no longer active, skipping food talk`);
            return;
        }
        const lastActivity = this.lastActivity.get(guildId) || 0;
        const idlePeriod = this.config.idlePeriodMinutes * 60 * 1000;
        const timeSinceActivity = Date.now() - lastActivity;
        if (timeSinceActivity < idlePeriod) {
            logger_1.logger.debug(`[AutomaticFoodTalk] Not idle long enough for guild ${guildId}, rescheduling`);
            this.scheduleNextFoodTalk(guildId);
            return;
        }
        const foodTalk = this.responseGenerator.generateRandomFoodTalk();
        const foodType = this.extractFoodType(foodTalk);
        const stats = this.stats.get(guildId);
        stats.totalMessages++;
        stats.lastFoodTalk = Date.now();
        stats.foodTalksByType[foodType] = (stats.foodTalksByType[foodType] || 0) + 1;
        this.lastFoodTalk.set(guildId, Date.now());
        logger_1.logger.info(`[AutomaticFoodTalk] Triggered food talk for guild ${guildId}: "${foodTalk}"`);
        this.emit('foodTalk', {
            guildId,
            message: foodTalk,
            foodType,
            timestamp: Date.now()
        });
        this.scheduleNextFoodTalk(guildId);
    }
    extractFoodType(message) {
        if (message.includes('watermelon'))
            return 'watermelon';
        if (message.includes('chicken'))
            return 'friedChicken';
        if (message.includes('Kool-Aid') || message.includes('kool aid'))
            return 'koolAid';
        return 'general';
    }
    getGuildStats(guildId) {
        return this.stats.get(guildId) || null;
    }
    getAllStats() {
        return new Map(this.stats);
    }
    getActiveGuilds() {
        return Array.from(this.activeGuilds);
    }
    isGuildActive(guildId) {
        return this.activeGuilds.has(guildId);
    }
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        logger_1.logger.info(`[AutomaticFoodTalk] Config updated:`, this.config);
        const activeGuilds = Array.from(this.activeGuilds);
        activeGuilds.forEach(guildId => {
            this.stopGuildTracking(guildId);
        });
    }
    getConfig() {
        return { ...this.config };
    }
    forceTriggerfoodTalk(guildId) {
        if (this.activeGuilds.has(guildId)) {
            this.triggerFoodTalk(guildId);
        }
    }
    setLastActivity(guildId, timestamp) {
        this.lastActivity.set(guildId, timestamp);
    }
    clearStats() {
        this.stats.clear();
        this.lastFoodTalk.clear();
    }
}
exports.AutomaticFoodTalkService = AutomaticFoodTalkService;
//# sourceMappingURL=AutomaticFoodTalkService.js.map