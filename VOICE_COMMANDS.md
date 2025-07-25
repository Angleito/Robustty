# Voice Commands Configuration Guide

Voice commands are an optional feature that allows users to control the music bot using voice input. This feature requires OpenAI API access for speech recognition.

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```env
# Enable/disable voice commands (default: false)
ENABLE_VOICE_COMMANDS=true

# Required only if voice commands are enabled
OPENAI_API_KEY=your_openai_api_key_here
```

### Requirements

- **OpenAI API Key**: Required for speech-to-text processing using Whisper API
- **Cost Consideration**: Voice commands use OpenAI's Whisper API which costs $0.006 per minute of audio processed

## How It Works

1. **Wake Word Detection**: The bot listens for the wake word "Kanye" to activate command processing
2. **Speech Recognition**: After wake word detection, the bot processes the command using OpenAI Whisper
3. **Command Execution**: Recognized commands are executed (play, skip, stop, etc.)

## Available Voice Commands

When voice commands are enabled, users can say:
- **"Kanye play [song name]"** - Play a song
- **"Kanye skip"** - Skip the current song
- **"Kanye stop"** - Stop playback
- **"Kanye pause"** - Pause playback
- **"Kanye resume"** - Resume playback
- **"Kanye queue"** - Check the queue

## Enabling Voice Commands in Discord

1. Join a voice channel
2. Use `/voice` command to enable voice commands in that channel
3. Use `/novoice` command to disable voice commands

## Running Without Voice Commands

The bot will run perfectly fine without voice commands. Simply:
1. Set `ENABLE_VOICE_COMMANDS=false` or omit it entirely
2. Don't provide an `OPENAI_API_KEY`
3. The `/voice` and `/novoice` commands won't be registered

## Cost Optimization

The voice command system is optimized to minimize API costs:
- Local wake word detection runs first (no API cost)
- Only audio after wake word detection is sent to OpenAI
- Cost tracking is built-in and can be monitored

## Monitoring Voice Command Costs

When voice commands are enabled, the bot tracks usage and costs. Admins can monitor this through the bot's admin commands.