import { logger } from '../services/logger';

// Mock environment variables for tests
process.env.NODE_ENV = 'test';
process.env.DISCORD_TOKEN = 'test-token';
process.env.TTS_ENABLED = 'true';
process.env.ELEVENLABS_API_KEY = 'test-api-key';
process.env.ELEVENLABS_VOICE_ID = 'test-voice-id';
process.env.OPENAI_API_KEY = 'test-openai-key';

// Silence logger during tests
logger.transports.forEach(transport => {
  transport.silent = true;
});

// Global test timeout
jest.setTimeout(30000);

// Mock Discord.js voice connection
const mockVoiceConnection = {
  state: {
    status: 'ready',
    subscription: {
      player: {
        state: { status: 'idle' },
        play: jest.fn(),
        on: jest.fn(),
        off: jest.fn()
      }
    }
  },
  destroy: jest.fn()
};

// Mock audio streams
const mockAudioStream = {
  pipe: jest.fn(),
  on: jest.fn(),
  destroy: jest.fn()
};

// Export mocks for use in tests
export { mockVoiceConnection, mockAudioStream };