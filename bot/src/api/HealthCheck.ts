import express from 'express';
import { Client } from 'discord.js';
import { logger } from '../services/logger';

export function createHealthCheckServer(client: Client, port: number = 8080) {
  const app = express();

  app.get('/health', (req, res) => {
    const status = {
      status: client.ws.status === 0 ? 'healthy' : 'unhealthy',
      uptime: process.uptime(),
      timestamp: new Date().toISOString(),
      discord: {
        connected: client.ws.status === 0,
        ping: client.ws.ping,
        guilds: client.guilds.cache.size
      }
    };

    const httpStatus = status.status === 'healthy' ? 200 : 503;
    res.status(httpStatus).json(status);
  });

  app.get('/ready', (req, res) => {
    const ready = client.isReady();
    res.status(ready ? 200 : 503).json({ ready });
  });

  const server = app.listen(port, () => {
    logger.info(`Health check server listening on port ${port}`);
  });

  return server;
}