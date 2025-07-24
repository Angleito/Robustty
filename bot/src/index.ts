import 'dotenv/config';
import { MusicBot } from './bot/MusicBot';
import { logger } from './services/logger';
import { createHealthCheckServer } from './api/HealthCheck';

async function main() {
  try {
    const bot = new MusicBot();
    await bot.initialize();
    await bot.start();
    
    // Start health check server
    createHealthCheckServer(bot.getClient());
    
    logger.info('Music bot started successfully');
  } catch (error) {
    logger.error('Failed to start bot:', error);
    process.exit(1);
  }
}

process.on('unhandledRejection', (error) => {
  logger.error('Unhandled rejection:', error);
});

process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception:', error);
  process.exit(1);
});

main();