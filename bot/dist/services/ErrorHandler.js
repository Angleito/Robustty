"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ErrorHandler = void 0;
const logger_1 = require("./logger");
const bullmq_1 = require("bullmq");
class ErrorHandler {
    retryQueue;
    redis;
    adminWebhook;
    constructor(redis) {
        this.redis = redis;
        this.adminWebhook = process.env.ADMIN_NOTIFICATION_WEBHOOK;
        this.retryQueue = new bullmq_1.Queue('playback-retry', {
            connection: redis.getBullMQConnection()
        });
        this.setupRetryWorker();
    }
    async handlePlaybackError(error, video) {
        const errorType = this.classifyError(error);
        logger_1.logger.error('Playback error:', {
            type: errorType,
            video: video.id,
            error: error.message,
            stack: error.stack
        });
        switch (errorType) {
            case 'rate_limit':
                await this.queueForRetry(video);
                break;
            case 'auth':
                await this.notifyAdminForReauth();
                break;
            case 'neko':
                await this.handleNekoError(error);
                break;
            case 'network':
                await this.queueForRetry(video, 5000);
                break;
            case 'audio_player':
                await this.handleAudioPlayerError(error, video);
                break;
            case 'stream':
                await this.handleStreamError(error, video);
                break;
            default:
                await this.logUnknownError(error, video);
        }
        await this.updateMetrics(errorType);
    }
    classifyError(error) {
        const message = error?.message?.toLowerCase() || '';
        const errorName = error?.name?.toLowerCase() || '';
        if (message.includes('429') || message.includes('rate limit')) {
            return 'rate_limit';
        }
        if (message.includes('auth') || message.includes('login')) {
            return 'auth';
        }
        if (message.includes('neko') || message.includes('browser')) {
            return 'neko';
        }
        if (message.includes('econnrefused') || message.includes('timeout') || message.includes('stream timeout')) {
            return 'network';
        }
        if (message.includes('aborted') || message.includes('audio player') || errorName.includes('error')) {
            return 'audio_player';
        }
        if (message.includes('stream') || message.includes('resource')) {
            return 'stream';
        }
        return 'unknown';
    }
    async queueForRetry(video, delay = 30000) {
        await this.retryQueue.add('retry-playback', {
            video,
            attempt: 1,
            timestamp: Date.now()
        }, {
            delay,
            attempts: 3,
            backoff: {
                type: 'exponential',
                delay: 30000
            }
        });
        logger_1.logger.info(`Queued video ${video.id} for retry in ${delay}ms`);
    }
    async notifyAdminForReauth() {
        if (!this.adminWebhook)
            return;
        try {
            await fetch(this.adminWebhook, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    embeds: [{
                            title: '⚠️ Authentication Required',
                            description: 'The bot needs re-authentication to continue playing music.',
                            color: 0xFF0000,
                            fields: [
                                {
                                    name: 'Action Required',
                                    value: 'Use `/admin auth` command to authenticate'
                                }
                            ],
                            timestamp: new Date().toISOString()
                        }]
                })
            });
        }
        catch (error) {
            logger_1.logger.error('Failed to send admin notification:', error);
        }
    }
    async handleNekoError(error) {
        logger_1.logger.error('Neko instance error:', error);
        const instanceId = error.instanceId;
        if (instanceId) {
            await this.redis.set(`neko:restart:${instanceId}`, '1', 60);
        }
    }
    async handleAudioPlayerError(error, video) {
        logger_1.logger.error('Audio player error detected:', error);
        if (error.message?.includes('aborted')) {
            await this.redis.set(`video:force_neko:${video.id}`, '1', 300);
            logger_1.logger.info(`Marked video ${video.id} for neko fallback due to player abort`);
        }
        await this.updateMetrics('audio_player_abort');
    }
    async handleStreamError(error, video) {
        logger_1.logger.error('Stream error detected:', error);
        if (error.message?.includes('timeout')) {
            await this.queueForRetry(video, 10000);
        }
        else {
            await this.redis.set(`video:force_neko:${video.id}`, '1', 300);
        }
    }
    async logUnknownError(error, video) {
        logger_1.logger.error('Unknown playback error:', {
            video: video.id,
            error: error.message,
            stack: error.stack
        });
    }
    async updateMetrics(errorType) {
        const key = `metrics:errors:${errorType}`;
        await this.redis.getClient().incr(key);
        const hourKey = `metrics:errors:${errorType}:${new Date().getHours()}`;
        await this.redis.getClient().incr(hourKey);
        await this.redis.getClient().expire(hourKey, 86400);
    }
    setupRetryWorker() {
        const worker = new bullmq_1.Worker('playback-retry', async (job) => {
            const { video, attempt } = job.data;
            logger_1.logger.info(`Retrying playback for ${video.id}, attempt ${attempt}`);
        }, {
            connection: this.redis.getBullMQConnection()
        });
        worker.on('failed', (job, err) => {
            logger_1.logger.error(`Retry job failed:`, err);
        });
    }
    async getErrorMetrics() {
        const errorTypes = ['rate_limit', 'auth', 'neko', 'network', 'unknown'];
        const metrics = {};
        for (const type of errorTypes) {
            const count = await this.redis.getClient().get(`metrics:errors:${type}`);
            metrics[type] = parseInt(count || '0');
        }
        return metrics;
    }
}
exports.ErrorHandler = ErrorHandler;
//# sourceMappingURL=ErrorHandler.js.map