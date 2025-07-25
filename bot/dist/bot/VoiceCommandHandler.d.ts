import { VoiceChannel } from 'discord.js';
import { EventEmitter } from 'events';
export declare class VoiceCommandHandler extends EventEmitter {
    private voiceListener;
    private wakeWordDetector;
    private speechRecognition;
    private textToSpeech;
    private responseGenerator;
    private processingQueues;
    private activeProcessing;
    private voiceConnections;
    constructor();
    private setupEventHandlers;
    startListening(voiceChannel: VoiceChannel, connection: any): Promise<void>;
    stopListening(guildId: string): Promise<void>;
    private handleAudioSegment;
    private processAudioQueue;
    private processAudioSegment;
    private captureCommandAudio;
    private processCommandWithWhisper;
    private detectWakeWord;
    private processSpeechRecognition;
    private parseVoiceCommand;
    isListening(guildId: string): boolean;
    getActiveGuilds(): string[];
    updateWakeWordThreshold(threshold: number): void;
    getSupportedCommands(): string[];
    getProcessingStats(): {
        activeGuilds: number;
        queuedSegments: number;
        activeProcessing: number;
        sessionCount: number;
    };
    createVoiceSession(guildId: string, userId: string, channelId: string): string;
    getActiveSession(guildId: string, userId: string): import("../domain/types").VoiceSession | null;
    getCostStats(): {
        totalRequests: number;
        totalMinutesProcessed: number;
        estimatedCost: number;
        averageCostPerRequest: number;
        lastRequestTime: number;
    };
    logCostSummary(): void;
    resetCostTracking(): void;
    getWakeWordStats(): {
        enabled: boolean;
        costOptimization: boolean;
        confidenceThreshold: number;
        supportedKeywords: number;
    };
    healthCheck(): Promise<{
        status: 'healthy' | 'degraded' | 'unhealthy';
        services: {
            voiceListener: boolean;
            wakeWordDetection: boolean;
            speechRecognition: boolean;
        };
        stats: any;
        costOptimization: {
            wakeWordFirst: boolean;
            costTracking: any;
            wakeWordStats: any;
        };
    }>;
    private playTTSResponse;
    speakResponse(guildId: string, context: any): Promise<void>;
}
//# sourceMappingURL=VoiceCommandHandler.d.ts.map