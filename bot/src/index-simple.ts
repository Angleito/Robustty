import 'dotenv/config';
import { Client, GatewayIntentBits } from 'discord.js';
import { logger } from './services/logger';
import { createHealthCheckServer } from './api/HealthCheck';

async function main() {
  try {
    logger.info('Starting Discord bot...');
    
    const client = new Client({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildVoiceStates
      ]
    });

    client.on('ready', () => {
      logger.info(`Bot logged in as ${client.user?.tag}`);
    });

    // Start health check server
    createHealthCheckServer(client);
    
    // Attempt to login (will fail with test token but that's ok)
    await client.login(process.env.DISCORD_TOKEN).catch(err => {
      logger.error('Failed to login to Discord:', err.message);
      logger.info('Bot will continue running for testing purposes');
    });
    
    logger.info('Bot initialization complete');
  } catch (error) {
    logger.error('Failed to start bot:', error);
  }
}

main();