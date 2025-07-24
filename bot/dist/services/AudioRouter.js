"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AudioRouter = void 0;
const stream_1 = require("stream");
const logger_1 = require("./logger");
class AudioRouter {
    audioServiceUrl;
    constructor() {
        this.audioServiceUrl = process.env.AUDIO_SERVICE_URL || 'http://localhost:3000';
    }
    async captureStream(instanceId) {
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
            const reader = response.body.getReader();
            return new stream_1.Readable({
                async read() {
                    try {
                        const { done, value } = await reader.read();
                        if (done) {
                            this.push(null);
                        }
                        else {
                            this.push(Buffer.from(value));
                        }
                    }
                    catch (error) {
                        logger_1.logger.error('Error reading audio stream:', error);
                        this.destroy(error);
                    }
                }
            });
        }
        catch (error) {
            logger_1.logger.error(`Failed to capture audio from instance ${instanceId}:`, error);
            throw error;
        }
    }
    async stopCapture(instanceId) {
        try {
            await fetch(`${this.audioServiceUrl}/capture/${instanceId}`, {
                method: 'DELETE'
            });
        }
        catch (error) {
            logger_1.logger.error(`Failed to stop audio capture for ${instanceId}:`, error);
        }
    }
    async getActiveStreams() {
        try {
            const response = await fetch(`${this.audioServiceUrl}/streams`);
            const data = await response.json();
            return data.activeStreams || [];
        }
        catch (error) {
            logger_1.logger.error('Failed to get active streams:', error);
            return [];
        }
    }
}
exports.AudioRouter = AudioRouter;
//# sourceMappingURL=AudioRouter.js.map