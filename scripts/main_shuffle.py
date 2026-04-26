import os
import random
from datetime import datetime, timedelta, timezone

from utils import get_sp, get_vibe_slot_ids, load_json, replace_playlist_tracks, save_json


VIBE_PLAYLIST_LIMIT = 50
COOLDOWN_DAYS = 30
RECENTLY_PLAYED_LIMIT = 50


def _parse_spotify_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _unique_track_ids(track_ids):
    return list(dict.fromkeys(track_id for track_id in track_ids if track_id))


def _shuffle_with_cooldown(track_ids, cooldown_ids):
    unique_ids = _unique_track_ids(track_ids)
    cooldown_set = set(cooldown_ids)
    fresh = [track_id for track_id in unique_ids if track_id not in cooldown_set]
    cooled = [track_id for track_id in unique_ids if track_id in cooldown_set]
    random.shuffle(fresh)
    random.shuffle(cooled)
    return fresh + cooled


def sync_play_history(sp):
    play_log = load_json("play_log.json", default=[])
    if not isinstance(play_log, list):
        play_log = []

    seen_events = {
        f"{entry.get('id')}|{entry.get('played_at')}"
        for entry in play_log
        if isinstance(entry, dict)
    }

    added = 0
    try:
        recent = sp.current_user_recently_played(limit=RECENTLY_PLAYED_LIMIT)
    except Exception as exc:
        print(f"Warning: could not fetch recently played tracks, cooldown unchanged. {exc}")
        cooldown_ids = load_json("history.json", default=[])
        return set(cooldown_ids if isinstance(cooldown_ids, list) else [])

    for item in recent.get("items", []):
        track = item.get("track") or {}
        track_id = track.get("id")
        played_at = item.get("played_at")
        event_key = f"{track_id}|{played_at}"
        if not track_id or not played_at or event_key in seen_events:
            continue

        play_log.append(
            {
                "id": track_id,
                "played_at": played_at,
                "name": track.get("name"),
                "artist": (track.get("artists") or [{}])[0].get("name"),
            }
        )
        seen_events.add(event_key)
        added += 1

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=COOLDOWN_DAYS)
    cooldown_ids = set()
    for entry in play_log:
        if not isinstance(entry, dict):
            continue
        played_at = _parse_spotify_time(entry.get("played_at"))
        if played_at and played_at >= cutoff and entry.get("id"):
            cooldown_ids.add(entry["id"])

    play_log.sort(key=lambda entry: entry.get("played_at", "") if isinstance(entry, dict) else "")
    save_json("play_log.json", play_log)
    save_json("history.json", sorted(cooldown_ids))
    print(f"Added {added} new play events. Active {COOLDOWN_DAYS}-day cooldown tracks: {len(cooldown_ids)}.")
    return cooldown_ids


def run_daily_shuffle():
    state = load_json("current_themes.json", default={})
    mappings = state.get("mappings", {})
    genres = state.get("genres", [])

    if not mappings:
        raise RuntimeError("current_themes.json has no mappings. Run the weekly intelligence sync first.")

    sp = get_sp()
    cooldown_ids = sync_play_history(sp)

    all_ids = [track_id for track_ids in mappings.values() for track_id in track_ids]
    ordered_master_ids = _shuffle_with_cooldown(all_ids, cooldown_ids)

    master_id = os.getenv("MASTER_SHUFFLE_ID")
    if not master_id:
        raise RuntimeError("Missing required environment variable: MASTER_SHUFFLE_ID")

    replace_playlist_tracks(sp, master_id, ordered_master_ids, limit=1000)
    print(f"Updated master shuffle with {min(len(ordered_master_ids), 1000)} tracks.")

    slots = get_vibe_slot_ids()
    if len(slots) < min(len(genres), 5):
        raise RuntimeError("Set VIBE_1_ID through VIBE_5_ID for the daily vibe playlists.")

    for index, vibe in enumerate(genres[:5]):
        ids = list(mappings.get(vibe, []))
        selection = _shuffle_with_cooldown(ids, cooldown_ids)[:VIBE_PLAYLIST_LIMIT]
        if not selection:
            print(f"Skipping {vibe}: no mapped tracks.")
            continue

        playlist_id = slots[index]
        replace_playlist_tracks(sp, playlist_id, selection)
        sp.playlist_change_details(
            playlist_id,
            name=f"Vibe: {vibe}",
            description=f"AI theme refreshed from SpotShuffle: {vibe}",
        )
        print(f"Updated vibe slot {index + 1}: {vibe} ({len(selection)} tracks).")


if __name__ == "__main__":
    run_daily_shuffle()
