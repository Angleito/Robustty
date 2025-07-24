import { VoiceChannel } from 'discord.js';
import { YouTubeVideo, PlaybackResult } from '../domain/types';
import { NekoPoolManager } from './NekoPoolManager';
import { RedisClient } from './RedisClient';
export declare class PlaybackStrategyManager {
    nekoPool: NekoPoolManager;
    private audioRouter;
    private redis;
    private failureCache;
    private readonly FAILURE_CACHE_TTL;
    constructor(redis: RedisClient);
    attemptPlayback(video: YouTubeVideo, voiceChannel: VoiceChannel): Promise<PlaybackResult>;
    private directStream;
    private nekoFallback;
    private isBotDetectionError;
    private getFailureCount;
    private incrementFailure;
    private clearFailure;
    private trackVideoHistory;
    getStats(): Promise<{
        direct: number;
        neko: number;
        recentFailures: number;
    }>;
}
//# sourceMappingURL=PlaybackStrategyManager.d.ts.map