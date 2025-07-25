import { Readable } from 'stream';
export interface TTSConfig {
    apiKey?: string;
    voiceId?: string;
    modelId?: string;
    enabled?: boolean;
}
export declare class TextToSpeechService {
    private client;
    private voiceId;
    private modelId;
    private enabled;
    constructor(config?: TTSConfig);
    isEnabled(): boolean;
    generateSpeech(text: string): Promise<Readable | null>;
    preloadVoice(): Promise<void>;
    getAvailableVoices(): Promise<any[]>;
    setVoice(voiceId: string): void;
    setEnabled(enabled: boolean): void;
}
//# sourceMappingURL=TextToSpeechService.d.ts.map