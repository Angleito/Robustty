# Voice Command Troubleshooting Guide

## Prerequisites Checklist

1. **Environment Variables** - Make sure these are set:
   ```bash
   # Voice commands (auto-enabled if TTS is true)
   ENABLE_VOICE_COMMANDS=true  # Optional if TTS_ENABLED=true
   OPENAI_API_KEY=sk-...  # Required for voice recognition
   
   # Text-to-Speech (will auto-enable voice commands)
   TTS_ENABLED=true  # This alone will enable voice commands too!
   ELEVENLABS_API_KEY=...  # Required for TTS
   ELEVENLABS_VOICE_ID=...  # Optional, has defaults
   ELEVENLABS_MODEL_ID=eleven_flash_v2_5  # Optional, defaults to fastest
   ```

   **Note**: Setting `TTS_ENABLED=true` automatically enables voice commands, so you don't need to set `ENABLE_VOICE_COMMANDS=true` separately.

2. **Docker Services** - All services must be running:
   ```bash
   docker-compose up -d
   docker-compose ps  # Should show all containers running
   ```

## Common Issues and Solutions

### Issue 1: "Voice commands are not enabled on this bot"
**Solution**: Set `ENABLE_VOICE_COMMANDS=true` in your `.env` file and restart Docker

### Issue 2: Bot doesn't hear "Kanye" wake word
**Possible causes**:
- Microphone quality/volume too low
- Background noise
- Not pronouncing "Kanye" clearly
- Bot not actually listening (check logs)

**Debug steps**:
```bash
# Check if voice listener is active
docker-compose logs bot | grep -i "voice"
docker-compose logs bot | grep -i "listening"
```

### Issue 3: No TTS response after commands
**Check**:
- `TTS_ENABLED=true` is set
- ElevenLabs API key is valid
- Voice ID exists in ElevenLabs

**Debug steps**:
```bash
# Look for TTS errors
docker-compose logs bot | grep -i "tts"
docker-compose logs bot | grep -i "elevenlabs"
```

### Issue 4: Bot joins voice channel but doesn't listen
**Debug steps**:
1. Check audio service is running:
   ```bash
   docker-compose logs audio
   ```

2. Check voice connection logs:
   ```bash
   docker-compose logs bot | grep "VoiceCommandHandler"
   ```

## Step-by-Step Testing

1. **Start fresh**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

2. **Watch logs in real-time**:
   ```bash
   docker-compose logs -f bot
   ```

3. **Enable voice in Discord**:
   - Join a voice channel
   - Type `/voice` command
   - Watch logs for initialization

4. **Test wake word**:
   - Say "Kanye" clearly
   - Look for "Wake word detected" in logs
   - Then say your command (e.g., "play some music")

## Log Messages to Look For

### Successful initialization:
```
[MusicBot] Voice commands enabled
[TTS] ✅ Text-to-Speech service initialized successfully with ElevenLabs
[VoiceCommandHandler] Started voice command listening in [channel name]
[VoiceCommandHandler] Generated greeting: "What's good nigga"
```

### Wake word detection:
```
[VoiceCommandHandler] 🎙️ Wake word "Kanye" detected!
[VoiceCommandHandler] 👂 Listening for command after wake word...
```

### Command processing:
```
[VoiceCommandHandler] 💰 Processing command with OpenAI Whisper
[VoiceCommandHandler] ✅ Voice command parsed: play with parameters: [song name]
```

### TTS playback:
```
[VoiceCommandHandler] 🎤 Generating speech using ElevenLabs API...
[VoiceCommandHandler] ✅ TTS response played successfully: "Ok nigga, playing..."
```

## API Key Validation

1. **Test OpenAI API**:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer YOUR_OPENAI_API_KEY"
   ```

2. **Test ElevenLabs API**:
   ```bash
   curl -X GET "https://api.elevenlabs.io/v1/voices" \
     -H "xi-api-key: YOUR_ELEVENLABS_API_KEY"
   ```

## Still Not Working?

1. **Enable debug logging**:
   ```bash
   LOG_LEVEL=debug
   ```

2. **Check Discord permissions**:
   - Bot needs: Connect, Speak, Use Voice Activity
   - User needs: Use Voice Activity

3. **Test components individually**:
   - First get `/play` commands working
   - Then enable voice without TTS
   - Finally enable TTS

4. **Common mistakes**:
   - Wrong API keys (copy-paste errors)
   - Missing quotes around API keys in .env
   - Not restarting Docker after .env changes
   - Firewall blocking voice packets