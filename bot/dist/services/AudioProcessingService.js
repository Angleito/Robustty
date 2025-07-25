"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AudioProcessingService = void 0;
const stream_1 = require("stream");
const logger_1 = require("./logger");
class AudioProcessingService {
    static DEFAULT_SAMPLE_RATE = 48000;
    static DEFAULT_CHANNELS = 2;
    static DEFAULT_BITS_PER_SAMPLE = 16;
    static createWavHeader(dataSize, sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE, channels = AudioProcessingService.DEFAULT_CHANNELS, bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE) {
        const header = Buffer.alloc(44);
        const byteRate = sampleRate * channels * (bitsPerSample / 8);
        const blockAlign = channels * (bitsPerSample / 8);
        header.write('RIFF', 0);
        header.writeUInt32LE(36 + dataSize, 4);
        header.write('WAVE', 8);
        header.write('fmt ', 12);
        header.writeUInt32LE(16, 16);
        header.writeUInt16LE(1, 20);
        header.writeUInt16LE(channels, 22);
        header.writeUInt32LE(sampleRate, 24);
        header.writeUInt32LE(byteRate, 28);
        header.writeUInt16LE(blockAlign, 32);
        header.writeUInt16LE(bitsPerSample, 34);
        header.write('data', 36);
        header.writeUInt32LE(dataSize, 40);
        return header;
    }
    static pcmToWav(pcmBuffer, sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE, channels = AudioProcessingService.DEFAULT_CHANNELS, bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE) {
        const header = AudioProcessingService.createWavHeader(pcmBuffer.length, sampleRate, channels, bitsPerSample);
        return Buffer.concat([header, pcmBuffer]);
    }
    static createPcmToWavTransform(sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE, channels = AudioProcessingService.DEFAULT_CHANNELS, bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE) {
        let headerWritten = false;
        let totalDataSize = 0;
        return new stream_1.Transform({
            transform(chunk, encoding, callback) {
                if (!headerWritten) {
                    const tempHeader = AudioProcessingService.createWavHeader(0, sampleRate, channels, bitsPerSample);
                    this.push(tempHeader);
                    headerWritten = true;
                }
                totalDataSize += chunk.length;
                this.push(chunk);
                callback();
            },
            flush(callback) {
                const finalHeader = AudioProcessingService.createWavHeader(totalDataSize, sampleRate, channels, bitsPerSample);
                logger_1.logger.info(`[AudioProcessingService] Created WAV file with ${totalDataSize} bytes of audio data`);
                callback();
            }
        });
    }
    static normalizeAudioLevel(buffer, targetLevel = 0.8) {
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        let peak = 0;
        for (let i = 0; i < samples.length; i++) {
            peak = Math.max(peak, Math.abs(samples[i]));
        }
        if (peak === 0) {
            return buffer;
        }
        const scale = (targetLevel * 32767) / peak;
        const normalizedSamples = new Int16Array(samples.length);
        for (let i = 0; i < samples.length; i++) {
            normalizedSamples[i] = Math.max(-32768, Math.min(32767, samples[i] * scale));
        }
        return Buffer.from(normalizedSamples.buffer);
    }
    static removeNoise(buffer, threshold = 1000) {
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        const filteredSamples = new Int16Array(samples.length);
        for (let i = 0; i < samples.length; i++) {
            filteredSamples[i] = Math.abs(samples[i]) > threshold ? samples[i] : 0;
        }
        return Buffer.from(filteredSamples.buffer);
    }
    static calculateAudioLevel(buffer) {
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        let sum = 0;
        for (let i = 0; i < samples.length; i++) {
            sum += Math.abs(samples[i]);
        }
        return sum / samples.length / 32767;
    }
    static detectSilence(buffer, threshold = 0.01) {
        const level = AudioProcessingService.calculateAudioLevel(buffer);
        return level < threshold;
    }
    static trimSilence(buffer, threshold = 0.01) {
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        const silenceThreshold = threshold * 32767;
        let start = 0;
        let end = samples.length - 1;
        while (start < samples.length && Math.abs(samples[start]) < silenceThreshold) {
            start++;
        }
        while (end > start && Math.abs(samples[end]) < silenceThreshold) {
            end--;
        }
        if (start >= end) {
            return Buffer.alloc(0);
        }
        const trimmedSamples = samples.slice(start, end + 1);
        return Buffer.from(trimmedSamples.buffer);
    }
}
exports.AudioProcessingService = AudioProcessingService;
//# sourceMappingURL=AudioProcessingService.js.map