import { NekoInstance } from '../domain/types';
import { NekoInstanceImpl } from './NekoInstanceImpl';
import { RedisClient } from './RedisClient';
export declare class NekoPoolManager {
    private instances;
    private redis;
    private readonly MAX_INSTANCES;
    private readonly HEALTH_CHECK_INTERVAL;
    private healthCheckTimer?;
    constructor(redis: RedisClient);
    initialize(): Promise<void>;
    getHealthyInstance(): Promise<NekoInstance | null>;
    private waitForAvailableInstance;
    maintainSessions(): Promise<void>;
    private restoreSessions;
    private restoreSession;
    private saveSession;
    private startHealthChecks;
    private performHealthChecks;
    private notifyAdminForAuth;
    getInstanceById(id: string): Promise<NekoInstanceImpl | undefined>;
    getAllInstances(): Promise<NekoInstanceImpl[]>;
    shutdown(): Promise<void>;
}
//# sourceMappingURL=NekoPoolManager.d.ts.map