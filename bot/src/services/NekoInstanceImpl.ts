import WebSocket from 'ws';
import { NekoInstance, Cookie } from '../domain/types';
import { RedisClient } from './RedisClient';
import { logger } from './logger';
import { EventEmitter } from 'events';

// WebSocket event types based on neko API
const EVENT = {
  // System Events
  SYSTEM: {
    INIT: 'system/init',
    DISCONNECT: 'system/disconnect',
    ERROR: 'system/error',
  },
  // Client Events  
  CLIENT: {
    HEARTBEAT: 'client/heartbeat',
  },
  // Signal Events
  SIGNAL: {
    OFFER: 'signal/offer',
    ANSWER: 'signal/answer',
    PROVIDE: 'signal/provide',
    CANDIDATE: 'signal/candidate',
  },
  // Member Events
  MEMBER: {
    LIST: 'member/list',
    CONNECTED: 'member/connected',
    DISCONNECTED: 'member/disconnected',
  },
  // Control Events
  CONTROL: {
    LOCKED: 'control/locked',
    RELEASE: 'control/release',
    REQUEST: 'control/request',
    REQUESTING: 'control/requesting',
    CLIPBOARD: 'control/clipboard',
    GIVE: 'control/give',
    KEYBOARD: 'control/keyboard',
  },
  // Screen Events
  SCREEN: {
    CONFIGURATIONS: 'screen/configurations',
    RESOLUTION: 'screen/resolution',
    SET: 'screen/set',
  },
  // Broadcast Events
  BROADCAST: {
    STATUS: 'broadcast/status',
    CREATE: 'broadcast/create',
    DESTROY: 'broadcast/destroy',
  },
  // Admin Events
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
} as const;

interface NekoMessage {
  event: string;
  [key: string]: any;
}

interface SystemInitMessage extends NekoMessage {
  event: 'system/init';
  session_id: string;
  control_host?: string;
  screen_size: {
    width: number;
    height: number;
    rate: number;
  };
  members: Array<{
    id: string;
    name: string;
  }>;
}

interface SignalProvideMessage extends NekoMessage {
  event: 'signal/provide';
  id: string;
  username: string;
  password: string;
}

interface ControlMessage extends NekoMessage {
  x?: number;
  y?: number;
  button?: number;
  key?: number;
  modifiers?: string[];
}

export class NekoInstanceImpl extends EventEmitter implements NekoInstance {
  id: string;
  isAuthenticated: boolean = false;
  currentVideo: string | null = null;
  private ws?: WebSocket;
  private redis: RedisClient;
  private lastUsed: number = 0;
  private nekoUrl: string;
  private nekoPassword: string;
  private nekoUsername: string;
  private reconnectTimer?: NodeJS.Timeout;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 5000;
  private pingInterval?: NodeJS.Timeout;
  private heartbeatInterval?: NodeJS.Timeout;
  private hasControl: boolean = false;
  private sessionId?: string;
  private controlHost?: string;

  constructor(id: string, redis: RedisClient) {
    super();
    this.id = id;
    this.redis = redis;
    this.nekoUrl = process.env.NEKO_INTERNAL_URL || 'http://neko:8080';
    this.nekoPassword = process.env.NEKO_PASSWORD || 'neko';
    this.nekoUsername = process.env.NEKO_USERNAME || 'admin';
  }

  async initialize() {
    try {
      await this.connect();
    } catch (error) {
      logger.error(`Failed to initialize neko instance ${this.id}:`, error);
      this.scheduleReconnect();
    }
  }

  private async connect(): Promise<void> {
    const wsUrl = this.nekoUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    
    this.ws = new WebSocket(`${wsUrl}/ws`);
    
    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, 10000);
      
      this.ws!.on('open', () => {
        clearTimeout(timeout);
        logger.info(`Connected to neko instance ${this.id}`);
        this.reconnectAttempts = 0;
        this.startPingInterval();
        resolve();
      });
      
      this.ws!.on('error', (error) => {
        clearTimeout(timeout);
        logger.error(`WebSocket error for ${this.id}:`, error);
        reject(error);
      });
      
      this.ws!.on('close', (code, reason) => {
        logger.warn(`WebSocket closed for ${this.id}:`, { code, reason: reason.toString() });
        this.isAuthenticated = false;
        this.hasControl = false;
        this.stopPingInterval();
        this.stopHeartbeat();
        this.scheduleReconnect();
      });
      
