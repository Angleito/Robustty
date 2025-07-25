import { VoiceConnection } from '@discordjs/voice';
import { VoiceChannel } from 'discord.js';
import { EventEmitter } from 'events';
import { Track } from '../domain/types';
import { PlaybackStrategyManager } from '../services/PlaybackStrategyManager';
export declare class VoiceManager extends EventEmitter {
    private connections;
    private players;
    private currentTracks;
    private playbackStrategy;
    private disconnectTimers;
    private foodTalkTimers;
    private voiceChannels;
    private idleTimeoutMs;
    private connectionStates;
    constructor(playbackStrategy: PlaybackStrategyManager);
    private logConnectionStatus;
    join(channel: VoiceChannel): Promise<VoiceConnection>;
    leave(guildId: string): Promise<void>;
    play(track: Track, guildId: string): Promise<void>;
    skip(guildId: string): void;
    stop(): void;
    isPlaying(guildId: string): boolean;
    playTTS(stream: any, guildId: string, text: string): Promise<void>;
    getVoiceChannel(guildId: string): VoiceChannel | null;
    private startDisconnectTimer;
    private clearDisconnectTimer;
    private startFoodTalkTimer;
    private clearFoodTalkTimer;
    getGuildStatus(guildId: string): any;
    checkConnectionHealth(guildId: string): Promise<boolean>;
}
//# sourceMappingURL=VoiceManager.d.ts.map