import { VoiceConnection } from '@discordjs/voice';
import { VoiceChannel } from 'discord.js';
import { EventEmitter } from 'events';
import { VoiceSession } from '../domain/types';
export declare class VoiceListenerService extends EventEmitter {
    private receivers;
    private sessions;
    private readonly bufferTimeout;
    private readonly maxBufferSize;
    private cleanupIntervals;
    constructor();
    startListening(connection: VoiceConnection, channel: VoiceChannel): Promise<void>;
    private setupUserAudioStreams;
    private refreshUserStreams;
    private setupAudioStreamHandlers;
    private handleSpeakingStart;
    private handleSpeakingEnd;
    private handleAudioData;
    private processAudioBuffer;
    stopListening(guildId: string): Promise<void>;
    createVoiceSession(guildId: string, userId: string, channelId: string): string;
    updateSessionState(sessionId: string, state: VoiceSession['currentState']): void;
    getActiveSession(guildId: string, userId: string): VoiceSession | null;
    private setupCleanupRoutine;
    private startCleanupRoutine;
    private stopCleanupRoutine;
    private cleanupGuildBuffers;
    private cleanupInactiveSessions;
    isListening(guildId: string): boolean;
    getActiveGuilds(): string[];
    getSessionCount(): number;
}
//# sourceMappingURL=VoiceListenerService.d.ts.map