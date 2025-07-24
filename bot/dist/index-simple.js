"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const discord_js_1 = require("discord.js");
const logger_1 = require("./services/logger");
const HealthCheck_1 = require("./api/HealthCheck");
async function main() {
    try {
        logger_1.logger.info('Starting Discord bot...');
        const client = new discord_js_1.Client({
            intents: [
                discord_js_1.GatewayIntentBits.Guilds,
                discord_js_1.GatewayIntentBits.GuildVoiceStates
            ]
        });
        client.on('ready', () => {
            logger_1.logger.info(`Bot logged in as ${client.user?.tag}`);
        });
        (0, HealthCheck_1.createHealthCheckServer)(client);
        await client.login(process.env.DISCORD_TOKEN).catch(err => {
            logger_1.logger.error('Failed to login to Discord:', err.message);
            logger_1.logger.info('Bot will continue running for testing purposes');
        });
        logger_1.logger.info('Bot initialization complete');
    }
    catch (error) {
        logger_1.logger.error('Failed to start bot:', error);
    }
}
main();
//# sourceMappingURL=index-simple.js.map