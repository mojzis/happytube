# HappyTube Web Player

A simple, controlled web player for curated YouTube videos from HappyTube.

## Features

- **Controlled Playback**: YouTube embed with disabled recommendations and related videos
- **Curated Playlist**: Only shows videos from your HappyTube collection
- **Search**: Filter videos by title, description, or channel
- **Keyboard Navigation**: Arrow keys or n/p to navigate between videos
- **Auto-play**: Optional auto-play next video when current ends
- **Fullscreen**: Fullscreen support while blocking unwanted YouTube navigation

## YouTube Embed Restrictions

The player uses the YouTube IFrame API with the following restrictions to prevent access to unsanctioned content:

- `rel=0` - No related videos from other channels
- `modestbranding=1` - Minimal YouTube branding
- `iv_load_policy=3` - No annotations
- `disablekb=1` - Disabled keyboard controls that could navigate to YouTube
- `showinfo=0` - No video information overlay

## Usage

### Start the web server:

```bash
# Using Poetry
poetry run python -m happytube.web.server

# Or directly
python happytube/web/server.py
```

The player will be available at `http://127.0.0.1:5000`

### Custom host/port:

```bash
poetry run python -c "from happytube.web import run_server; run_server(host='0.0.0.0', port=8080)"
```

## Requirements

1. First, run the main HappyTube script to fetch and rate videos:
   ```bash
   poetry run python -m happytube.main
   ```

2. This will populate the `data/fetched/` directory with video data

3. Then start the web player to view your curated videos

## API Endpoints

- `GET /` - Main player interface
- `GET /api/videos` - Get all videos as JSON
- `GET /api/videos/<video_id>` - Get specific video details

## Future Enhancements

Potential improvements for the future:

- User preferences and watch history
- Playlist management (create custom playlists)
- Video ratings and feedback
- Integration with happiness scores
- Export as standalone app
- Mobile-responsive improvements
- Separate repository for easier deployment
