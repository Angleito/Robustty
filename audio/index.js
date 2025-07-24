require('dotenv').config();
const express = require('express');
const { spawn, execSync } = require('child_process');
const winston = require('winston');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Logger setup
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    })
  ]
});

// Active capture processes and module IDs
const activeCaptures = new Map();
const virtualSinks = new Map();

// Initialize PulseAudio virtual sinks
async function initializePulseAudio() {
  try {
    logger.info('Initializing PulseAudio virtual sinks...');
    
    // First, list and remove any existing virtual sinks
    try {
      const modules = await runCommand('pactl', ['list', 'short', 'modules']);
      const lines = modules.split('\n').filter(line => line.includes('module-null-sink'));
      
      for (const line of lines) {
        const moduleId = line.split('\t')[0];
        if (moduleId) {
          await runCommand('pactl', ['unload-module', moduleId]).catch(() => {});
        }
      }
    } catch (error) {
      logger.debug('No existing modules to clean up');
    }
    
    // Create virtual sinks for each potential neko instance
    const maxInstances = parseInt(process.env.MAX_NEKO_INSTANCES || '5');
    
    for (let i = 0; i < maxInstances; i++) {
      const sinkName = `neko_sink_${i}`;
      
      try {
        // Create new virtual sink with proper configuration
        const result = await runCommand('pactl', [
          'load-module',
          'module-null-sink',
          `sink_name=${sinkName}`,
          `sink_properties=device.description="Neko_Instance_${i}"`,
          'rate=48000',
          'channels=2',
          'channel_map=front-left,front-right'
        ]);
        
        const moduleId = result.trim();
        virtualSinks.set(sinkName, moduleId);
        
        logger.info(`Created virtual sink: ${sinkName} (module ${moduleId})`);
      } catch (error) {
        logger.error(`Failed to create sink ${sinkName}:`, error.message);
      }
    }
    
    // List all sinks for verification
    const sinks = await runCommand('pactl', ['list', 'short', 'sinks']);
    logger.debug('Available sinks:', sinks);
    
  } catch (error) {
    logger.error('Failed to initialize PulseAudio:', error);
    throw error;
  }
}

// Run command helper
function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args);
    let output = '';
    
    proc.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    proc.stderr.on('data', (data) => {
      logger.error(`Command error: ${data.toString()}`);
    });
    
    proc.on('close', (code) => {
      if (code === 0) {
        resolve(output);
      } else {
        reject(new Error(`Command failed with code ${code}`));
      }
    });
  });
}

