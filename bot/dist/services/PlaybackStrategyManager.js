"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.PlaybackStrategyManager = void 0;
const ytdl_core_1 = __importDefault(require("@distube/ytdl-core"));
const playDl = __importStar(require("play-dl"));
const NekoPoolManager_1 = require("./NekoPoolManager");
const AudioRouter_1 = require("./AudioRouter");
const logger_1 = require("./logger");
class PlaybackStrategyManager {
    nekoPool;
    audioRouter;
    redis;
    failureCache = new Map();
    FAILURE_CACHE_TTL = 3600000;
    constructor(redis) {
        this.redis = redis;
        this.nekoPool = new NekoPoolManager_1.NekoPoolManager(redis);
        this.audioRouter = new AudioRouter_1.AudioRouter();
    }
    async attemptPlayback(video, voiceChannel) {
        const failureCount = await this.getFailureCount(video.id);
        const forceNeko = await this.redis.get(`video:force_neko:${video.id}`);
        if (forceNeko) {
            logger_1.logger.info(`Video ${video.id} marked for neko fallback due to previous errors`);
            return await this.nekoFallback(video);
        }
        if (failureCount > 2) {
            logger_1.logger.info(`Video ${video.id} has failed ${failureCount} times, using neko fallback`);
            return await this.nekoFallback(video);
        }
        try {
            const stream = await this.directStream(video.url);
            await this.clearFailure(video.id);
            return {
                method: 'direct',
                stream
            };
        }
        catch (error) {
            if (this.isBotDetectionError(error)) {
                logger_1.logger.warn(`Bot detection for video ${video.id}, falling back to neko`);
                await this.incrementFailure(video.id);
                return await this.nekoFallback(video);
            }
            throw error;
        }
    }
    async directStream(url) {
        let stream = null;
        try {
            if (ytdl_core_1.default.validateURL(url)) {
                const info = await ytdl_core_1.default.getInfo(url);
                if (info.videoDetails.isLiveContent) {
                    stream = (0, ytdl_core_1.default)(url, {
                        quality: 'highestaudio',
                        highWaterMark: 1 << 25,
                        dlChunkSize: 0
                    });
                }
                else {
                    stream = (0, ytdl_core_1.default)(url, {
                        filter: 'audioonly',
                        quality: 'highestaudio',
                        highWaterMark: 1 << 25
                    });
                }
                stream.on('error', (error) => {
                    logger_1.logger.error('YTDL stream error:', error);
                });
                return stream;
            }
        }
        catch (error) {
            logger_1.logger.warn('ytdl-core failed, trying play-dl:', error);
            if (stream) {
                stream.destroy();
            }
        }
        try {
            const result = await playDl.stream(url, {
                discordPlayerCompatibility: true
            });
            stream = result.stream;
            stream.on('error', (error) => {
                logger_1.logger.error('play-dl stream error:', error);
            });
            return stream;
        }
        catch (error) {
            logger_1.logger.error('Both ytdl-core and play-dl failed:', error);
            if (stream) {
                stream.destroy();
            }
            throw error;
        }
    }
    async nekoFallback(video) {
        const instance = await this.nekoPool.getHealthyInstance();
        if (!instance) {
            throw new Error('No healthy neko instances available');
        }
        await instance.playVideo(video.url);
        const stream = await this.audioRouter.captureStream(instance.id);
        await this.trackVideoHistory(video.id, 'neko');
        return {
            method: 'neko',
            stream
        };
    }
    isBotDetectionError(error) {
        const errorMessage = error?.message?.toLowerCase() || '';
        const botDetectionPhrases = [
            'sign in to confirm',
            'bot',
            'captcha',
            'verify',
            'age-restricted',
            'inappropriate',
            '429',
            'too many requests'
        ];
        return botDetectionPhrases.some(phrase => errorMessage.includes(phrase));
    }
    async getFailureCount(videoId) {
        const cached = this.failureCache.get(videoId);
        if (cached !== undefined)
            return cached;
        const stored = await this.redis.get(`failure:${videoId}`);
        return stored ? parseInt(stored) : 0;
    }
    async incrementFailure(videoId) {
        const current = await this.getFailureCount(videoId);
        const newCount = current + 1;
        this.failureCache.set(videoId, newCount);
        await this.redis.set(`failure:${videoId}`, newCount.toString(), this.FAILURE_CACHE_TTL / 1000);
        setTimeout(() => {
            this.failureCache.delete(videoId);
        }, this.FAILURE_CACHE_TTL);
    }
    async clearFailure(videoId) {
        this.failureCache.delete(videoId);
        await this.redis.del(`failure:${videoId}`);
    }
    async trackVideoHistory(videoId, method) {
        await this.redis.hset('video:history', videoId, method);
        await this.redis.sadd(`videos:${method}`, videoId);
    }
    async getStats() {
        const directVideos = await this.redis.smembers('videos:direct');
        const nekoVideos = await this.redis.smembers('videos:neko');
        return {
            direct: directVideos.length,
            neko: nekoVideos.length,
            recentFailures: this.failureCache.size
        };
    }
}
exports.PlaybackStrategyManager = PlaybackStrategyManager;
//# sourceMappingURL=PlaybackStrategyManager.js.map