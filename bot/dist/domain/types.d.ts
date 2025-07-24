export interface Track {
    id: string;
    title: string;
    url: string;
    duration: number;
    thumbnail: string;
    requestedBy: string;
}
export interface YouTubeVideo {
    id: string;
    title: string;
    url: string;
    duration: number;
    thumbnail: string;
    channel: string;
    description?: string;
}
export interface Queue {
    guildId: string;
    tracks: Track[];
    currentIndex: number;
    loop: 'none' | 'track' | 'queue';
}
export interface NekoInstance {
    id: string;
    isAuthenticated: boolean;
    currentVideo: string | null;
    playVideo(url: string): Promise<void>;
    pause(): Promise<void>;
    resume(): Promise<void>;
    seekTo(seconds: number): Promise<void>;
    getAuthCookies(): Promise<Cookie[]>;
    restoreSession(cookies: Cookie[]): Promise<void>;
}
export interface Cookie {
    name: string;
    value: string;
    domain: string;
    path: string;
    expires?: number;
    httpOnly?: boolean;
    secure?: boolean;
    sameSite?: 'strict' | 'lax' | 'none';
}
export type PlaybackMethod = 'direct' | 'neko';
import { Readable } from 'stream';
export interface PlaybackResult {
    method: PlaybackMethod;
    stream: Readable;
}
export interface ErrorInfo {
    type: 'rate_limit' | 'auth' | 'neko' | 'unknown';
    message: string;
    details?: any;
}
//# sourceMappingURL=types.d.ts.map