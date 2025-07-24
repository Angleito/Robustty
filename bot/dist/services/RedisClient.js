"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.RedisClient = void 0;
const ioredis_1 = __importDefault(require("ioredis"));
const logger_1 = require("./logger");
class RedisClient {
    client;
    constructor() {
        this.client = new ioredis_1.default(process.env.REDIS_URL || 'redis://localhost:6379', {
            maxRetriesPerRequest: 3,
            retryStrategy: (times) => {
                const delay = Math.min(times * 50, 2000);
                return delay;
            }
        });
        this.client.on('error', (error) => {
            logger_1.logger.error('Redis error:', error);
        });
        this.client.on('connect', () => {
            logger_1.logger.info('Connected to Redis');
        });
    }
    async connect() {
        await this.client.ping();
    }
    async get(key) {
        return this.client.get(key);
    }
    async set(key, value, expiresIn) {
        if (expiresIn) {
            await this.client.set(key, value, 'EX', expiresIn);
        }
        else {
            await this.client.set(key, value);
        }
    }
    async del(key) {
        await this.client.del(key);
    }
    async exists(key) {
        return (await this.client.exists(key)) === 1;
    }
    async hset(key, field, value) {
        await this.client.hset(key, field, value);
    }
    async hget(key, field) {
        return this.client.hget(key, field);
    }
    async hgetall(key) {
        return this.client.hgetall(key);
    }
    async sadd(key, ...members) {
        await this.client.sadd(key, ...members);
    }
    async smembers(key) {
        return this.client.smembers(key);
    }
    async srem(key, ...members) {
        await this.client.srem(key, ...members);
    }
    getClient() {
        return this.client;
    }
    getBullMQConnection() {
        return new ioredis_1.default(process.env.REDIS_URL || 'redis://localhost:6379', {
            maxRetriesPerRequest: null,
            retryStrategy: (times) => {
                const delay = Math.min(times * 50, 2000);
                return delay;
            }
        });
    }
    async disconnect() {
        await this.client.quit();
    }
}
exports.RedisClient = RedisClient;
//# sourceMappingURL=RedisClient.js.map