import { Transform } from 'stream';
import { logger } from './logger';

interface WavHeader {
  chunkSize: number;
  subchunk1Size: number;
  audioFormat: number;
  numChannels: number;
  sampleRate: number;
  byteRate: number;
  blockAlign: number;
  bitsPerSample: number;
  subchunk2Size: number;
}

export class AudioProcessingService {
  private static readonly DEFAULT_SAMPLE_RATE = 48000;
  private static readonly DEFAULT_CHANNELS = 2;
  private static readonly DEFAULT_BITS_PER_SAMPLE = 16;

  static createWavHeader(
    dataSize: number,
    sampleRate: number = AudioProcessingService.DEFAULT_SAMPLE_RATE,
    channels: number = AudioProcessingService.DEFAULT_CHANNELS,
    bitsPerSample: number = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE
  ): Buffer {
    const header = Buffer.alloc(44);
    const byteRate = sampleRate * channels * (bitsPerSample / 8);
    const blockAlign = channels * (bitsPerSample / 8);

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

    return header;
  }

  static pcmToWav(
    pcmBuffer: Buffer,
    sampleRate: number = AudioProcessingService.DEFAULT_SAMPLE_RATE,
    channels: number = AudioProcessingService.DEFAULT_CHANNELS,
    bitsPerSample: number = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE
  ): Buffer {
    const header = AudioProcessingService.createWavHeader(
      pcmBuffer.length,
      sampleRate,
      channels,
      bitsPerSample
    );
    
    return Buffer.concat([header, pcmBuffer]);
  }

  static createPcmToWavTransform(
    sampleRate: number = AudioProcessingService.DEFAULT_SAMPLE_RATE,
    channels: number = AudioProcessingService.DEFAULT_CHANNELS,
    bitsPerSample: number = AudioProcessingService.DEFAULT_BITS_PER_SAMPLE
  ): Transform {
    let headerWritten = false;
    let totalDataSize = 0;

    return new Transform({
      transform(chunk: Buffer, encoding, callback) {
        if (!headerWritten) {
          // Write temporary header (will be updated on end)
          const tempHeader = AudioProcessingService.createWavHeader(
            0,
            sampleRate,
            channels,
            bitsPerSample
          );
          this.push(tempHeader);
          headerWritten = true;
        }

        totalDataSize += chunk.length;
        this.push(chunk);
        callback();
      },

      flush(callback) {
        // Update header with actual data size
        const finalHeader = AudioProcessingService.createWavHeader(
          totalDataSize,
          sampleRate,
          channels,
          bitsPerSample
        );
        
        logger.info(`[AudioProcessingService] Created WAV file with ${totalDataSize} bytes of audio data`);
        callback();
      }
    });
  }

  static normalizeAudioLevel(buffer: Buffer, targetLevel: number = 0.8): Buffer {
    const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
    
    // Find peak amplitude
    let peak = 0;
    for (let i = 0; i < samples.length; i++) {
      peak = Math.max(peak, Math.abs(samples[i]));
    }
    
    if (peak === 0) {
      return buffer; // Silence, no normalization needed
    }
    
    // Calculate scaling factor
    const scale = (targetLevel * 32767) / peak;
    
    // Apply scaling
    const normalizedSamples = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      normalizedSamples[i] = Math.max(-32768, Math.min(32767, samples[i] * scale));
    }
    
    return Buffer.from(normalizedSamples.buffer);
  }

  static removeNoise(buffer: Buffer, threshold: number = 1000): Buffer {
    const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
    const filteredSamples = new Int16Array(samples.length);
    
    for (let i = 0; i < samples.length; i++) {
      // Simple noise gate - zero out samples below threshold
      filteredSamples[i] = Math.abs(samples[i]) > threshold ? samples[i] : 0;
    }
    
    return Buffer.from(filteredSamples.buffer);
  }

  static calculateAudioLevel(buffer: Buffer): number {
    const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
    
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += Math.abs(samples[i]);
    }
    
    return sum / samples.length / 32767; // Normalize to 0-1 range
  }

  static detectSilence(buffer: Buffer, threshold: number = 0.01): boolean {
    const level = AudioProcessingService.calculateAudioLevel(buffer);
    return level < threshold;
  }

  static trimSilence(buffer: Buffer, threshold: number = 0.01): Buffer {
    const samples = new Int16Array(buffer.buffer, buffer.byteOffset, buffer.length / 2);
    const silenceThreshold = threshold * 32767;
    
    let start = 0;
    let end = samples.length - 1;
    
    // Find start of audio
    while (start < samples.length && Math.abs(samples[start]) < silenceThreshold) {
      start++;
    }
    
    // Find end of audio
    while (end > start && Math.abs(samples[end]) < silenceThreshold) {
      end--;
    }
    
    if (start >= end) {
      return Buffer.alloc(0); // All silence
    }
    
    const trimmedSamples = samples.slice(start, end + 1);
    return Buffer.from(trimmedSamples.buffer);
  }
}