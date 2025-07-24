"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NekoPoolManager = void 0;
const NekoInstanceImpl_1 = require("./NekoInstanceImpl");
const logger_1 = require("./logger");
class NekoPoolManager {
    instances = new Map();
    redis;
    MAX_INSTANCES = 3;
    HEALTH_CHECK_INTERVAL = 60000;
    healthCheckTimer;
    constructor(redis) {
        this.redis = redis;
    }
    async initialize() {
        logger_1.logger.info('Initializing neko instance pool...');
        for (let i = 0; i < this.MAX_INSTANCES; i++) {
            const instance = new NekoInstanceImpl_1.NekoInstanceImpl(`neko-${i}`, this.redis);
            await instance.initialize();
            this.instances.set(instance.id, instance);
        }
        await this.restoreSessions();
        this.startHealthChecks();
    }
    async getHealthyInstance() {
        const availableInstances = Array.from(this.instances.values())
            .filter(instance => !instance.currentVideo && instance.isAuthenticated)
            .sort((a, b) => a.getLastUsed() - b.getLastUsed());
        if (availableInstances.length > 0) {
            return availableInstances[0];
        }
        const authenticatedInstances = Array.from(this.instances.values())
            .filter(instance => instance.isAuthenticated);
        if (authenticatedInstances.length === 0) {
            logger_1.logger.error('No authenticated neko instances available');
            await this.notifyAdminForAuth();
            return null;
        }
        return await this.waitForAvailableInstance();
    }
    async waitForAvailableInstance() {
        const maxWaitTime = 30000;
        const checkInterval = 1000;
        const startTime = Date.now();
        while (Date.now() - startTime < maxWaitTime) {
            const available = Array.from(this.instances.values())
                .find(instance => !instance.currentVideo && instance.isAuthenticated);
            if (available) {
                return available;
            }
            await new Promise(resolve => setTimeout(resolve, checkInterval));
        }
        return null;
    }
    async maintainSessions() {
        for (const instance of this.instances.values()) {
            try {
                if (!instance.isAuthenticated) {
                    const restored = await this.restoreSession(instance.id);
                    if (!restored) {
                        logger_1.logger.warn(`Instance ${instance.id} needs authentication`);
                        await this.notifyAdminForAuth();
                    }
                }
                else {
                    const cookies = await instance.getAuthCookies();
                    await this.saveSession(instance.id, cookies);
                }
            }
            catch (error) {
                logger_1.logger.error(`Session maintenance error for ${instance.id}:`, error);
            }
        }
    }
    async restoreSessions() {
        for (const instance of this.instances.values()) {
            await this.restoreSession(instance.id);
        }
    }
    async restoreSession(instanceId) {
        try {
            const encryptedCookies = await this.redis.get(`session:${instanceId}`);
            if (!encryptedCookies)
                return false;
            const cookies = JSON.parse(encryptedCookies);
            const instance = this.instances.get(instanceId);
            if (instance) {
                await instance.restoreSession(cookies);
                return true;
            }
            return false;
        }
        catch (error) {
            logger_1.logger.error(`Failed to restore session for ${instanceId}:`, error);
            return false;
        }
    }
    async saveSession(instanceId, cookies) {
        try {
            const encrypted = JSON.stringify(cookies);
            await this.redis.set(`session:${instanceId}`, encrypted, 604800);
        }
        catch (error) {
            logger_1.logger.error(`Failed to save session for ${instanceId}:`, error);
        }
    }
    startHealthChecks() {
        this.healthCheckTimer = setInterval(() => {
            this.performHealthChecks();
        }, this.HEALTH_CHECK_INTERVAL);
    }
    async performHealthChecks() {
        for (const instance of this.instances.values()) {
            try {
                const healthy = await instance.healthCheck();
                if (!healthy) {
                    logger_1.logger.warn(`Instance ${instance.id} is unhealthy, attempting restart...`);
                    await instance.restart();
                }
            }
            catch (error) {
                logger_1.logger.error(`Health check failed for ${instance.id}:`, error);
            }
        }
    }
    async notifyAdminForAuth() {
        const webhook = process.env.ADMIN_NOTIFICATION_WEBHOOK;
        if (!webhook)
            return;
        try {
            await fetch(webhook, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: '⚠️ **Neko Authentication Required**\nOne or more neko instances need authentication. Please use `/admin auth` command.'
                })
            });
        }
        catch (error) {
            logger_1.logger.error('Failed to send admin notification:', error);
        }
    }
    async getInstanceById(id) {
        return this.instances.get(id);
    }
    async getAllInstances() {
        return Array.from(this.instances.values());
    }
    async shutdown() {
        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
        }
        for (const instance of this.instances.values()) {
            await instance.shutdown();
        }
    }
}
exports.NekoPoolManager = NekoPoolManager;
//# sourceMappingURL=NekoPoolManager.js.map