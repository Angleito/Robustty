"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const MusicBot_1 = require("./bot/MusicBot");
const logger_1 = require("./services/logger");
const HealthCheck_1 = require("./api/HealthCheck");
function validateEnvironment() {
    const required = [
        'DISCORD_TOKEN',
        'DISCORD_CLIENT_ID',
        'NEKO_PASSWORD'
    ];
    const missing = required.filter(env => !process.env[env]);
    if (missing.length > 0) {
        logger_1.logger.error(`Missing required environment variables: ${missing.join(', ')}`);
        process.exit(1);
    }
    logger_1.logger.info('Environment validation passed');
}
async function main() {
    try {
        validateEnvironment();
        const bot = new MusicBot_1.MusicBot();
        await bot.initialize();
        await bot.start();
        (0, HealthCheck_1.createHealthCheckServer)(bot.getClient());
        logger_1.logger.info('Music bot started successfully');
    }
    catch (error) {
        logger_1.logger.error('Failed to start bot:', error);
        process.exit(1);
    }
}
process.on('unhandledRejection', (error) => {
    logger_1.logger.error('Unhandled rejection:', error);
});
process.on('uncaughtException', (error) => {
    logger_1.logger.error('Uncaught exception:', error);
    process.exit(1);
});
main();
//# sourceMappingURL=index.js.map