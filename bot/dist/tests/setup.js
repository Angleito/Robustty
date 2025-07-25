"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mockAudioStream = exports.mockVoiceConnection = void 0;
const logger_1 = require("../services/logger");
process.env.NODE_ENV = 'test';
process.env.DISCORD_TOKEN = 'test-token';
process.env.TTS_ENABLED = 'true';
process.env.ELEVENLABS_API_KEY = 'test-api-key';
process.env.ELEVENLABS_VOICE_ID = 'test-voice-id';
process.env.OPENAI_API_KEY = 'test-openai-key';
logger_1.logger.transports.forEach(transport => {
    transport.silent = true;
});
jest.setTimeout(30000);
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
exports.mockVoiceConnection = mockVoiceConnection;
const mockAudioStream = {
    pipe: jest.fn(),
    on: jest.fn(),
    destroy: jest.fn()
};
exports.mockAudioStream = mockAudioStream;
//# sourceMappingURL=setup.js.map