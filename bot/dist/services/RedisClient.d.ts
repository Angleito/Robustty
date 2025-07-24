import Redis from 'ioredis';
export declare class RedisClient {
    private client;
    constructor();
    connect(): Promise<void>;
    get(key: string): Promise<string | null>;
    set(key: string, value: string, expiresIn?: number): Promise<void>;
    del(key: string): Promise<void>;
    exists(key: string): Promise<boolean>;
    hset(key: string, field: string, value: string): Promise<void>;
    hget(key: string, field: string): Promise<string | null>;
    hgetall(key: string): Promise<Record<string, string>>;
    sadd(key: string, ...members: string[]): Promise<void>;
    smembers(key: string): Promise<string[]>;
    srem(key: string, ...members: string[]): Promise<void>;
    getClient(): Redis;
    getBullMQConnection(): Redis;
    disconnect(): Promise<void>;
}
//# sourceMappingURL=RedisClient.d.ts.map