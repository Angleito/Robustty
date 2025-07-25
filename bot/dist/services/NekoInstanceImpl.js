"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.NekoInstanceImpl = void 0;
const ws_1 = __importDefault(require("ws"));
const logger_1 = require("./logger");
const events_1 = require("events");
const EVENT = {
    SYSTEM: {
        INIT: 'system/init',
        DISCONNECT: 'system/disconnect',
        ERROR: 'system/error',
    },
    CLIENT: {
        HEARTBEAT: 'client/heartbeat',
    },
    SIGNAL: {
        OFFER: 'signal/offer',
        ANSWER: 'signal/answer',
        PROVIDE: 'signal/provide',
        CANDIDATE: 'signal/candidate',
    },
    MEMBER: {
        LIST: 'member/list',
        CONNECTED: 'member/connected',
        DISCONNECTED: 'member/disconnected',
    },
    CONTROL: {
        LOCKED: 'control/locked',
        RELEASE: 'control/release',
        REQUEST: 'control/request',
        REQUESTING: 'control/requesting',
        CLIPBOARD: 'control/clipboard',
        GIVE: 'control/give',
        KEYBOARD: 'control/keyboard',
    },
    SCREEN: {
        CONFIGURATIONS: 'screen/configurations',
        RESOLUTION: 'screen/resolution',
        SET: 'screen/set',
    },
    BROADCAST: {
        STATUS: 'broadcast/status',
        CREATE: 'broadcast/create',
        DESTROY: 'broadcast/destroy',
    },
    ADMIN: {
        BAN: 'admin/ban',
        KICK: 'admin/kick',
        LOCK: 'admin/lock',
        UNLOCK: 'admin/unlock',
        MUTE: 'admin/mute',
        UNMUTE: 'admin/unmute',
        CONTROL: 'admin/control',
        RELEASE: 'admin/release',
        GIVE: 'admin/give',
    },
};
class NekoInstanceImpl extends events_1.EventEmitter {
    id;
    isAuthenticated = false;
    currentVideo = null;
    ws;
    redis;
    lastUsed = 0;
    nekoUrl;
    nekoPassword;
    nekoUsername;
    reconnectTimer;
    reconnectAttempts = 0;
    maxReconnectAttempts = 5;
    reconnectDelay = 5000;
    pingInterval;
    heartbeatInterval;
    hasControl = false;
    sessionId;
    controlHost;
    constructor(id, redis) {
        super();
        this.id = id;
        this.redis = redis;
        this.nekoUrl = process.env.NEKO_INTERNAL_URL || 'http://neko:8080';
        this.nekoPassword = process.env.NEKO_PASSWORD || (() => {
            throw new Error('NEKO_PASSWORD environment variable is required');
        })();
        this.nekoUsername = process.env.NEKO_USERNAME || 'admin';
    }
    async initialize() {
        try {
            await this.connect();
        }
        catch (error) {
            logger_1.logger.error(`Failed to initialize neko instance ${this.id}:`, error);
            this.scheduleReconnect();
        }
    }
    async connect() {
        const wsUrl = this.nekoUrl.replace('http://', 'ws://').replace('https://', 'wss://');
        this.ws = new ws_1.default(`${wsUrl}/ws`);
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Connection timeout'));
            }, 10000);
            this.ws.on('open', () => {
                clearTimeout(timeout);
                logger_1.logger.info(`Connected to neko instance ${this.id}`);
                this.reconnectAttempts = 0;
                this.startPingInterval();
                resolve();
            });
            this.ws.on('error', (error) => {
                clearTimeout(timeout);
                logger_1.logger.error(`WebSocket error for ${this.id}:`, error);
                reject(error);
            });
            this.ws.on('close', (code, reason) => {
                logger_1.logger.warn(`WebSocket closed for ${this.id}:`, { code, reason: reason.toString() });
                this.isAuthenticated = false;
                this.hasControl = false;
                this.stopPingInterval();
                this.stopHeartbeat();
                this.scheduleReconnect();
            });
            this.ws.on('message', (data) => {
                this.handleMessage(data.toString());
            });
        });
    }
    async authenticate() {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Authentication timeout'));
            }, 5000);
            clearTimeout(timeout);
            this.isAuthenticated = true;
            logger_1.logger.info(`Authenticated to neko instance ${this.id} (simplified auth)`);
            resolve();
        });
    }
    handleMessage(message) {
        try {
            const data = JSON.parse(message);
            logger_1.logger.debug(`Received neko message for ${this.id}:`, { event: data.event });
            switch (data.event) {
                case EVENT.SYSTEM.INIT:
                    const initData = data;
                    this.sessionId = initData.session_id;
                    this.controlHost = initData.control_host;
                    logger_1.logger.info(`Neko session initialized for ${this.id}:`, {
                        sessionId: this.sessionId,
                        screenSize: initData.screen_size,
                        members: initData.members.length
                    });
                    this.startHeartbeat();
                    this.authenticate()
                        .catch(error => {
                        logger_1.logger.error(`Authentication failed for ${this.id}:`, error);
                        this.ws?.close();
                    });
                    break;
                case EVENT.MEMBER.CONNECTED:
                    logger_1.logger.debug(`Member connected to neko ${this.id}:`, data.id);
                    break;
                case EVENT.SYSTEM.ERROR:
                    logger_1.logger.error(`System error from neko ${this.id}:`, data);
                    break;
                case EVENT.CONTROL.LOCKED:
                    this.controlHost = data.id;
                    this.hasControl = data.id === this.sessionId;
                    logger_1.logger.debug(`Control status for ${this.id}:`, {
                        hasControl: this.hasControl,
                        controlHost: this.controlHost
                    });
                    this.emit('control', data);
                    break;
                case EVENT.CONTROL.RELEASE:
                    if (this.controlHost === data.id) {
                        this.controlHost = undefined;
                        this.hasControl = false;
                    }
                    this.emit('control', data);
                    break;
                case EVENT.SCREEN.RESOLUTION:
                    logger_1.logger.debug(`Screen resolution for ${this.id}:`, data);
                    break;
                case EVENT.MEMBER.LIST:
                    logger_1.logger.debug(`Member list for ${this.id}:`, data.members);
                    break;
                case EVENT.SYSTEM.DISCONNECT:
                    logger_1.logger.warn(`Disconnected from neko ${this.id}:`, data.message);
                    this.emit('auth', data);
                    this.ws?.close();
                    break;
                case EVENT.CONTROL.REQUESTING:
                    logger_1.logger.debug(`Control requested by ${data.id} for ${this.id}`);
                    break;
                default:
                    logger_1.logger.debug(`Unhandled neko event for ${this.id}:`, data.event);
            }
        }
        catch (error) {
            logger_1.logger.error(`Failed to parse neko message for ${this.id}:`, error);
        }
    }
    send(data) {
        if (this.ws?.readyState === ws_1.default.OPEN) {
            const message = JSON.stringify(data);
            logger_1.logger.debug(`Sending neko message for ${this.id}:`, { event: data.event });
            this.ws.send(message);
        }
        else {
            logger_1.logger.warn(`Cannot send message to neko ${this.id}: WebSocket not open`);
        }
    }
    async requestControl() {
        if (this.hasControl)
            return;
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Control request timeout'));
            }, 5000);
            const controlHandler = (message) => {
                if (message.event === EVENT.CONTROL.LOCKED && message.id === this.sessionId) {
                    clearTimeout(timeout);
                    this.hasControl = true;
                    this.controlHost = this.sessionId;
                    this.removeListener('control', controlHandler);
                    resolve();
                }
            };
            this.on('control', controlHandler);
            this.send({
                event: EVENT.CONTROL.REQUEST
            });
        });
    }
    async releaseControl() {
        if (!this.hasControl)
            return;
        this.send({
            event: EVENT.CONTROL.RELEASE
        });
        this.hasControl = false;
    }
    async sendMouseMove(x, y) {
        await this.requestControl();
        this.send({
            event: 'mousemove',
            x,
            y
        });
    }
    async sendMouseClick(x, y, button = 0) {
        await this.requestControl();
        this.send({
            event: 'mousedown',
            x,
            y,
            button
        });
        setTimeout(() => {
            this.send({
                event: 'mouseup',
                x,
                y,
                button
            });
        }, 50);
    }
    async sendKey(keysym, pressed = true) {
        await this.requestControl();
        this.send({
            event: pressed ? 'keydown' : 'keyup',
            keysym
        });
    }
    async sendText(text) {
        await this.requestControl();
        for (const char of text) {
            const keysym = char.charCodeAt(0);
            await this.sendKey(keysym, true);
            await this.sendKey(keysym, false);
            await new Promise(resolve => setTimeout(resolve, 10));
        }
    }
    async navigate(url) {
        await this.requestControl();
        await this.sendMouseClick(400, 50);
        await new Promise(resolve => setTimeout(resolve, 100));
        await this.sendKey(0xFFE3, true);
        await this.sendKey(0x0061, true);
        await this.sendKey(0x0061, false);
        await this.sendKey(0xFFE3, false);
        await new Promise(resolve => setTimeout(resolve, 100));
        await this.sendText(url);
        await new Promise(resolve => setTimeout(resolve, 100));
        await this.sendKey(0xFF0D, true);
        await this.sendKey(0xFF0D, false);
    }
    async playVideo(url) {
        this.currentVideo = url;
        this.lastUsed = Date.now();
        try {
            await this.navigate(url);
            await new Promise(resolve => setTimeout(resolve, 5000));
            await this.sendMouseClick(640, 360);
        }
        catch (error) {
            logger_1.logger.error(`Failed to play video on neko ${this.id}:`, error);
            throw error;
        }
    }
    async pause() {
        await this.requestControl();
        await this.sendKey(0x0020, true);
        await this.sendKey(0x0020, false);
    }
    async resume() {
        await this.pause();
    }
    async seekTo(seconds) {
        await this.requestControl();
        const progressBarY = 650;
        const progressBarStartX = 200;
        const progressBarEndX = 1080;
        const progressBarWidth = progressBarEndX - progressBarStartX;
        await this.sendMouseClick(progressBarStartX, progressBarY);
    }
    async getAuthCookies() {
        logger_1.logger.warn(`Cookie extraction not fully implemented for neko ${this.id}`);
        return [];
    }
    async restoreSession(cookies) {
        logger_1.logger.warn(`Cookie restoration not fully implemented for neko ${this.id}`);
        this.isAuthenticated = false;
    }
    async healthCheck() {
        if (this.ws?.readyState !== ws_1.default.OPEN || !this.isAuthenticated) {
            return false;
        }
        try {
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('Health check timeout'));
                }, 3000);
                this.ws.ping((error) => {
                    clearTimeout(timeout);
                    if (error) {
                        reject(error);
                    }
                    else {
                        resolve();
                    }
                });
            });
            return true;
        }
        catch (error) {
            logger_1.logger.warn(`Health check failed for neko ${this.id}:`, error);
            return false;
        }
    }
    async restart() {
        logger_1.logger.info(`Restarting neko instance ${this.id}`);
        await this.shutdown();
        await new Promise(resolve => setTimeout(resolve, 1000));
        await this.initialize();
    }
    async shutdown() {
        logger_1.logger.info(`Shutting down neko instance ${this.id}`);
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = undefined;
        }
        this.stopPingInterval();
        this.stopHeartbeat();
        if (this.hasControl) {
            try {
                await this.releaseControl();
            }
            catch (error) {
                logger_1.logger.warn(`Failed to release control during shutdown:`, error);
            }
        }
        if (this.ws) {
            this.ws.removeAllListeners();
            this.ws.close(1000, 'Shutdown');
            this.ws = undefined;
        }
        this.isAuthenticated = false;
        this.hasControl = false;
        this.currentVideo = null;
        this.sessionId = undefined;
        this.controlHost = undefined;
        this.reconnectAttempts = 0;
        this.removeAllListeners();
    }
    getLastUsed() {
        return this.lastUsed;
    }
    scheduleReconnect() {
        if (this.reconnectTimer || this.reconnectAttempts >= this.maxReconnectAttempts) {
            return;
        }
        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * this.reconnectAttempts, 30000);
        logger_1.logger.info(`Scheduling reconnect for neko ${this.id} in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.reconnectTimer = setTimeout(async () => {
            this.reconnectTimer = undefined;
            try {
                await this.initialize();
                logger_1.logger.info(`Successfully reconnected neko ${this.id}`);
            }
            catch (error) {
                logger_1.logger.error(`Failed to reconnect neko ${this.id}:`, error);
                this.scheduleReconnect();
            }
        }, delay);
    }
    startPingInterval() {
        this.stopPingInterval();
        this.pingInterval = setInterval(() => {
            if (this.ws?.readyState === ws_1.default.OPEN) {
                this.ws.ping((error) => {
                    if (error) {
                        logger_1.logger.warn(`Ping failed for neko ${this.id}:`, error);
                    }
                });
            }
        }, 30000);
    }
    stopPingInterval() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = undefined;
        }
    }
    startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatInterval = setInterval(() => {
            if (this.ws?.readyState === ws_1.default.OPEN && this.isAuthenticated) {
                this.send({
                    event: EVENT.CLIENT.HEARTBEAT
                });
            }
        }, 10000);
    }
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = undefined;
        }
    }
}
exports.NekoInstanceImpl = NekoInstanceImpl;
//# sourceMappingURL=NekoInstanceImpl.js.map