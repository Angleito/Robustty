import { Client, CommandInteraction } from 'discord.js';
import { ButtonHandler } from './ButtonHandler';
import { QueueManager } from '../domain/QueueManager';
import { PlaybackStrategyManager } from '../services/PlaybackStrategyManager';
import { ErrorHandler } from '../services/ErrorHandler';
import { MonitoringService } from '../services/MonitoringService';
import { SearchResultHandler } from '../services/SearchResultHandler';
import { Track, YouTubeVideo } from '../domain/types';
export declare class MusicBot {
    private client;
    private commandHandler;
    private buttonHandler;
    private voiceManager;
    private queueManager;
    private youtubeService;
    private playbackStrategy;
    private redis;
    private errorHandler;
    private monitoringService;
    private searchResultHandler;
    constructor();
    initialize(): Promise<void>;
    start(): Promise<void>;
    play(query: string, interaction: CommandInteraction): Promise<void>;
    playSelectedVideo(video: YouTubeVideo, interaction: CommandInteraction): Promise<void>;
    playSelectedVideoFromButton(video: YouTubeVideo, guildId: string, userId: string): Promise<{
        success: boolean;
        message: string;
    }>;
    addToQueue(track: Track): Promise<void>;
    skip(guildId: string): Promise<void>;
    stop(guildId: string): Promise<void>;
    searchYouTube(query: string): Promise<YouTubeVideo[]>;
    getPlaylist(playlistId: string): Promise<YouTubeVideo[]>;
    private playNext;
    getClient(): Client<boolean>;
    getQueueManager(): QueueManager;
    getButtonHandler(): ButtonHandler;
    getNekoPool(): import("../services/NekoPoolManager").NekoPoolManager;
    getPlaybackStrategy(): PlaybackStrategyManager;
    getMonitoringService(): MonitoringService;
    getErrorHandler(): ErrorHandler;
    getSearchResultHandler(): SearchResultHandler;
}
//# sourceMappingURL=MusicBot.d.ts.map