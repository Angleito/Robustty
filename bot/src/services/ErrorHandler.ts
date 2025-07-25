import { YouTubeVideo } from '../domain/types';
import { logger } from './logger';
import { Queue, Worker } from 'bullmq';
import { RedisClient } from './RedisClient';

export class ErrorHandler {
  private retryQueue: Queue;
  private redis: RedisClient;
  private adminWebhook?: string;
  
  constructor(redis: RedisClient) {
    this.redis = redis;
    this.adminWebhook = process.env.ADMIN_NOTIFICATION_WEBHOOK;
    
    this.retryQueue = new Queue('playback-retry', {
      connection: redis.getBullMQConnection()
    });

    this.setupRetryWorker();
  }

  async handlePlaybackError(error: any, video: YouTubeVideo) {
    const errorType = this.classifyError(error);
    
    logger.error('Playback error:', {
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

  private classifyError(error: any): string {
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
    
    // Audio player specific errors
    if (message.includes('aborted') || message.includes('audio player') || errorName.includes('error')) {
      return 'audio_player';
    }
    
    if (message.includes('stream') || message.includes('resource')) {
      return 'stream';
    }
    
    return 'unknown';
  }

  private async queueForRetry(video: YouTubeVideo, delay: number = 30000) {
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
    
    logger.info(`Queued video ${video.id} for retry in ${delay}ms`);
  }

  private async notifyAdminForReauth() {
    if (!this.adminWebhook) return;
    
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
    } catch (error) {
      logger.error('Failed to send admin notification:', error);
    }
  }

  private async handleNekoError(error: any) {
    logger.error('Neko instance error:', error);
    
    // Try to restart the affected instance
    const instanceId = error.instanceId;
    if (instanceId) {
      await this.redis.set(`neko:restart:${instanceId}`, '1', 60);
    }
  }

  private async handleAudioPlayerError(error: any, video: YouTubeVideo) {
    logger.error('Audio player error detected:', error);
    
    // Mark video for fallback to neko if direct stream fails
    if (error.message?.includes('aborted')) {
      await this.redis.set(`video:force_neko:${video.id}`, '1', 300); // 5 minutes
      logger.info(`Marked video ${video.id} for neko fallback due to player abort`);
    }
    
    // Don't retry immediately, let the system try next track
    await this.updateMetrics('audio_player_abort');
  }

  private async handleStreamError(error: any, video: YouTubeVideo) {
    logger.error('Stream error detected:', error);
    
    // For stream errors, try again with different method
    if (error.message?.includes('timeout')) {
      await this.queueForRetry(video, 10000); // Retry in 10 seconds
    } else {
      // For other stream errors, force neko fallback
      await this.redis.set(`video:force_neko:${video.id}`, '1', 300);
    }
  }

  private async logUnknownError(error: any, video: YouTubeVideo) {
    logger.error('Unknown playback error:', {
      video: video.id,
      error: error.message,
      stack: error.stack
    });
  }

  private async updateMetrics(errorType: string) {
    const key = `metrics:errors:${errorType}`;
    await this.redis.getClient().incr(key);
    
    // Update hourly metrics
    const hourKey = `metrics:errors:${errorType}:${new Date().getHours()}`;
    await this.redis.getClient().incr(hourKey);
    await this.redis.getClient().expire(hourKey, 86400); // 24 hours
  }

  private setupRetryWorker() {
    const worker = new Worker('playback-retry', async (job) => {
      const { video, attempt } = job.data;
      
      logger.info(`Retrying playback for ${video.id}, attempt ${attempt}`);
      
      // The actual retry logic would be handled by the PlaybackStrategyManager
      // This is just for queuing and tracking
    }, {
      connection: this.redis.getBullMQConnection()
    });

    worker.on('failed', (job, err) => {
      logger.error(`Retry job failed:`, err);
    });
  }

  async getErrorMetrics() {
    const errorTypes = ['rate_limit', 'auth', 'neko', 'network', 'unknown'];
    const metrics: Record<string, number> = {};
    
    for (const type of errorTypes) {
      const count = await this.redis.getClient().get(`metrics:errors:${type}`);
      metrics[type] = parseInt(count || '0');
    }
    
    return metrics;
  }
}