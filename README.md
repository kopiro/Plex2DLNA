# Plex2DLNA

Automatically redirects active Plex streams to a LG webOS TV's native media player. Fetches the current stream from Tautulli, terminates the Plex session, and launches direct playback via `luna-send-pub`.

## Why?

It's sad that it has to be this way in 2026...

The Plex app is great for discovering content, but even on good remote boxes like Apple TV it can be buggy and slow to load. By redirecting the stream to the TV's native player, you get better format support on audio and video, and a more seamless experience.

If you want, you can also use [Magic Mapper](https://github.com/andrewfraley/magic_mapper) to map a key on your remote to trigger the script, so you can start watching with a single button press - alternatively, you can run it via CRON or add a script to Home Assistant.

## How It Works

1. Queries Tautulli for active Plex sessions
2. Filters by allowed users
3. Extracts the direct file stream URL from Plex
4. Terminates the original Plex session and marks it as watched
5. Launches the media on the TV via webOS `mediadiscovery` app

## Requirements

- Python 3
- LG webOS TV (with `luna-send-pub` available)
- [Tautulli](https://tautulli.com/) monitoring your Plex server

## Setup

1. Copy `plex2dlna.py` and `plex2dlna.json` to the TV
2. Edit `plex2dlna.json`:

```json
{
  "tautulli_url": "http://<tautulli-host>:8181/api/v2",
  "tautulli_api_key": "<your-tautulli-api-key>",
  "plex_url": "http://<plex-host>:32400",
  "allowed_users": ["username1", "username2"]
}
```

| Key | Description |
|-----|-------------|
| `tautulli_url` | Tautulli API base URL |
| `tautulli_api_key` | Tautulli API key (Settings > Web Interface) |
| `plex_url` | Plex server base URL |
| `allowed_users` | Usernames whose streams can be redirected |

## Usage

```bash
# Redirect the first active allowed stream to the TV
python3 plex2dlna.py

# Debug mode -- dumps session JSON without playing
python3 plex2dlna.py --debug
```

## Supported Formats

mkv, mp4, avi, mov, wmv, ts, m4v
