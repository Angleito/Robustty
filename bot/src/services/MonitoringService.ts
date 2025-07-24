import { Client } from 'discord.js';
import { RedisClient } from './RedisClient';
import { logger } from './logger';

export class MonitoringService {
  private client: Client;
  private redis: RedisClient;
  private metricsInterval?: NodeJS.Timeout;
  
  constructor(client: Client, redis: RedisClient) {
    this.client = client;
    this.redis = redis;
  }

  start() {
    // Collect metrics every minute
    this.metricsInterval = setInterval(() => {
      this.collectMetrics();
    }, 60000);

    // Initial collection
    this.collectMetrics();
  }

  stop() {
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval);
    }
  }

  private async collectMetrics() {
    try {
      const metrics = {
        timestamp: Date.now(),
        discord: {
          ping: this.client.ws.ping,
          guilds: this.client.guilds.cache.size,
          users: this.client.users.cache.size,
          voiceConnections: this.client.voice.adapters.size
        },
        system: {
          memoryUsage: process.memoryUsage(),
          uptime: process.uptime(),
          cpuUsage: process.cpuUsage()
        }
      };

      // Store current metrics
      await this.redis.set('metrics:current', JSON.stringify(metrics), 300);

      // Store historical data
      const hourKey = `metrics:history:${new Date().getHours()}`;
      await this.redis.getClient().lpush(hourKey, JSON.stringify(metrics));
      await this.redis.getClient().ltrim(hourKey, 0, 59); // Keep last 60 entries (1 hour)
      await this.redis.getClient().expire(hourKey, 86400); // 24 hours

      // Check thresholds
      await this.checkThresholds(metrics);

    } catch (error) {
      logger.error('Failed to collect metrics:', error);
    }
  }

  private async checkThresholds(metrics: any) {
    // High memory usage warning
    const memoryUsageMB = metrics.system.memoryUsage.heapUsed / 1024 / 1024;
    if (memoryUsageMB > 500) {
      logger.warn(`High memory usage: ${memoryUsageMB.toFixed(2)}MB`);
      await this.sendAlert('High Memory Usage', `Heap usage: ${memoryUsageMB.toFixed(2)}MB`);
    }

    // High ping warning
    if (metrics.discord.ping > 500) {
      logger.warn(`High Discord ping: ${metrics.discord.ping}ms`);
      await this.sendAlert('High Discord Ping', `Current ping: ${metrics.discord.ping}ms`);
    }
  }

  private async sendAlert(title: string, description: string) {
    const webhook = process.env.ADMIN_NOTIFICATION_WEBHOOK;
    if (!webhook) return;

    try {
      await fetch(webhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          embeds: [{
            title: `⚠️ ${title}`,
            description,
            color: 0xFFFF00,
            timestamp: new Date().toISOString()
          }]
        })
      });
    } catch (error) {
      logger.error('Failed to send monitoring alert:', error);
    }
  }

  async getMetrics() {
    const current = await this.redis.get('metrics:current');
    return current ? JSON.parse(current) : null;
  }

  async getHistoricalMetrics(hours: number = 1) {
    const metrics = [];
    const currentHour = new Date().getHours();
    
    for (let i = 0; i < hours; i++) {
      const hour = (currentHour - i + 24) % 24;
      const hourKey = `metrics:history:${hour}`;
      const data = await this.redis.getClient().lrange(hourKey, 0, -1);
      
      metrics.push(...data.map(d => JSON.parse(d)));
    }
    
    return metrics.sort((a, b) => a.timestamp - b.timestamp);
  }

  async getHealthStatus() {
    const metrics = await this.getMetrics();
    if (!metrics) {
      return { healthy: false, reason: 'No metrics available' };
    }

    const issues = [];
    
    if (metrics.discord.ping > 1000) {
      issues.push(`High ping: ${metrics.discord.ping}ms`);
    }
    
    if (metrics.system.memoryUsage.heapUsed > 1024 * 1024 * 1024) {
      issues.push('Memory usage above 1GB');
    }
    
    if (metrics.discord.guilds === 0) {
      issues.push('Not connected to any guilds');
    }

    return {
      healthy: issues.length === 0,
      issues,
      metrics
    };
  }
}