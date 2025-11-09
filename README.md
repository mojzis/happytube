# HappyTube

A Python application that analyzes YouTube videos to identify and enhance "happy" content. It fetches videos from YouTube API, uses Claude AI to assess happiness scores, and provides a curated web player for viewing.

## Features

- **Video Fetching**: Search and fetch videos from YouTube API by category, length, and order
- **AI Assessment**: Use Claude AI to assess video happiness from title & description
- **Web Player**: Simple, controlled video player with disabled YouTube recommendations
- **Curated Playlists**: Only display videos that meet happiness criteria

## Quick Start

```bash
# Install dependencies
poetry install

# Set up environment variables (.env file)
YTKEY=your_youtube_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Run the main pipeline to fetch and rate videos
poetry run python -m happytube.main

# Start the web player
poetry run python -m happytube.web.server

# Access the player at http://127.0.0.1:5000
```

## Web Player

The web player provides a controlled YouTube viewing experience:

- Embeds videos with disabled recommendations and related content
- Search and filter through your curated video collection
- Keyboard navigation (arrow keys or n/p)
- Auto-play next video option
- Fullscreen support

See `happytube/web/README.md` for more details.

## Pipeline Details

- Fetch videos from search - per category & length & order
- Assess from title & description whether they seem happy + add "publishable"
- Fetch details (?) (not sure whether entirely necessary now ?)
- [nth] fetch comments & assess whether happy
- [nth] statistics about channels - maybe we could rely more on known channels ?

### storage
- RequestLog to store
 - request id
 - request time
 - params (flattened)
 - num new results (after deduplication)
 - num happy results
- source data - json, in dirs per month & day, identified by type and ID
- processed data - parquet (?), after dropping duplicates. 

locally vs cloud ... mother duck ? blob ?


## TODO
- parse `thumbnails`, put the middle one into the df
- store stats about the call to claude - how long it took, tokens ...
- experiment with much smarter propmpt
- try varipus models, observe the happiness distribution


## tech ideas
- do it in several async loops with a queue in the middle ?
- structured logging into csvs (per day, week ?), eventually blob or so
 - wrapper ? to reduce repetition ... or DI ?


 parent log
 parent config

 log gets config as argument and stores its fields


## https://www.googleapis.com/youtube/v3/search

according to https://developers.google.com/youtube/v3/docs/search/list

part=snippet




in case i manage to identify channels channelId

maxResults=50

order=rating

q = general query - do we bother ?

regionCode=CZ

safeSearch=strict

topicId - look at the page, should be useful

type=video

videoCategoryId= as per https://developers.google.com/youtube/v3/docs/videoCategories

https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=CZ





