import { Readable } from 'stream';
import { logger } from './logger';

export class AudioRouter {
  private audioServiceUrl: string;

  constructor() {
    this.audioServiceUrl = process.env.AUDIO_SERVICE_URL || 'http://localhost:3000';
  }

  async captureStream(instanceId: string): Promise<Readable> {
    try {
      const response = await fetch(`${this.audioServiceUrl}/capture/${instanceId}`, {
        method: 'GET',
        headers: {
          'Accept': 'audio/opus'
        }
      });

      if (!response.ok) {
        throw new Error(`Audio capture failed: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('No audio stream received');
      }

      // Convert Web Stream to Node.js Readable
      const reader = response.body.getReader();
      
      const stream = new Readable({
        async read() {
          try {
            const { done, value } = await reader.read();
            
            if (done) {
              this.push(null);
            } else {
              this.push(Buffer.from(value));
            }
          } catch (error) {
            logger.error('Error reading audio stream:', error);
            this.destroy(error as Error);
          }
        }
      });

      // Add timeout and cleanup handling
      const timeout = setTimeout(() => {
        logger.warn(`Audio stream timeout for instance ${instanceId}`);
        stream.destroy(new Error('Stream timeout'));
      }, 60000); // 60 second timeout

      stream.on('close', () => {
        clearTimeout(timeout);
        reader.releaseLock();
      });

      stream.on('error', () => {
        clearTimeout(timeout);
        reader.releaseLock();
      });

      return stream;
    } catch (error) {
      logger.error(`Failed to capture audio from instance ${instanceId}:`, error);
      throw error;
    }
  }

  async stopCapture(instanceId: string): Promise<void> {
    try {
      await fetch(`${this.audioServiceUrl}/capture/${instanceId}`, {
        method: 'DELETE'
      });
    } catch (error) {
      logger.error(`Failed to stop audio capture for ${instanceId}:`, error);
    }
  }

  async getActiveStreams(): Promise<string[]> {
    try {
      const response = await fetch(`${this.audioServiceUrl}/streams`);
      const data = await response.json() as { activeStreams?: string[] };
      return data.activeStreams || [];
    } catch (error) {
      logger.error('Failed to get active streams:', error);
      return [];
    }
  }
}