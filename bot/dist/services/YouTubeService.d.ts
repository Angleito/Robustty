import { YouTubeVideo } from '../domain/types';
export declare class YouTubeService {
    private youtube;
    private redis;
    private readonly CACHE_TTL;
    constructor();
    search(query: string, maxResults?: number): Promise<YouTubeVideo[]>;
    getVideo(videoId: string): Promise<YouTubeVideo | null>;
    getPlaylist(playlistId: string): Promise<YouTubeVideo[]>;
    private getVideoDetails;
    private parseDuration;
    isVideoAvailable(videoId: string): Promise<boolean>;
}
//# sourceMappingURL=YouTubeService.d.ts.map