// Audio capture endpoint
app.get('/capture/:instanceId', async (req, res) => {
  const { instanceId } = req.params;
  
  if (activeCaptures.has(instanceId)) {
    res.status(409).json({ error: 'Capture already active for this instance' });
    return;
  }
  
  try {
    // Extract instance number from instanceId (format: neko-0, neko-1, etc.)
    const match = instanceId.match(/\d+/);
    const instanceNum = match ? match[0] : '0';
    const sinkName = `neko_sink_${instanceNum}`;
    const monitorSource = `${sinkName}.monitor`;
    
    // Verify the sink exists
    const sources = await runCommand('pactl', ['list', 'short', 'sources']);
    if (!sources.includes(monitorSource)) {
      logger.error(`Monitor source ${monitorSource} not found`);
      res.status(404).json({ error: `Audio source for instance ${instanceId} not found` });
      return;
    }
    
    logger.info(`Starting audio capture for ${instanceId} from ${monitorSource}`);
    
    // Start FFmpeg capture process with optimized settings for Discord
    const ffmpeg = spawn('ffmpeg', [
      '-f', 'pulse',
      '-i', monitorSource,
      '-ac', '2',              // Force stereo
      '-ar', '48000',          // Discord native sample rate
      '-c:a', 'libopus',       // Discord native codec
      '-b:a', '128k',          // High quality bitrate
      '-application', 'audio', // Optimized for music/audio
      '-frame_duration', '20', // 20ms frames for Discord
      '-packet_loss', '10',    // Handle up to 10% packet loss
      '-vbr', 'on',           // Variable bitrate for better quality
      '-compression_level', '10', // Max compression efficiency
      '-f', 'opus',           // Output format
      '-loglevel', 'warning', // Reduce log verbosity
      'pipe:1'
    ]);
    
    const captureInfo = {
      process: ffmpeg,
      instanceId,
      sinkName,
      startTime: new Date(),
      bytesTransmitted: 0
    };
    
    activeCaptures.set(instanceId, captureInfo);
    
    // Handle FFmpeg stderr for debugging
    ffmpeg.stderr.on('data', (data) => {
      const message = data.toString();
      if (message.includes('error') || message.includes('Error')) {
        logger.error(`FFmpeg error (${instanceId}): ${message}`);
      } else {
        logger.debug(`FFmpeg (${instanceId}): ${message}`);
      }
    });
    
    ffmpeg.on('error', (error) => {
      logger.error(`FFmpeg spawn error (${instanceId}):`, error);
      activeCaptures.delete(instanceId);
      if (!res.headersSent) {
        res.status(500).json({ error: 'Failed to start audio capture' });
      }
    });
    
    ffmpeg.on('close', (code) => {
      logger.info(`FFmpeg closed for ${instanceId} with code ${code}`);
      const capture = activeCaptures.get(instanceId);
      if (capture) {
        const duration = (new Date() - capture.startTime) / 1000;
        logger.info(`Capture stats for ${instanceId}: Duration=${duration}s, Bytes=${capture.bytesTransmitted}`);
      }
      activeCaptures.delete(instanceId);
    });
    
    // Set response headers for streaming
    res.setHeader('Content-Type', 'audio/opus');
    res.setHeader('Transfer-Encoding', 'chunked');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('X-Instance-Id', instanceId);
    
    // Track bytes transmitted
    ffmpeg.stdout.on('data', (chunk) => {
      captureInfo.bytesTransmitted += chunk.length;
    });
    
    // Pipe FFmpeg output to response
    ffmpeg.stdout.pipe(res);
    
    // Clean up on client disconnect
    req.on('close', () => {
      logger.info(`Client disconnected from ${instanceId}`);
      if (ffmpeg && !ffmpeg.killed) {
        ffmpeg.kill('SIGTERM');
      }
      activeCaptures.delete(instanceId);
    });
    
  } catch (error) {
    logger.error(`Failed to start capture for ${instanceId}:`, error);
    res.status(500).json({ error: 'Failed to start audio capture', details: error.message });
  }
});

// Stop capture endpoint
app.delete('/capture/:instanceId', (req, res) => {
  const { instanceId } = req.params;
  const captureInfo = activeCaptures.get(instanceId);
  
  if (captureInfo && captureInfo.process) {
    const { process: ffmpeg, startTime, bytesTransmitted } = captureInfo;
    
    if (!ffmpeg.killed) {
      ffmpeg.kill('SIGTERM');
    }
    
    const duration = (new Date() - startTime) / 1000;
    activeCaptures.delete(instanceId);
    
    res.json({ 
      message: 'Capture stopped',
      stats: {
        duration: `${duration}s`,
        bytesTransmitted,
        averageBitrate: bytesTransmitted > 0 ? Math.round((bytesTransmitted * 8) / duration / 1000) + ' kbps' : '0 kbps'
      }
    });
  } else {
    res.status(404).json({ error: 'No active capture for this instance' });
  }
});

// Get active streams with detailed info
app.get('/streams', (req, res) => {
  const streams = Array.from(activeCaptures.entries()).map(([id, info]) => ({
    instanceId: id,
    sinkName: info.sinkName,
    startTime: info.startTime,
    duration: `${(new Date() - info.startTime) / 1000}s`,
    bytesTransmitted: info.bytesTransmitted,
    active: info.process && !info.process.killed
  }));
  
  res.json({
    activeStreams: streams.length,
    streams
  });
});

