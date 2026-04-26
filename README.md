# SpotVibeIQ

SpotVibeIQ samples a large Spotify archive playlist, uses OpenAI to discover five current listening themes, and updates one master shuffle playlist plus five rotating vibe playlists from GitHub Actions.

## How It Runs

```text
Weekly Intelligence Sync
  1. Reads ARCHIVE_PLAYLIST_ID.
  2. Samples up to SYNC_SAMPLE_LIMIT tracks.
  3. Uses OpenAI to discover five vibe names.
  4. Classifies sampled tracks into those vibes.
  5. Writes current_themes.json back to the repo.

Daily Vibe Shuffle
  1. Reads current_themes.json.
  2. Updates MASTER_SHUFFLE_ID with up to 1,000 shuffled tracks.
  3. Updates VIBE_1_ID through VIBE_5_ID with up to 50 tracks each.
  4. Renames vibe playlists in Spotify.
```

## Project Structure

```text
SpotShuffle/
|-- .github/workflows/
|   |-- intel_sync.yml      # Weekly OpenAI theme discovery
|   `-- daily_music.yml     # Daily Spotify playlist updates
|-- scripts/
|   |-- utils.py            # Shared Spotify, JSON, and playlist helpers
|   |-- intel_sync.py       # Weekly AI state generator
|   |-- main_shuffle.py     # Daily master/vibe playlist updater
|   `-- vibe_playlists.py   # Manual vibe-only updater
|-- current_themes.json     # Generated theme and mapping state
|-- requirements.txt
`-- .env.example
```

## GitHub Secrets

Add these in **Settings > Secrets and variables > Actions**:

| Secret | Purpose |
| --- | --- |
| `CLIENT_ID` | Spotify app client ID |
| `CLIENT_SECRET` | Spotify app client secret |
| `REFRESH_TOKEN` | Spotify refresh token generated from local auth |
| `OPENAI_API_KEY` | OpenAI API key |
| `ARCHIVE_PLAYLIST_ID` | Source Spotify playlist to sample, or `liked` for Liked Songs |
| `MASTER_SHUFFLE_ID` | Target playlist for the 1,000-track shuffle |
| `VIBE_1_ID` | Target vibe slot 1 |
| `VIBE_2_ID` | Target vibe slot 2 |
| `VIBE_3_ID` | Target vibe slot 3 |
| `VIBE_4_ID` | Target vibe slot 4 |
| `VIBE_5_ID` | Target vibe slot 5 |

The workflows set `SPOTIPY_REDIRECT_URI` to `http://127.0.0.1:8888/callback`. Use that exact redirect URI in your Spotify Developer Dashboard and when generating the refresh token.

`ARCHIVE_PLAYLIST_ID` must be a real Spotify playlist ID/URL that contains tracks. If you want to sample your Spotify Liked Songs instead, set `ARCHIVE_PLAYLIST_ID` to `liked`.

## Local Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in `.env`, then run the weekly sync before the daily shuffle:

```powershell
python scripts/intel_sync.py
python scripts/main_shuffle.py
```

## Notes

- `current_themes.json` must contain both `genres` and `mappings`. The daily workflow fails clearly if the weekly sync has not populated mappings yet.
- `OPENAI_MODEL` is optional. If unset, `scripts/intel_sync.py` uses `gpt-4o-mini`.
- `SYNC_SAMPLE_LIMIT` is optional. If unset, the weekly sync samples 1,000 tracks.
- Weekly theme discovery asks OpenAI for five distinct playlist lanes across mood, tempo, era, instrumentation, and listening context.
