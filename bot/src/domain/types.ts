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

export interface SearchSession {
  sessionId: string;
  userId: string;
  guildId: string;
  query: string;
  results: YouTubeVideo[];
  createdAt: number;
  expiresAt: number;
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

export interface VoiceCommand {
  id: string;
  userId: string;
  guildId: string;
  command: string;
  parameters: string[];
  confidence: number;
  timestamp: number;
  processingTimeMs: number;
}

export interface AudioSegment {
  id: string;
  guildId: string;
  userId: string;
  audioData: Buffer;
  duration: number;
  sampleRate: number;
  channels: number;
  timestamp: number;
  isWakeWordDetected: boolean;
  wakeWordConfidence?: number;
}

export interface VoiceSession {
  sessionId: string;
  guildId: string;
  userId: string;
  channelId: string;
  isActive: boolean;
  startedAt: number;
  lastActivityAt: number;
  commandsProcessed: number;
  currentState: 'idle' | 'listening' | 'processing' | 'responding';
}

export interface SpeechRecognitionResult {
  text: string;
  confidence: number;
  isPartial: boolean;
  language: string;
  processingTimeMs: number;
  alternatives?: Array<{
    text: string;
    confidence: number;
  }>;
}

export interface WakeWordResult {
  detected: boolean;
  confidence: number;
  keyword: string;
  startTime: number;
  endTime: number;
}