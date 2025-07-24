import { NekoInstance, Cookie } from '../domain/types';
import { NekoInstanceImpl } from './NekoInstanceImpl';
import { RedisClient } from './RedisClient';
import { logger } from './logger';

export class NekoPoolManager {
  private instances: Map<string, NekoInstanceImpl> = new Map();
  private redis: RedisClient;
  private readonly MAX_INSTANCES = 1; // Single neko instance
  private readonly HEALTH_CHECK_INTERVAL = 60000; // 1 minute
  private healthCheckTimer?: NodeJS.Timeout;

  constructor(redis: RedisClient) {
    this.redis = redis;
  }

  async initialize() {
    logger.info('Initializing neko instance pool...');
    
    for (let i = 0; i < this.MAX_INSTANCES; i++) {
      const instance = new NekoInstanceImpl(`neko-${i}`, this.redis);
      await instance.initialize();
      this.instances.set(instance.id, instance);
    }

    await this.restoreSessions();
    this.startHealthChecks();
  }

  async getHealthyInstance(): Promise<NekoInstance | null> {
    const availableInstances = Array.from(this.instances.values())
      .filter(instance => !instance.currentVideo && instance.isAuthenticated)
      .sort((a, b) => a.getLastUsed() - b.getLastUsed());

    if (availableInstances.length > 0) {
      return availableInstances[0];
    }

    // Try to find any authenticated instance
    const authenticatedInstances = Array.from(this.instances.values())
      .filter(instance => instance.isAuthenticated);

    if (authenticatedInstances.length === 0) {
      logger.error('No authenticated neko instances available');
      await this.notifyAdminForAuth();
      return null;
    }

    // Wait for an instance to become available
    return await this.waitForAvailableInstance();
  }

  private async waitForAvailableInstance(): Promise<NekoInstance | null> {
    const maxWaitTime = 30000; // 30 seconds
    const checkInterval = 1000; // 1 second
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
            logger.warn(`Instance ${instance.id} needs authentication`);
            await this.notifyAdminForAuth();
          }
        } else {
          // Save current session
          const cookies = await instance.getAuthCookies();
          await this.saveSession(instance.id, cookies);
        }
      } catch (error) {
        logger.error(`Session maintenance error for ${instance.id}:`, error);
      }
    }
  }

  private async restoreSessions() {
    for (const instance of this.instances.values()) {
      await this.restoreSession(instance.id);
    }
  }

  private async restoreSession(instanceId: string): Promise<boolean> {
    try {
      const encryptedCookies = await this.redis.get(`session:${instanceId}`);
      if (!encryptedCookies) return false;

      const cookies = JSON.parse(encryptedCookies) as Cookie[];
      const instance = this.instances.get(instanceId);
      
      if (instance) {
        await instance.restoreSession(cookies);
        return true;
      }
      
      return false;
    } catch (error) {
      logger.error(`Failed to restore session for ${instanceId}:`, error);
      return false;
    }
  }

  private async saveSession(instanceId: string, cookies: Cookie[]) {
    try {
      const encrypted = JSON.stringify(cookies);
      await this.redis.set(`session:${instanceId}`, encrypted, 604800); // 7 days
    } catch (error) {
      logger.error(`Failed to save session for ${instanceId}:`, error);
    }
  }

  private startHealthChecks() {
    this.healthCheckTimer = setInterval(() => {
      this.performHealthChecks();
    }, this.HEALTH_CHECK_INTERVAL);
  }

  private async performHealthChecks() {
    for (const instance of this.instances.values()) {
      try {
        const healthy = await instance.healthCheck();
        if (!healthy) {
          logger.warn(`Instance ${instance.id} is unhealthy, attempting restart...`);
          await instance.restart();
        }
      } catch (error) {
        logger.error(`Health check failed for ${instance.id}:`, error);
      }
    }
  }

  private async notifyAdminForAuth() {
    const webhook = process.env.ADMIN_NOTIFICATION_WEBHOOK;
    if (!webhook) return;

    try {
      await fetch(webhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: '⚠️ **Neko Authentication Required**\nOne or more neko instances need authentication. Please use `/admin auth` command.'
        })
      });
    } catch (error) {
      logger.error('Failed to send admin notification:', error);
    }
  }

  async getInstanceById(id: string): Promise<NekoInstanceImpl | undefined> {
    return this.instances.get(id);
  }

  async getAllInstances(): Promise<NekoInstanceImpl[]> {
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