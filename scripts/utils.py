import json
import os
import random
import time
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth


SPOTIFY_SCOPE = (
    "playlist-read-private "
    "playlist-modify-public "
    "playlist-modify-private "
    "user-library-read"
)
SPOTIFY_PAGE_LIMIT = 50
LIKED_SONGS_ALIASES = {
    "liked",
    "liked_songs",
    "liked-songs",
    "saved",
    "saved_tracks",
    "saved-tracks",
    "library",
    "collection",
    "spotify:collection:tracks",
    "https://open.spotify.com/collection/tracks",
}

load_dotenv()


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_sp():
    refresh_token = require_env("SPOTIFY_REFRESH_TOKEN")
    token_info = {
        "refresh_token": refresh_token,
        "access_token": None,
        "expires_at": 0,
        "scope": SPOTIFY_SCOPE,
    }

    auth_manager = SpotifyOAuth(
        client_id=require_env("SPOTIPY_CLIENT_ID"),
        client_secret=require_env("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SPOTIFY_SCOPE,
        cache_handler=MemoryCacheHandler(token_info=token_info),
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def load_json(path, default=None):
    file_path = Path(path)
    if not file_path.exists():
        return {} if default is None else default

    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{path} is not valid JSON: {exc}") from exc


def save_json(path, data):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
        f.write("\n")


def normalize_playlist_id(playlist_id):
    if not playlist_id:
        raise RuntimeError("Playlist ID is empty.")

    value = playlist_id.strip().strip("\"'")
    if "playlist/" in value:
        value = value.split("playlist/", 1)[1].split("?", 1)[0]
    elif value.startswith("spotify:playlist:"):
        value = value.split("spotify:playlist:", 1)[1]

    value = value.strip().rstrip("/")
    if not value:
        raise RuntimeError("Playlist ID is empty after normalization.")
    return value


def is_liked_songs_source(source_id):
    if not source_id:
        return False
    return source_id.strip().strip("\"'").lower().rstrip("/") in LIKED_SONGS_ALIASES


def get_vibe_slot_ids():
    slots = [os.getenv(f"VIBE_{i}_ID") for i in range(1, 6)]
    slots = [normalize_playlist_id(slot) for slot in slots if slot]
    if slots:
        return slots

    legacy_json = os.getenv("VIBE_SLOTS")
    if legacy_json:
        try:
            parsed = json.loads(legacy_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("VIBE_SLOTS must be a JSON array of playlist IDs.") from exc
        return [normalize_playlist_id(slot) for slot in parsed if slot]

    return []


def fetch_playlist_tracks(sp, playlist_id, limit=1000):
    if is_liked_songs_source(playlist_id):
        return fetch_saved_tracks(sp, limit=limit)

    playlist_id = normalize_playlist_id(playlist_id)

    page_fields = "total,items(track(id,name,artists(name)),item(id,name,type,artists(name))),next"
    first_page = sp.playlist_items(
        playlist_id,
        limit=SPOTIFY_PAGE_LIMIT,
        offset=0,
        fields=page_fields,
    )
    total = first_page.get("total", 0)
    if total <= 0:
        print(f"Archive playlist {playlist_id} has 0 items.")
        return []

    max_offset = max(0, total - limit)
    offset = random.randint(0, max_offset)
    print(f"Sampling {min(limit, total)} tracks from {total} available tracks at offset {offset}.")

    tracks = []
    if offset == 0:
        results = first_page
    else:
        results = sp.playlist_items(
            playlist_id,
            limit=SPOTIFY_PAGE_LIMIT,
            offset=offset,
            fields=page_fields,
        )

    while results and len(tracks) < limit:
        for item in results.get("items", []):
            track = item.get("track") or item.get("item")
            artists = track.get("artists", []) if track else []
            if track and track.get("id") and artists:
                tracks.append(
                    {
                        "id": track["id"],
                        "name": track.get("name", "Unknown title"),
                        "artist": artists[0].get("name", "Unknown artist"),
                    }
                )
                if len(tracks) >= limit:
                    break

        if results.get("next") and len(tracks) < limit:
            time.sleep(random.uniform(0.5, 1.5))
            results = sp.next(results)
        else:
            break

    print(f"Sampled {len(tracks)} tracks from archive playlist.")
    return tracks


def fetch_saved_tracks(sp, limit=1000):
    first_page = sp.current_user_saved_tracks(limit=1, offset=0)
    total = first_page.get("total", 0)
    if total <= 0:
        print("Current user's Liked Songs library has 0 tracks.")
        return []

    max_offset = max(0, total - limit)
    offset = random.randint(0, max_offset)
    print(f"Sampling {min(limit, total)} tracks from {total} liked songs at offset {offset}.")

    tracks = []
    results = sp.current_user_saved_tracks(limit=SPOTIFY_PAGE_LIMIT, offset=offset)

    while results and len(tracks) < limit:
        for item in results.get("items", []):
            track = item.get("track")
            artists = track.get("artists", []) if track else []
            if track and track.get("id") and artists:
                tracks.append(
                    {
                        "id": track["id"],
                        "name": track.get("name", "Unknown title"),
                        "artist": artists[0].get("name", "Unknown artist"),
                    }
                )
                if len(tracks) >= limit:
                    break

        if results.get("next") and len(tracks) < limit:
            time.sleep(random.uniform(0.5, 1.5))
            results = sp.next(results)
        else:
            break

    print(f"Sampled {len(tracks)} tracks from Liked Songs.")
    return tracks


def replace_playlist_tracks(sp, playlist_id, track_ids, limit=None):
    playlist_id = normalize_playlist_id(playlist_id)
    selected = track_ids[:limit] if limit else track_ids
    uris = [track_id if track_id.startswith("spotify:track:") else f"spotify:track:{track_id}" for track_id in selected]

    sp.playlist_replace_items(playlist_id, uris[:100])
    for index in range(100, len(uris), 100):
        sp.playlist_add_items(playlist_id, uris[index:index + 100])
