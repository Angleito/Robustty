import { Client } from 'discord.js';
import { RedisClient } from './RedisClient';
export declare class MonitoringService {
    private client;
    private redis;
    private metricsInterval?;
    constructor(client: Client, redis: RedisClient);
    start(): void;
    stop(): void;
    private collectMetrics;
    private checkThresholds;
    private sendAlert;
    getMetrics(): Promise<any>;
    getHistoricalMetrics(hours?: number): Promise<any[]>;
    getHealthStatus(): Promise<{
        healthy: boolean;
        reason: string;
        issues?: undefined;
        metrics?: undefined;
    } | {
        healthy: boolean;
        issues: string[];
        metrics: any;
        reason?: undefined;
    }>;
}
//# sourceMappingURL=MonitoringService.d.ts.map