// Enhanced health check
app.get('/health', async (req, res) => {
  try {
    // Check PulseAudio status
    let pulseAudioStatus = 'unknown';
    let availableSinks = 0;
    
    try {
      const paInfo = await runCommand('pactl', ['info']);
      if (paInfo.includes('Server Name:')) {
        pulseAudioStatus = 'running';
        
        // Count virtual sinks
        const sinks = await runCommand('pactl', ['list', 'short', 'sinks']);
        availableSinks = (sinks.match(/neko_sink_\d+/g) || []).length;
      }
    } catch (error) {
      pulseAudioStatus = 'error';
    }
    
    // Check FFmpeg availability
    let ffmpegAvailable = false;
    try {
      await runCommand('ffmpeg', ['-version']);
      ffmpegAvailable = true;
    } catch (error) {
      ffmpegAvailable = false;
    }
    
    const health = {
      status: pulseAudioStatus === 'running' && ffmpegAvailable ? 'healthy' : 'degraded',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      services: {
        pulseAudio: {
          status: pulseAudioStatus,
          virtualSinks: availableSinks
        },
        ffmpeg: {
          available: ffmpegAvailable
        }
      },
      captures: {
        active: activeCaptures.size,
        instances: Array.from(activeCaptures.keys())
      },
      memory: process.memoryUsage()
    };
    
    res.status(health.status === 'healthy' ? 200 : 503).json(health);
  } catch (error) {
    logger.error('Health check error:', error);
    res.status(503).json({ 
      status: 'error', 
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Route audio from neko to virtual sink
app.post('/route/:instanceId', async (req, res) => {
  const { instanceId } = req.params;
  const { sourceApp } = req.body; // The neko application name in PulseAudio
  
  try {
    const match = instanceId.match(/\d+/);
    const instanceNum = match ? match[0] : '0';
    const sinkName = `neko_sink_${instanceNum}`;
    
    // Check if sink exists
    if (!virtualSinks.has(sinkName)) {
      res.status(404).json({ error: `Virtual sink for instance ${instanceId} not found` });
      return;
    }
    
    // Move the audio stream to our virtual sink
    if (sourceApp) {
      await runCommand('pactl', ['move-sink-input', sourceApp, sinkName]);
      logger.info(`Routed audio from ${sourceApp} to ${sinkName}`);
      res.json({ message: 'Audio routed successfully', sink: sinkName });
    } else {
      // List all sink inputs to help identify the correct one
      const inputs = await runCommand('pactl', ['list', 'short', 'sink-inputs']);
      res.json({ 
        message: 'Please provide sourceApp parameter',
        availableInputs: inputs.split('\n').filter(line => line.trim())
      });
    }
  } catch (error) {
    logger.error(`Failed to route audio for ${instanceId}:`, error);
    res.status(500).json({ error: 'Failed to route audio', details: error.message });
  }
});

// Start server
async function start() {
  await initializePulseAudio();
  
  server = app.listen(PORT, () => {
    logger.info(`Audio capture service listening on port ${PORT}`);
  });
  
  return server;
}

// Graceful shutdown
async function shutdown(signal) {
  logger.info(`Received ${signal}, shutting down audio capture service...`);
  
  // Stop accepting new connections
  if (server) {
    server.close(() => {
      logger.info('HTTP server closed');
    });
  }
  
  // Kill all active captures
  for (const [instanceId, captureInfo] of activeCaptures.entries()) {
    if (captureInfo.process && !captureInfo.process.killed) {
      logger.info(`Stopping capture for ${instanceId}`);
      captureInfo.process.kill('SIGTERM');
    }
  }
  
  // Unload virtual sinks
  for (const [sinkName, moduleId] of virtualSinks.entries()) {
    try {
      await runCommand('pactl', ['unload-module', moduleId]);
      logger.info(`Unloaded virtual sink: ${sinkName}`);
    } catch (error) {
      logger.error(`Failed to unload ${sinkName}:`, error.message);
    }
  }
  
  // Give processes time to clean up
  setTimeout(() => {
    process.exit(0);
  }, 2000);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// Global error handlers
process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception:', error);
  shutdown('uncaughtException');
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled rejection at:', promise, 'reason:', reason);
});

// Start the server
let server;
start().catch(error => {
  logger.error('Failed to start audio capture service:', error);
  process.exit(1);
});