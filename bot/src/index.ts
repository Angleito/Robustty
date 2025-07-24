import 'dotenv/config';
import { MusicBot } from './bot/MusicBot';
import { logger } from './services/logger';
import { createHealthCheckServer } from './api/HealthCheck';

function validateEnvironment() {
  const required = [
    'DISCORD_TOKEN',
    'DISCORD_CLIENT_ID', 
    'NEKO_PASSWORD'
  ];
  
  const missing = required.filter(env => !process.env[env]);
  
  if (missing.length > 0) {
    logger.error(`Missing required environment variables: ${missing.join(', ')}`);
    process.exit(1);
  }
  
  logger.info('Environment validation passed');
}

async function main() {
  try {
    // Validate environment variables first
    validateEnvironment();
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