import { google, youtube_v3 } from 'googleapis';
import { YouTubeVideo } from '../domain/types';
import { logger } from './logger';
import { RedisClient } from './RedisClient';

export class YouTubeService {
  private youtube: youtube_v3.Youtube;
  private redis: RedisClient;
  private readonly CACHE_TTL = 3600; // 1 hour

  constructor() {
    this.youtube = google.youtube({
      version: 'v3',
      auth: process.env.YOUTUBE_API_KEY
    });
    this.redis = new RedisClient();
  }

  async search(query: string, maxResults: number = 5): Promise<YouTubeVideo[]> {
    const cacheKey = `youtube:search:${query}:${maxResults}`;
    
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      return JSON.parse(cached);
    }

    try {
      const response = await this.youtube.search.list({
        part: ['snippet'],
        q: query,
        type: ['video'],
        maxResults,
        videoCategoryId: '10' // Music category
      });

      if (!response.data.items || response.data.items.length === 0) {
        return [];
      }

      const videoIds = response.data.items
        .map(item => item.id?.videoId)
        .filter(Boolean) as string[];

      const videos = await this.getVideoDetails(videoIds);
      
      await this.redis.set(cacheKey, JSON.stringify(videos), this.CACHE_TTL);
      
      return videos;
    } catch (error) {
      logger.error('YouTube search error:', error);
      throw error;
    }
  }

  async getVideo(videoId: string): Promise<YouTubeVideo | null> {
    const cacheKey = `youtube:video:${videoId}`;
    
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      return JSON.parse(cached);
    }

    const videos = await this.getVideoDetails([videoId]);
    const video = videos[0] || null;
    
    if (video) {
      await this.redis.set(cacheKey, JSON.stringify(video), this.CACHE_TTL);
    }
    
    return video;
  }

  async getPlaylist(playlistId: string): Promise<YouTubeVideo[]> {
    const cacheKey = `youtube:playlist:${playlistId}`;
    
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      return JSON.parse(cached);
    }

    try {
      const videos: YouTubeVideo[] = [];
      let pageToken: string | undefined;

      do {
        const response = await this.youtube.playlistItems.list({
          part: ['snippet'],
          playlistId,
          maxResults: 50,
          pageToken
        });

        if (!response.data.items) break;

        const videoIds = response.data.items
          .map(item => item.snippet?.resourceId?.videoId)
          .filter(Boolean) as string[];

        const videoDetails = await this.getVideoDetails(videoIds);
        videos.push(...videoDetails);

        pageToken = response.data.nextPageToken || undefined;
      } while (pageToken && videos.length < 200); // Limit to 200 videos

      await this.redis.set(cacheKey, JSON.stringify(videos), this.CACHE_TTL);
      
      return videos;
    } catch (error) {
      logger.error('YouTube playlist error:', error);
      throw error;
    }
  }

  private async getVideoDetails(videoIds: string[]): Promise<YouTubeVideo[]> {
    if (videoIds.length === 0) return [];

    try {
      const response = await this.youtube.videos.list({
        part: ['snippet', 'contentDetails'],
        id: videoIds
      });

      if (!response.data.items) return [];

      return response.data.items.map(item => ({
        id: item.id!,
        title: item.snippet?.title || 'Unknown',
        url: `https://www.youtube.com/watch?v=${item.id}`,
        duration: this.parseDuration(item.contentDetails?.duration || 'PT0S'),
        thumbnail: item.snippet?.thumbnails?.default?.url || '',
        channel: item.snippet?.channelTitle || 'Unknown',
        description: item.snippet?.description ?? undefined
      }));
    } catch (error) {
      logger.error('YouTube video details error:', error);
      return [];
    }
  }

  private parseDuration(isoDuration: string): number {
    const match = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
    if (!match) return 0;

    const hours = parseInt(match[1] || '0');
    const minutes = parseInt(match[2] || '0');
    const seconds = parseInt(match[3] || '0');

    return hours * 3600 + minutes * 60 + seconds;
  }

  async isVideoAvailable(videoId: string): Promise<boolean> {
    try {
      const video = await this.getVideo(videoId);
      return video !== null;
    } catch {
      return false;
    }
  }
}