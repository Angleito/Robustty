# Platform Implementation Guide

## Odysee Platform

### How to Enable
1. Set `ODYSEE_ENABLED=true` in your `.env` file
2. The bot will automatically register and use the Odysee platform

### Features
- Search videos on Odysee/LBRY network
- Extract video IDs from Odysee URLs
- Get video details and metadata
- Stream URLs for playback

### Implementation Details
- Uses LBRY API endpoints for searching and streaming
- Supports multiple URL formats (odysee.com, lbry.tv, lbry://)
- Leverages claim_search API for video discovery

## PeerTube Platform

### How to Enable
PeerTube is enabled by default. You can configure instances in `config/config.yaml`:

```yaml
peertube:
  enabled: true
  instances:
    - https://framatube.org
    - https://video.ploud.fr
    - https://peertube.social
  max_results_per_instance: 5
```

### Features
- Search across multiple PeerTube instances
- Federated video discovery
- Instance-specific configuration
- Automatic failover for unavailable instances

### Implementation Details
- Searches multiple instances in parallel
- Handles 403 errors gracefully (some instances require auth)
- Aggregates and sorts results by view count
- Supports PeerTube's API v1

## Adding New Platforms

To add a new platform:

1. Create a new file in `src/platforms/newplatform.py`
2. Inherit from `VideoPlatform` base class
3. Implement required methods:
   - `search_videos()`
   - `get_video_details()`
   - `extract_video_id()`
   - `is_platform_url()`
   - `get_stream_url()`
4. Register in `src/bot/bot.py`
5. Add configuration to `config/config.yaml`
6. Update `.env.example` if needed

## API Requirements

Each platform must provide:
- Search functionality
- Video metadata retrieval
- Stream URL generation
- URL pattern matching

## Error Handling

All platforms should:
- Log errors appropriately
- Return empty results on failure
- Handle network issues gracefully
- Validate input parameters