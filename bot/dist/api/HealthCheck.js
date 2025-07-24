"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createHealthCheckServer = createHealthCheckServer;
const express_1 = __importDefault(require("express"));
const logger_1 = require("../services/logger");
function createHealthCheckServer(client, port = 8080) {
    const app = (0, express_1.default)();
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
        logger_1.logger.info(`Health check server listening on port ${port}`);
    });
    return server;
}
//# sourceMappingURL=HealthCheck.js.map