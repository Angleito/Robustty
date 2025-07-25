import { WakeWordResult } from '../domain/types';
interface AudioPattern {
    pattern: number[];
    threshold: number;
    minLength: number;
    maxLength: number;
}
export declare class WakeWordDetectionService {
    private wakeWordPatterns;
    private confidenceThreshold;
    private readonly sampleRate;
    private processingEnabled;
    private costOptimizationMode;
    constructor(confidenceThreshold?: number, sampleRate?: number);
    private initializeKanyePatterns;
    detectWakeWord(audioBuffer: Buffer, keyword?: string): Promise<WakeWordResult>;
    private costOptimizedPreprocessing;
    private fastAnalyzeAudioPatterns;
    private fastEnergyEnvelope;
    private fastMatchPattern;
    private preprocessAudio;
    private analyzeAudioPatterns;
    private calculateEnergyEnvelope;
    private matchPattern;
    private createNegativeResult;
    updateConfidenceThreshold(newThreshold: number): void;
    addCustomPattern(keyword: string, patterns: AudioPattern[]): void;
    getSupportedKeywords(): string[];
    enableProcessing(): void;
    disableProcessing(): void;
    setCostOptimizationMode(enabled: boolean): void;
    getProcessingStats(): {
        enabled: boolean;
        costOptimization: boolean;
        confidenceThreshold: number;
        supportedKeywords: number;
    };
}
export {};
//# sourceMappingURL=WakeWordDetectionService.d.ts.map