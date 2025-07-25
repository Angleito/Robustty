import { SpeechRecognitionResult } from '../domain/types';
export declare class SpeechRecognitionService {
    private openai;
    private isEnabled;
    private costTracker;
    constructor();
    transcribeAudio(audioBuffer: Buffer, language?: string): Promise<SpeechRecognitionResult>;
    transcribeAudioStream(audioBuffer: Buffer): Promise<SpeechRecognitionResult>;
    isServiceEnabled(): boolean;
    parseVoiceCommand(transcriptionText: string): {
        command: string;
        parameters: string[];
    };
    getCostStats(): {
        totalRequests: number;
        totalMinutesProcessed: number;
        estimatedCost: number;
        averageCostPerRequest: number;
        lastRequestTime: number;
        successfulTranscriptions: number;
        failedTranscriptions: number;
        successRate: number;
        averageResponseTimeMs: number;
        sessionDurationMinutes: number;
    };
    resetCostTracking(): void;
    logCostSummary(): void;
}
//# sourceMappingURL=SpeechRecognitionService.d.ts.map