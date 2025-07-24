import { YouTubeVideo } from '../domain/types';
import { RedisClient } from './RedisClient';
export declare class ErrorHandler {
    private retryQueue;
    private redis;
    private adminWebhook?;
    constructor(redis: RedisClient);
    handlePlaybackError(error: any, video: YouTubeVideo): Promise<void>;
    private classifyError;
    private queueForRetry;
    private notifyAdminForReauth;
    private handleNekoError;
    private logUnknownError;
    private updateMetrics;
    private setupRetryWorker;
    getErrorMetrics(): Promise<Record<string, number>>;
}
//# sourceMappingURL=ErrorHandler.d.ts.map