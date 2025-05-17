# Running Robustty Without Browser Automation

This guide explains how to run Robustty without the browser automation packages (`selenium` and `browser_cookie3`), which can sometimes cause installation timeouts.

## Why Run Without Browser Automation?

Browser automation packages are only required for automatic cookie extraction from browsers. The bot functions perfectly without them, you'll just need to provide cookies manually if needed.

Benefits of running without browser automation:
- Faster Docker builds
- Smaller container size
- No timeout issues during installation
- Reduced dependencies

## Quick Start

### Option 1: Use the Minimal Docker Compose

```bash
# Use the minimal docker-compose that excludes cookie extractor
docker-compose -f docker-compose.minimal.yml up -d
```

### Option 2: Build Without Browser Dependencies

```bash
# Use the quick build script
./scripts/quick-build.sh

# Or build manually with the no-browser requirements
docker build -f docker/bot/Dockerfile.no-browser -t robustty-bot .
```

### Option 3: Modify Main Requirements

```bash
# Use requirements without browser automation
cp requirements-no-browser.txt requirements.txt
docker-compose build
```

## Manual Cookie Configuration

If you need to use cookies for YouTube (e.g., for age-restricted content), you can provide them manually:

1. Create a `cookies` directory:
   ```bash
   mkdir -p cookies
   ```

2. Extract cookies from your browser using a browser extension:
   - [Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt/)
   - [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

3. Convert the cookies to JSON format:
   ```json
   [
     {
       "name": "cookie_name",
       "value": "cookie_value",
       "domain": ".youtube.com",
       "path": "/",
       "secure": true,
       "httpOnly": false,
       "sameSite": "None"
     }
   ]
   ```

4. Save as `cookies/youtube_cookies.json` or `cookies/manual_cookies.json`

## Modified Cookie Extractor

The cookie extractor has been updated to handle missing browser automation gracefully:

- It will check if `browser_cookie3` is available
- If not, it runs in manual mode
- In manual mode, it checks for `manual_cookies.json` periodically
- The bot will use cookies if available, but won't fail if they're missing

## Verifying the Installation

After building and running:

1. Check bot logs:
   ```bash
   docker logs robustty-bot
   ```

2. Look for warnings about missing browser automation (these are normal):
   ```
   WARNING - browser_cookie3 is not installed. Cookie extraction will be disabled.
   ```

3. The bot should still start successfully and respond to commands

## Troubleshooting

### Build Still Times Out

If the build still times out, try:

1. Use the staged Dockerfile:
   ```bash
   docker build -f docker/bot/Dockerfile.staged -t robustty-bot .
   ```

2. Build with increased timeout:
   ```bash
   docker build --build-arg BUILDKIT_PROGRESS=plain \
                --progress=plain \
                -f docker/bot/Dockerfile.fixed \
                -t robustty-bot .
   ```

### Bot Can't Access Age-Restricted Content

Without cookies, the bot might not be able to access age-restricted content. Solutions:

1. Provide manual cookies (see above)
2. Use YouTube API for search (not affected by age restrictions)
3. Consider using alternative platforms

### Cookie Extractor Container Fails

If you're using docker-compose and the cookie extractor fails:

1. Comment it out in `docker-compose.yml`
2. Or use `docker-compose.minimal.yml`
3. The bot will continue to work without it

## Feature Limitations

Without browser automation, these features are limited:

- **Automatic cookie extraction**: Must be done manually
- **Browser profile access**: Not available
- **Automatic authentication**: Must provide cookies manually

However, these features still work normally:
- All music playback functionality
- Search across all platforms
- Queue management
- All bot commands
- YouTube API search (if API key is provided)

## Future Improvements

We're working on:
- Alternative cookie extraction methods
- OAuth2 authentication support
- Better manual cookie management
- Optional browser automation loading