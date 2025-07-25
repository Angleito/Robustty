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
        const startTime = Date.now();
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
        logger_1.logger.debug(`[AudioProcessing] WAV header created: ${sampleRate}Hz, ${channels}ch, ${bitsPerSample}bit, dataSize: ${dataSize}B, time: ${Date.now() - startTime}ms`);
        return header;
    }
    static pcmToWav(pcmBuffer, sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE, channels = AudioProcessingService.DEFAULT_CHANNELS, bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE) {
        const startTime = Date.now();
        const inputSize = pcmBuffer.length;
        logger_1.logger.info(`[AudioProcessing] PCM to WAV conversion started: input ${inputSize}B, ${sampleRate}Hz, ${channels}ch, ${bitsPerSample}bit`);
        const header = AudioProcessingService.createWavHeader(pcmBuffer.length, sampleRate, channels, bitsPerSample);
        const wavBuffer = Buffer.concat([header, pcmBuffer]);
        const outputSize = wavBuffer.length;
        logger_1.logger.info(`[AudioProcessing] PCM to WAV conversion complete: ${inputSize}B → ${outputSize}B (header: 44B), time: ${Date.now() - startTime}ms`);
        return wavBuffer;
    }
    static createPcmToWavTransform(sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE, channels = AudioProcessingService.DEFAULT_CHANNELS, bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE) {
        let headerWritten = false;
        let totalDataSize = 0;
        let chunkCount = 0;
        const startTime = Date.now();
        logger_1.logger.debug(`[AudioProcessing] PCM to WAV transform created: ${sampleRate}Hz, ${channels}ch, ${bitsPerSample}bit`);
        return new stream_1.Transform({
            transform(chunk, encoding, callback) {
                if (!headerWritten) {
                    const tempHeader = AudioProcessingService.createWavHeader(0, sampleRate, channels, bitsPerSample);
                    this.push(tempHeader);
                    headerWritten = true;
                    logger_1.logger.debug(`[AudioProcessing] WAV header written to stream`);
                }
                chunkCount++;
                totalDataSize += chunk.length;
                logger_1.logger.debug(`[AudioProcessing] Processing chunk #${chunkCount}: ${chunk.length}B, total: ${totalDataSize}B`);
                this.push(chunk);
                callback();
            },
            flush(callback) {
                const finalHeader = AudioProcessingService.createWavHeader(totalDataSize, sampleRate, channels, bitsPerSample);
                const duration = (totalDataSize / (sampleRate * channels * (bitsPerSample / 8))) * 1000;
                logger_1.logger.info(`[AudioProcessing] WAV stream complete: ${totalDataSize}B, ${chunkCount} chunks, ${duration.toFixed(1)}ms audio, process time: ${Date.now() - startTime}ms`);
                callback();
            }
        });
    }
    static normalizeAudioLevel(buffer, targetLevel = 0.8) {
        const startTime = Date.now();
        const inputSize = buffer.length;
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        logger_1.logger.debug(`[AudioProcessing] Normalizing audio: input ${inputSize}B, ${samples.length} samples, target level: ${targetLevel}`);
        let peak = 0;
        for (let i = 0; i < samples.length; i++) {
            peak = Math.max(peak, Math.abs(samples[i]));
        }
        if (peak === 0) {
            logger_1.logger.warn(`[AudioProcessing] Audio is silent (peak=0), skipping normalization`);
            return buffer;
        }
        const scale = (targetLevel * 32767) / peak;
        const peakDb = 20 * Math.log10(peak / 32767);
        const gainDb = 20 * Math.log10(scale);
        logger_1.logger.info(`[AudioProcessing] Peak: ${peak} (${peakDb.toFixed(1)}dB), Scale: ${scale.toFixed(3)} (${gainDb.toFixed(1)}dB gain)`);
        const normalizedSamples = new Int16Array(samples.length);
        let clippedSamples = 0;
        for (let i = 0; i < samples.length; i++) {
            const scaled = samples[i] * scale;
            if (scaled > 32767 || scaled < -32768) {
                clippedSamples++;
            }
            normalizedSamples[i] = Math.max(-32768, Math.min(32767, scaled));
        }
        if (clippedSamples > 0) {
            logger_1.logger.warn(`[AudioProcessing] Clipping detected: ${clippedSamples} samples (${(clippedSamples / samples.length * 100).toFixed(2)}%)`);
        }
        const outputBuffer = Buffer.from(normalizedSamples.buffer);
        logger_1.logger.info(`[AudioProcessing] Normalization complete: ${inputSize}B → ${outputBuffer.length}B, time: ${Date.now() - startTime}ms`);
        return outputBuffer;
    }
    static removeNoise(buffer, threshold = 1000) {
        const startTime = Date.now();
        const inputSize = buffer.length;
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        const filteredSamples = new Int16Array(samples.length);
        const thresholdDb = 20 * Math.log10(threshold / 32767);
        logger_1.logger.debug(`[AudioProcessing] Noise reduction started: input ${inputSize}B, threshold: ${threshold} (${thresholdDb.toFixed(1)}dB)`);
        let gatedSamples = 0;
        let maxGatedValue = 0;
        for (let i = 0; i < samples.length; i++) {
            if (Math.abs(samples[i]) > threshold) {
                filteredSamples[i] = samples[i];
            }
            else {
                filteredSamples[i] = 0;
                gatedSamples++;
                maxGatedValue = Math.max(maxGatedValue, Math.abs(samples[i]));
            }
        }
        const gatedPercent = (gatedSamples / samples.length * 100).toFixed(2);
        const maxGatedDb = maxGatedValue > 0 ? 20 * Math.log10(maxGatedValue / 32767) : -Infinity;
        logger_1.logger.info(`[AudioProcessing] Noise reduction complete: ${gatedSamples} samples gated (${gatedPercent}%), max gated: ${maxGatedValue} (${maxGatedDb.toFixed(1)}dB), time: ${Date.now() - startTime}ms`);
        return Buffer.from(filteredSamples.buffer);
    }
    static calculateAudioLevel(buffer) {
        const startTime = Date.now();
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        let sum = 0;
        let peak = 0;
        let rmsSum = 0;
        for (let i = 0; i < samples.length; i++) {
            const abs = Math.abs(samples[i]);
            sum += abs;
            peak = Math.max(peak, abs);
            rmsSum += samples[i] * samples[i];
        }
        const avgLevel = sum / samples.length / 32767;
        const peakLevel = peak / 32767;
        const rmsLevel = Math.sqrt(rmsSum / samples.length) / 32767;
        const avgDb = avgLevel > 0 ? 20 * Math.log10(avgLevel) : -Infinity;
        const peakDb = peakLevel > 0 ? 20 * Math.log10(peakLevel) : -Infinity;
        const rmsDb = rmsLevel > 0 ? 20 * Math.log10(rmsLevel) : -Infinity;
        logger_1.logger.debug(`[AudioProcessing] Audio level: avg=${avgLevel.toFixed(4)} (${avgDb.toFixed(1)}dB), peak=${peakLevel.toFixed(4)} (${peakDb.toFixed(1)}dB), RMS=${rmsLevel.toFixed(4)} (${rmsDb.toFixed(1)}dB), ${samples.length} samples, time: ${Date.now() - startTime}ms`);
        return avgLevel;
    }
    static detectSilence(buffer, threshold = 0.01) {
        const startTime = Date.now();
        const level = AudioProcessingService.calculateAudioLevel(buffer);
        const isSilent = level < threshold;
        logger_1.logger.debug(`[AudioProcessing] Silence detection: level=${level.toFixed(4)}, threshold=${threshold}, silent=${isSilent}, time: ${Date.now() - startTime}ms`);
        return isSilent;
    }
    static trimSilence(buffer, threshold = 0.01) {
        const startTime = Date.now();
        const inputSize = buffer.length;
        const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        const silenceThreshold = threshold * 32767;
        logger_1.logger.debug(`[AudioProcessing] Trimming silence: input ${inputSize}B, threshold: ${threshold} (${silenceThreshold.toFixed(0)} raw)`);
        let start = 0;
        let end = samples.length - 1;
        while (start < samples.length && Math.abs(samples[start]) < silenceThreshold) {
            start++;
        }
        while (end > start && Math.abs(samples[end]) < silenceThreshold) {
            end--;
        }
        if (start >= end) {
            logger_1.logger.warn(`[AudioProcessing] Buffer is all silence, returning empty buffer`);
            return Buffer.alloc(0);
        }
        const trimmedSamples = samples.slice(start, end + 1);
        const outputBuffer = Buffer.from(trimmedSamples.buffer);
        const trimmedStart = (start / samples.length * 100).toFixed(1);
        const trimmedEnd = ((samples.length - 1 - end) / samples.length * 100).toFixed(1);
        const sizeReduction = ((1 - outputBuffer.length / inputSize) * 100).toFixed(1);
        logger_1.logger.info(`[AudioProcessing] Silence trimmed: ${inputSize}B → ${outputBuffer.length}B (${sizeReduction}% reduction), trimmed ${trimmedStart}% from start, ${trimmedEnd}% from end, time: ${Date.now() - startTime}ms`);
        return outputBuffer;
    }
}
exports.AudioProcessingService = AudioProcessingService;
//# sourceMappingURL=AudioProcessingService.js.map