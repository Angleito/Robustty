"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AudioProcessingService = void 0;
var stream_1 = require("stream");
var logger_1 = require("./logger");
var AudioProcessingService = /** @class */ (function () {
    function AudioProcessingService() {
    }
    AudioProcessingService.createWavHeader = function (dataSize, sampleRate, channels, bitsPerSample) {
        if (sampleRate === void 0) { sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE; }
        if (channels === void 0) { channels = AudioProcessingService.DEFAULT_CHANNELS; }
        if (bitsPerSample === void 0) { bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE; }
        var startTime = Date.now();
        var header = Buffer.alloc(44);
        var byteRate = sampleRate * channels * (bitsPerSample / 8);
        var blockAlign = channels * (bitsPerSample / 8);
        // RIFF header
        header.write('RIFF', 0);
        header.writeUInt32LE(36 + dataSize, 4);
        header.write('WAVE', 8);
        // fmt subchunk
        header.write('fmt ', 12);
        header.writeUInt32LE(16, 16);
        header.writeUInt16LE(1, 20); // PCM format
        header.writeUInt16LE(channels, 22);
        header.writeUInt32LE(sampleRate, 24);
        header.writeUInt32LE(byteRate, 28);
        header.writeUInt16LE(blockAlign, 32);
        header.writeUInt16LE(bitsPerSample, 34);
        // data subchunk
        header.write('data', 36);
        header.writeUInt32LE(dataSize, 40);
        logger_1.logger.debug("[AudioProcessing] WAV header created: ".concat(sampleRate, "Hz, ").concat(channels, "ch, ").concat(bitsPerSample, "bit, dataSize: ").concat(dataSize, "B, time: ").concat(Date.now() - startTime, "ms"));
        return header;
    };
    AudioProcessingService.pcmToWav = function (pcmBuffer, sampleRate, channels, bitsPerSample) {
        if (sampleRate === void 0) { sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE; }
        if (channels === void 0) { channels = AudioProcessingService.DEFAULT_CHANNELS; }
        if (bitsPerSample === void 0) { bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE; }
        var startTime = Date.now();
        var inputSize = pcmBuffer.length;
        logger_1.logger.info("[AudioProcessing] PCM to WAV conversion started: input ".concat(inputSize, "B, ").concat(sampleRate, "Hz, ").concat(channels, "ch, ").concat(bitsPerSample, "bit"));
        var header = AudioProcessingService.createWavHeader(pcmBuffer.length, sampleRate, channels, bitsPerSample);
        var wavBuffer = Buffer.concat([header, pcmBuffer]);
        var outputSize = wavBuffer.length;
        logger_1.logger.info("[AudioProcessing] PCM to WAV conversion complete: ".concat(inputSize, "B \u2192 ").concat(outputSize, "B (header: 44B), time: ").concat(Date.now() - startTime, "ms"));
        return wavBuffer;
    };
    AudioProcessingService.createPcmToWavTransform = function (sampleRate, channels, bitsPerSample) {
        if (sampleRate === void 0) { sampleRate = AudioProcessingService.DEFAULT_SAMPLE_RATE; }
        if (channels === void 0) { channels = AudioProcessingService.DEFAULT_CHANNELS; }
        if (bitsPerSample === void 0) { bitsPerSample = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE; }
        var headerWritten = false;
        var totalDataSize = 0;
        var chunkCount = 0;
        var startTime = Date.now();
        logger_1.logger.debug("[AudioProcessing] PCM to WAV transform created: ".concat(sampleRate, "Hz, ").concat(channels, "ch, ").concat(bitsPerSample, "bit"));
        return new stream_1.Transform({
            transform: function (chunk, encoding, callback) {
                if (!headerWritten) {
                    // Write temporary header (will be updated on end)
                    var tempHeader = AudioProcessingService.createWavHeader(0, sampleRate, channels, bitsPerSample);
                    this.push(tempHeader);
                    headerWritten = true;
                    logger_1.logger.debug("[AudioProcessing] WAV header written to stream");
                }
                chunkCount++;
                totalDataSize += chunk.length;
                logger_1.logger.debug("[AudioProcessing] Processing chunk #".concat(chunkCount, ": ").concat(chunk.length, "B, total: ").concat(totalDataSize, "B"));
                this.push(chunk);
                callback();
            },
            flush: function (callback) {
                // Update header with actual data size
                var finalHeader = AudioProcessingService.createWavHeader(totalDataSize, sampleRate, channels, bitsPerSample);
                var duration = (totalDataSize / (sampleRate * channels * (bitsPerSample / 8))) * 1000;
                logger_1.logger.info("[AudioProcessing] WAV stream complete: ".concat(totalDataSize, "B, ").concat(chunkCount, " chunks, ").concat(duration.toFixed(1), "ms audio, process time: ").concat(Date.now() - startTime, "ms"));
                callback();
            }
        });
    };
    AudioProcessingService.normalizeAudioLevel = function (buffer, targetLevel) {
        if (targetLevel === void 0) { targetLevel = 0.8; }
        var startTime = Date.now();
        var inputSize = buffer.length;
        var samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        logger_1.logger.debug("[AudioProcessing] Normalizing audio: input ".concat(inputSize, "B, ").concat(samples.length, " samples, target level: ").concat(targetLevel));
        // Find peak amplitude
        var peak = 0;
        for (var i = 0; i < samples.length; i++) {
            peak = Math.max(peak, Math.abs(samples[i]));
        }
        if (peak === 0) {
            logger_1.logger.warn("[AudioProcessing] Audio is silent (peak=0), skipping normalization");
            return buffer; // Silence, no normalization needed
        }
        // Calculate scaling factor
        var scale = (targetLevel * 32767) / peak;
        var peakDb = 20 * Math.log10(peak / 32767);
        var gainDb = 20 * Math.log10(scale);
        logger_1.logger.info("[AudioProcessing] Peak: ".concat(peak, " (").concat(peakDb.toFixed(1), "dB), Scale: ").concat(scale.toFixed(3), " (").concat(gainDb.toFixed(1), "dB gain)"));
        // Apply scaling
        var normalizedSamples = new Int16Array(samples.length);
        var clippedSamples = 0;
        for (var i = 0; i < samples.length; i++) {
            var scaled = samples[i] * scale;
            if (scaled > 32767 || scaled < -32768) {
                clippedSamples++;
            }
            normalizedSamples[i] = Math.max(-32768, Math.min(32767, scaled));
        }
        if (clippedSamples > 0) {
            logger_1.logger.warn("[AudioProcessing] Clipping detected: ".concat(clippedSamples, " samples (").concat((clippedSamples / samples.length * 100).toFixed(2), "%)"));
        }
        var outputBuffer = Buffer.from(normalizedSamples.buffer);
        logger_1.logger.info("[AudioProcessing] Normalization complete: ".concat(inputSize, "B \u2192 ").concat(outputBuffer.length, "B, time: ").concat(Date.now() - startTime, "ms"));
        return outputBuffer;
    };
    AudioProcessingService.removeNoise = function (buffer, threshold) {
        if (threshold === void 0) { threshold = 1000; }
        var startTime = Date.now();
        var inputSize = buffer.length;
        var samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        var filteredSamples = new Int16Array(samples.length);
        var thresholdDb = 20 * Math.log10(threshold / 32767);
        logger_1.logger.debug("[AudioProcessing] Noise reduction started: input ".concat(inputSize, "B, threshold: ").concat(threshold, " (").concat(thresholdDb.toFixed(1), "dB)"));
        var gatedSamples = 0;
        var maxGatedValue = 0;
        for (var i = 0; i < samples.length; i++) {
            // Simple noise gate - zero out samples below threshold
            if (Math.abs(samples[i]) > threshold) {
                filteredSamples[i] = samples[i];
            }
            else {
                filteredSamples[i] = 0;
                gatedSamples++;
                maxGatedValue = Math.max(maxGatedValue, Math.abs(samples[i]));
            }
        }
        var gatedPercent = (gatedSamples / samples.length * 100).toFixed(2);
        var maxGatedDb = maxGatedValue > 0 ? 20 * Math.log10(maxGatedValue / 32767) : -Infinity;
        logger_1.logger.info("[AudioProcessing] Noise reduction complete: ".concat(gatedSamples, " samples gated (").concat(gatedPercent, "%), max gated: ").concat(maxGatedValue, " (").concat(maxGatedDb.toFixed(1), "dB), time: ").concat(Date.now() - startTime, "ms"));
        return Buffer.from(filteredSamples.buffer);
    };
    AudioProcessingService.calculateAudioLevel = function (buffer) {
        var startTime = Date.now();
        var samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        var sum = 0;
        var peak = 0;
        var rmsSum = 0;
        for (var i = 0; i < samples.length; i++) {
            var abs = Math.abs(samples[i]);
            sum += abs;
            peak = Math.max(peak, abs);
            rmsSum += samples[i] * samples[i];
        }
        var avgLevel = sum / samples.length / 32767; // Normalize to 0-1 range
        var peakLevel = peak / 32767;
        var rmsLevel = Math.sqrt(rmsSum / samples.length) / 32767;
        var avgDb = avgLevel > 0 ? 20 * Math.log10(avgLevel) : -Infinity;
        var peakDb = peakLevel > 0 ? 20 * Math.log10(peakLevel) : -Infinity;
        var rmsDb = rmsLevel > 0 ? 20 * Math.log10(rmsLevel) : -Infinity;
        logger_1.logger.debug("[AudioProcessing] Audio level: avg=".concat(avgLevel.toFixed(4), " (").concat(avgDb.toFixed(1), "dB), peak=").concat(peakLevel.toFixed(4), " (").concat(peakDb.toFixed(1), "dB), RMS=").concat(rmsLevel.toFixed(4), " (").concat(rmsDb.toFixed(1), "dB), ").concat(samples.length, " samples, time: ").concat(Date.now() - startTime, "ms"));
        return avgLevel;
    };
    AudioProcessingService.detectSilence = function (buffer, threshold) {
        if (threshold === void 0) { threshold = 0.01; }
        var startTime = Date.now();
        var level = AudioProcessingService.calculateAudioLevel(buffer);
        var isSilent = level < threshold;
        logger_1.logger.debug("[AudioProcessing] Silence detection: level=".concat(level.toFixed(4), ", threshold=").concat(threshold, ", silent=").concat(isSilent, ", time: ").concat(Date.now() - startTime, "ms"));
        return isSilent;
    };
    AudioProcessingService.trimSilence = function (buffer, threshold) {
        if (threshold === void 0) { threshold = 0.01; }
        var startTime = Date.now();
        var inputSize = buffer.length;
        var samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
        var silenceThreshold = threshold * 32767;
        logger_1.logger.debug("[AudioProcessing] Trimming silence: input ".concat(inputSize, "B, threshold: ").concat(threshold, " (").concat(silenceThreshold.toFixed(0), " raw)"));
        var start = 0;
        var end = samples.length - 1;
        // Find start of audio
        while (start < samples.length && Math.abs(samples[start]) < silenceThreshold) {
            start++;
        }
        // Find end of audio
        while (end > start && Math.abs(samples[end]) < silenceThreshold) {
            end--;
        }
        if (start >= end) {
            logger_1.logger.warn("[AudioProcessing] Buffer is all silence, returning empty buffer");
            return Buffer.alloc(0); // All silence
        }
        var trimmedSamples = samples.slice(start, end + 1);
        var outputBuffer = Buffer.from(trimmedSamples.buffer);
        var trimmedStart = (start / samples.length * 100).toFixed(1);
        var trimmedEnd = ((samples.length - 1 - end) / samples.length * 100).toFixed(1);
        var sizeReduction = ((1 - outputBuffer.length / inputSize) * 100).toFixed(1);
        logger_1.logger.info("[AudioProcessing] Silence trimmed: ".concat(inputSize, "B \u2192 ").concat(outputBuffer.length, "B (").concat(sizeReduction, "% reduction), trimmed ").concat(trimmedStart, "% from start, ").concat(trimmedEnd, "% from end, time: ").concat(Date.now() - startTime, "ms"));
        return outputBuffer;
    };
    AudioProcessingService.DEFAULT_SAMPLE_RATE = 48000;
    AudioProcessingService.DEFAULT_CHANNELS = 2;
    AudioProcessingService.DEFAULT_BITS_PER_SAMPLE = 16;
    return AudioProcessingService;
}());
exports.AudioProcessingService = AudioProcessingService;
