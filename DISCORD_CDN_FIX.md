# Discord CDN HTTP 403 Error Fix

## Issue
The bot's network connectivity checker was receiving HTTP 403 (Forbidden) errors when checking Discord CDN connectivity at `https://cdn.discordapp.com`. This was causing warnings in the logs:
```
WARNING:src.utils.network_connectivity:✗ Discord CDN: HTTP 403
```

## Root Cause
1. Discord CDN blocks generic HEAD requests without proper headers
2. The network connectivity checker was using a simple HEAD request without a User-Agent header
3. Discord CDN requires proper User-Agent headers to prevent abuse and bot scraping

## Solution Implemented
Modified `src/utils/network_connectivity.py` to:

1. **Add proper headers** including User-Agent for all endpoint checks:
   ```python
   headers = {
       'User-Agent': 'Robustty Bot/1.0 (Discord Music Bot)',
       'Accept': '*/*',
       'Accept-Encoding': 'gzip, deflate',
       'Connection': 'keep-alive'
   }
   ```

2. **Special handling for Discord CDN**:
   - Switch from HEAD to GET requests for Discord CDN endpoints
   - Accept any HTTP response (including 403/404) as successful connectivity
   - The goal is to verify network connectivity, not CDN authorization
   - Connection errors would throw exceptions, so any HTTP response means CDN is reachable

3. **Updated success criteria**:
   ```python
   if 'cdn.discordapp.com' in endpoint.url or 'discordapp.com' in endpoint.url:
       # Consider it successful if we got any HTTP response
       # Connection errors would have thrown exceptions
       success = True
       error = None if response.status < 400 else f"HTTP {response.status} (CDN reachable)"
   ```

## Why This Fix Works
- Discord CDN is primarily used for serving attachments and media with proper authentication
- For connectivity checks, we only need to verify that we can reach the CDN servers
- Getting a 403 response actually confirms the CDN is reachable and responding
- True connectivity failures would result in timeouts or connection errors, not HTTP responses

## Configuration
The Discord CDN check is configured in `config/config.yaml`:
```yaml
network:
  essential_endpoints:
    - name: "Discord CDN"
      url: "https://cdn.discordapp.com"
      timeout: 5
      required: true
      priority: 2
```

## Testing
The fix can be verified by:
1. Running the bot and checking logs for Discord CDN connectivity status
2. The warning should now either disappear or show "(CDN reachable)" instead of a failure
3. Full connectivity checks should show improved success rates

## Additional Notes
- This aligns with how the `HTTPSessionManager` handles requests (using proper User-Agent)
- The fix is backward compatible and doesn't affect other endpoint checks
- Discord CDN will still return 403 for unauthorized requests, but that's expected behavior