      this.ws!.on('message', (data) => {
        this.handleMessage(data.toString());
      });
    });
  }

  private async authenticate(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Authentication timeout'));
      }, 5000);
      
      // For now, just mark as authenticated after receiving system/init
      // Neko authentication might not be required for basic usage
      clearTimeout(timeout);
      this.isAuthenticated = true;
      logger.info(`Authenticated to neko instance ${this.id} (simplified auth)`);
      resolve();
    });
  }

  private handleMessage(message: string): void {
    try {
      const data: NekoMessage = JSON.parse(message);
      
      logger.debug(`Received neko message for ${this.id}:`, { event: data.event });
      
      switch (data.event) {
        case EVENT.SYSTEM.INIT:
          const initData = data as SystemInitMessage;
          this.sessionId = initData.session_id;
          this.controlHost = initData.control_host;
          logger.info(`Neko session initialized for ${this.id}:`, { 
            sessionId: this.sessionId,
            screenSize: initData.screen_size,
            members: initData.members.length 
          });
          
          // Start heartbeat
          this.startHeartbeat();
          
          // Authenticate after init (simplified)
          this.authenticate()
            .catch(error => {
              logger.error(`Authentication failed for ${this.id}:`, error);
              this.ws?.close();
            });
          break;
          
        case EVENT.MEMBER.CONNECTED:
          logger.debug(`Member connected to neko ${this.id}:`, data.id);
          break;
          
        case EVENT.SYSTEM.ERROR:
          logger.error(`System error from neko ${this.id}:`, data);
          break;
          
        case EVENT.CONTROL.LOCKED:
          this.controlHost = data.id;
          this.hasControl = data.id === this.sessionId;
          logger.debug(`Control status for ${this.id}:`, { 
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
          logger.debug(`Screen resolution for ${this.id}:`, data);
          break;
          
        case EVENT.MEMBER.LIST:
          logger.debug(`Member list for ${this.id}:`, data.members);
          break;
          
        case EVENT.SYSTEM.DISCONNECT:
          logger.warn(`Disconnected from neko ${this.id}:`, data.message);
          this.emit('auth', data);
          this.ws?.close();
          break;
          
        case EVENT.CONTROL.REQUESTING:
          logger.debug(`Control requested by ${data.id} for ${this.id}`);
          break;
          
        default:
          logger.debug(`Unhandled neko event for ${this.id}:`, data.event);
      }
    } catch (error) {
      logger.error(`Failed to parse neko message for ${this.id}:`, error);
    }
  }

  private send(data: NekoMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const message = JSON.stringify(data);
      logger.debug(`Sending neko message for ${this.id}:`, { event: data.event });
      this.ws.send(message);
    } else {
      logger.warn(`Cannot send message to neko ${this.id}: WebSocket not open`);
    }
  }
  
  private async requestControl(): Promise<void> {
    if (this.hasControl) return;
    
    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Control request timeout'));
      }, 5000);
      
      const controlHandler = (message: NekoMessage) => {
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
  
  private async releaseControl(): Promise<void> {
    if (!this.hasControl) return;
    
    this.send({
      event: EVENT.CONTROL.RELEASE
    });
    this.hasControl = false;
  }
  
  private async sendMouseMove(x: number, y: number): Promise<void> {
    await this.requestControl();
    
    this.send({
      event: 'mousemove',
      x,
      y
    });
  }
  
  private async sendMouseClick(x: number, y: number, button: number = 0): Promise<void> {
    await this.requestControl();
    
    // Send mouse down
    this.send({
      event: 'mousedown',
      x,
      y,
      button
    });
    
    // Send mouse up after a short delay
    setTimeout(() => {
      this.send({
        event: 'mouseup',
        x,
        y,
        button
      });
    }, 50);
  }
  
  private async sendKey(keysym: number, pressed: boolean = true): Promise<void> {
    await this.requestControl();
    
    this.send({
      event: pressed ? 'keydown' : 'keyup',
      keysym
    });
  }
  
  private async sendText(text: string): Promise<void> {
    await this.requestControl();
    
    // Convert text to keysyms and send each character
    for (const char of text) {
      const keysym = char.charCodeAt(0);
      await this.sendKey(keysym, true);
      await this.sendKey(keysym, false);
      await new Promise(resolve => setTimeout(resolve, 10)); // Small delay between keys
    }
  }
  
  private async navigate(url: string): Promise<void> {
    await this.requestControl();
    
    // Click on address bar (assuming it's at the top)
    await this.sendMouseClick(400, 50);
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Select all (Ctrl+A)
    await this.sendKey(0xFFE3, true); // Control key down
    await this.sendKey(0x0061, true); // 'a' key down
    await this.sendKey(0x0061, false); // 'a' key up
    await this.sendKey(0xFFE3, false); // Control key up
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Type the URL
    await this.sendText(url);
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Press Enter
    await this.sendKey(0xFF0D, true); // Return key down
    await this.sendKey(0xFF0D, false); // Return key up
  }

  async playVideo(url: string): Promise<void> {
    this.currentVideo = url;
    this.lastUsed = Date.now();
    
    try {
      // Navigate to the video URL
      await this.navigate(url);
      
      // Wait for page load
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      // Try to click play button (YouTube specific)
      // YouTube play button is usually in the center of the video
      await this.sendMouseClick(640, 360); // Assuming 1280x720 resolution
      
    } catch (error) {
      logger.error(`Failed to play video on neko ${this.id}:`, error);
      throw error;
    }
  }

  async pause(): Promise<void> {
    await this.requestControl();
    
    // Send spacebar to pause/play
    await this.sendKey(0x0020, true); // Space key down
    await this.sendKey(0x0020, false); // Space key up
  }

  async resume(): Promise<void> {
    await this.pause(); // Space toggles play/pause
  }

  async seekTo(seconds: number): Promise<void> {
    await this.requestControl();
    
    // Click on the progress bar (rough approximation)
    // This is a simplified approach - in reality you'd need to calculate the exact position
    const progressBarY = 650; // Approximate Y position of YouTube progress bar
    const progressBarStartX = 200;
    const progressBarEndX = 1080;
    const progressBarWidth = progressBarEndX - progressBarStartX;
    
    // For now, just click at the beginning of the progress bar
    // TODO: Calculate proper position based on video duration and target seconds
    await this.sendMouseClick(progressBarStartX, progressBarY);
  }

  async getAuthCookies(): Promise<Cookie[]> {
    // Since we can't execute JavaScript directly in neko, we need to use a different approach
    // This would require implementing a browser extension or using neko's clipboard functionality
    logger.warn(`Cookie extraction not fully implemented for neko ${this.id}`);
    return [];
  }

  async restoreSession(cookies: Cookie[]): Promise<void> {
    // Cookie restoration would need to be done through browser developer tools or extension
    logger.warn(`Cookie restoration not fully implemented for neko ${this.id}`);
    this.isAuthenticated = false;
  }

  async healthCheck(): Promise<boolean> {
    if (this.ws?.readyState !== WebSocket.OPEN || !this.isAuthenticated) {
      return false;
    }
    
    try {
      // Send a ping to verify connection is alive
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Health check timeout'));
        }, 3000);
        
        this.ws!.ping((error: any) => {
          clearTimeout(timeout);
          if (error) {
            reject(error);
          } else {
            resolve();
          }
        });
      });
      
      return true;
    } catch (error) {
      logger.warn(`Health check failed for neko ${this.id}:`, error);
      return false;
    }
  }

  async restart(): Promise<void> {
    logger.info(`Restarting neko instance ${this.id}`);
    await this.shutdown();
    await new Promise(resolve => setTimeout(resolve, 1000)); // Brief delay before restart
    await this.initialize();
  }

  async shutdown(): Promise<void> {
    logger.info(`Shutting down neko instance ${this.id}`);
    
    // Clear any reconnection attempts
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    
    // Stop intervals
    this.stopPingInterval();
    this.stopHeartbeat();
    
    // Release control if we have it
    if (this.hasControl) {
      try {
        await this.releaseControl();
      } catch (error) {
        logger.warn(`Failed to release control during shutdown:`, error);
      }
    }
    
    // Close WebSocket connection
    if (this.ws) {
      this.ws.removeAllListeners();
      this.ws.close(1000, 'Shutdown');
      this.ws = undefined;
    }
    
    // Reset state
    this.isAuthenticated = false;
    this.hasControl = false;
    this.currentVideo = null;
    this.sessionId = undefined;
    this.controlHost = undefined;
    this.reconnectAttempts = 0;
    
    // Remove all event listeners
    this.removeAllListeners();
  }

  getLastUsed(): number {
    return this.lastUsed;
  }
  
  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }
    
    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * this.reconnectAttempts, 30000); // Max 30 seconds
    
    logger.info(`Scheduling reconnect for neko ${this.id} in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = undefined;
      
      try {
        await this.initialize();
        logger.info(`Successfully reconnected neko ${this.id}`);
      } catch (error) {
        logger.error(`Failed to reconnect neko ${this.id}:`, error);
        this.scheduleReconnect();
      }
    }, delay);
  }
  
  private startPingInterval(): void {
    this.stopPingInterval();
    
    // Send ping every 30 seconds to keep connection alive
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.ping((error: any) => {
          if (error) {
            logger.warn(`Ping failed for neko ${this.id}:`, error);
          }
        });
      }
    }, 30000);
  }
  
  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = undefined;
    }
  }
  
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    // Send heartbeat every 10 seconds as per neko protocol
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN && this.isAuthenticated) {
        this.send({
          event: EVENT.CLIENT.HEARTBEAT
        });
      }
    }, 10000);
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = undefined;
    }
  }
}