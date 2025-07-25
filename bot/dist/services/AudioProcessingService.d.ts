import { Transform } from 'stream';
export declare class AudioProcessingService {
    private static readonly DEFAULT_SAMPLE_RATE;
    private static readonly DEFAULT_CHANNELS;
    private static readonly DEFAULT_BITS_PER_SAMPLE;
    static createWavHeader(dataSize: number, sampleRate?: number, channels?: number, bitsPerSample?: number): Buffer;
    static pcmToWav(pcmBuffer: Buffer, sampleRate?: number, channels?: number, bitsPerSample?: number): Buffer;
    static createPcmToWavTransform(sampleRate?: number, channels?: number, bitsPerSample?: number): Transform;
    static normalizeAudioLevel(buffer: Buffer, targetLevel?: number): Buffer;
    static removeNoise(buffer: Buffer, threshold?: number): Buffer;
    static calculateAudioLevel(buffer: Buffer): number;
    static detectSilence(buffer: Buffer, threshold?: number): boolean;
    static trimSilence(buffer: Buffer, threshold?: number): Buffer;
}
//# sourceMappingURL=AudioProcessingService.d.ts.map