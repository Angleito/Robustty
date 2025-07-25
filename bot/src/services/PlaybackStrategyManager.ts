import { VoiceChannel } from 'discord.js';
import ytdl from '@distube/ytdl-core';
import * as playDl from 'play-dl';
import { YouTubeVideo, PlaybackResult, PlaybackMethod } from '../domain/types';
import { NekoPoolManager } from './NekoPoolManager';
import { AudioRouter } from './AudioRouter';
import { RedisClient } from './RedisClient';
import { logger } from './logger';

export class PlaybackStrategyManager {
  public nekoPool: NekoPoolManager;
  private audioRouter: AudioRouter;
  private redis: RedisClient;
  private failureCache: Map<string, number> = new Map();
  private readonly FAILURE_CACHE_TTL = 3600000; // 1 hour

  constructor(redis: RedisClient) {
    this.redis = redis;
    this.nekoPool = new NekoPoolManager(redis);
    this.audioRouter = new AudioRouter();
  }

  async attemptPlayback(
    video: YouTubeVideo, 
    voiceChannel: VoiceChannel
  ): Promise<PlaybackResult> {
    const failureCount = await this.getFailureCount(video.id);
    
    // Check if video is marked for forced neko fallback
    const forceNeko = await this.redis.get(`video:force_neko:${video.id}`);
    if (forceNeko) {
      logger.info(`Video ${video.id} marked for neko fallback due to previous errors`);
      return await this.nekoFallback(video);
    }
    
    // If failed recently, skip direct attempt
    if (failureCount > 2) {
      logger.info(`Video ${video.id} has failed ${failureCount} times, using neko fallback`);
      return await this.nekoFallback(video);
    }

    try {
      const stream = await this.directStream(video.url);
      await this.clearFailure(video.id);
      
      return {
        method: 'direct',
        stream
      };
    } catch (error) {
      if (this.isBotDetectionError(error)) {
        logger.warn(`Bot detection for video ${video.id}, falling back to neko`);
        await this.incrementFailure(video.id);
        return await this.nekoFallback(video);
      }
      throw error;
    }
  }

  private async directStream(url: string): Promise<import('stream').Readable> {
    let stream: import('stream').Readable | null = null;
    
    try {
      // Try ytdl-core first
      if (ytdl.validateURL(url)) {
        const info = await ytdl.getInfo(url);
        
        if (info.videoDetails.isLiveContent) {
          stream = ytdl(url, {
            quality: 'highestaudio',
            highWaterMark: 1 << 25,
            dlChunkSize: 0
          });
        } else {
          stream = ytdl(url, {
            filter: 'audioonly',
            quality: 'highestaudio',
            highWaterMark: 1 << 25
          });
        }
        
        // Add error handling to the stream
        stream.on('error', (error) => {
          logger.error('YTDL stream error:', error);
        });
        
        return stream;
      }
    } catch (error) {
      logger.warn('ytdl-core failed, trying play-dl:', error);
      if (stream) {
        stream.destroy();
      }
    }

    // Fallback to play-dl
    try {
      const result = await playDl.stream(url, {
        discordPlayerCompatibility: true
      });
      
      stream = result.stream;
      
      // Add error handling to the stream
      stream.on('error', (error) => {
        logger.error('play-dl stream error:', error);
      });
      
      return stream;
    } catch (error) {
      logger.error('Both ytdl-core and play-dl failed:', error);
      if (stream) {
        stream.destroy();
      }
      throw error;
    }
  }

  private async nekoFallback(video: YouTubeVideo): Promise<PlaybackResult> {
    const instance = await this.nekoPool.getHealthyInstance();
    
    if (!instance) {
      throw new Error('No healthy neko instances available');
    }

    await instance.playVideo(video.url);
    
    const stream = await this.audioRouter.captureStream(instance.id);
    
    await this.trackVideoHistory(video.id, 'neko');
    
    return {
      method: 'neko',
      stream
    };
  }

  private isBotDetectionError(error: any): boolean {
    const errorMessage = error?.message?.toLowerCase() || '';
    const botDetectionPhrases = [
      'sign in to confirm',
      'bot',
      'captcha',
      'verify',
      'age-restricted',
      'inappropriate',
      '429',
      'too many requests'
    ];
    
    return botDetectionPhrases.some(phrase => errorMessage.includes(phrase));
  }

  private async getFailureCount(videoId: string): Promise<number> {
    const cached = this.failureCache.get(videoId);
    if (cached !== undefined) return cached;
    
    const stored = await this.redis.get(`failure:${videoId}`);
    return stored ? parseInt(stored) : 0;
  }

  private async incrementFailure(videoId: string) {
    const current = await this.getFailureCount(videoId);
    const newCount = current + 1;
    
    this.failureCache.set(videoId, newCount);
    await this.redis.set(`failure:${videoId}`, newCount.toString(), this.FAILURE_CACHE_TTL / 1000);
    
    setTimeout(() => {
      this.failureCache.delete(videoId);
    }, this.FAILURE_CACHE_TTL);
  }

  private async clearFailure(videoId: string) {
    this.failureCache.delete(videoId);
    await this.redis.del(`failure:${videoId}`);
  }

  private async trackVideoHistory(videoId: string, method: PlaybackMethod) {
    await this.redis.hset('video:history', videoId, method);
    await this.redis.sadd(`videos:${method}`, videoId);
  }

  async getStats(): Promise<{
    direct: number;
    neko: number;
    recentFailures: number;
  }> {
    const directVideos = await this.redis.smembers('videos:direct');
    const nekoVideos = await this.redis.smembers('videos:neko');
    
    return {
      direct: directVideos.length,
      neko: nekoVideos.length,
      recentFailures: this.failureCache.size
    };
  }
}