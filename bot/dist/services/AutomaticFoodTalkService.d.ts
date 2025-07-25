import { EventEmitter } from 'events';
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
export declare class AutomaticFoodTalkService extends EventEmitter {
    private config;
    private responseGenerator;
    private idleTimers;
    private lastActivity;
    private lastFoodTalk;
    private stats;
    private activeGuilds;
    constructor(config?: Partial<FoodTalkConfig>);
    startGuildTracking(guildId: string, isTTSEnabled: boolean, isInVoiceChannel: boolean): void;
    stopGuildTracking(guildId: string): void;
    updateActivity(guildId: string): void;
    private scheduleNextFoodTalk;
    private triggerFoodTalk;
    private extractFoodType;
    getGuildStats(guildId: string): FoodTalkStats | null;
    getAllStats(): Map<string, FoodTalkStats>;
    getActiveGuilds(): string[];
    isGuildActive(guildId: string): boolean;
    updateConfig(newConfig: Partial<FoodTalkConfig>): void;
    getConfig(): FoodTalkConfig;
    forceTriggerfoodTalk(guildId: string): void;
    setLastActivity(guildId: string, timestamp: number): void;
    clearStats(): void;
}
//# sourceMappingURL=AutomaticFoodTalkService.d.ts.map