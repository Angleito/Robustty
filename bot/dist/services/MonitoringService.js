"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MonitoringService = void 0;
const logger_1 = require("./logger");
class MonitoringService {
    client;
    redis;
    metricsInterval;
    constructor(client, redis) {
        this.client = client;
        this.redis = redis;
    }
    start() {
        this.metricsInterval = setInterval(() => {
            this.collectMetrics();
        }, 60000);
        this.collectMetrics();
    }
    stop() {
        if (this.metricsInterval) {
            clearInterval(this.metricsInterval);
        }
    }
    async collectMetrics() {
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
            await this.redis.set('metrics:current', JSON.stringify(metrics), 300);
            const hourKey = `metrics:history:${new Date().getHours()}`;
            await this.redis.getClient().lpush(hourKey, JSON.stringify(metrics));
            await this.redis.getClient().ltrim(hourKey, 0, 59);
            await this.redis.getClient().expire(hourKey, 86400);
            await this.checkThresholds(metrics);
        }
        catch (error) {
            logger_1.logger.error('Failed to collect metrics:', error);
        }
    }
    async checkThresholds(metrics) {
        const memoryUsageMB = metrics.system.memoryUsage.heapUsed / 1024 / 1024;
        if (memoryUsageMB > 500) {
            logger_1.logger.warn(`High memory usage: ${memoryUsageMB.toFixed(2)}MB`);
            await this.sendAlert('High Memory Usage', `Heap usage: ${memoryUsageMB.toFixed(2)}MB`);
        }
        if (metrics.discord.ping > 500) {
            logger_1.logger.warn(`High Discord ping: ${metrics.discord.ping}ms`);
            await this.sendAlert('High Discord Ping', `Current ping: ${metrics.discord.ping}ms`);
        }
    }
    async sendAlert(title, description) {
        const webhook = process.env.ADMIN_NOTIFICATION_WEBHOOK;
        if (!webhook)
            return;
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
        }
        catch (error) {
            logger_1.logger.error('Failed to send monitoring alert:', error);
        }
    }
    async getMetrics() {
        const current = await this.redis.get('metrics:current');
        return current ? JSON.parse(current) : null;
    }
    async getHistoricalMetrics(hours = 1) {
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
exports.MonitoringService = MonitoringService;
//# sourceMappingURL=MonitoringService.js.map