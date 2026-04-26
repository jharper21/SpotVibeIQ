import os
import random

from utils import get_sp, get_vibe_slot_ids, load_json, replace_playlist_tracks


VIBE_PLAYLIST_LIMIT = 50


def run_daily_shuffle():
    state = load_json("current_themes.json", default={})
    mappings = state.get("mappings", {})
    genres = state.get("genres", [])

    if not mappings:
        raise RuntimeError("current_themes.json has no mappings. Run the weekly intelligence sync first.")

    sp = get_sp()

    all_ids = [track_id for track_ids in mappings.values() for track_id in track_ids]
    random.shuffle(all_ids)

    master_id = os.getenv("MASTER_SHUFFLE_ID")
    if not master_id:
        raise RuntimeError("Missing required environment variable: MASTER_SHUFFLE_ID")

    replace_playlist_tracks(sp, master_id, all_ids, limit=1000)
    print(f"Updated master shuffle with {min(len(all_ids), 1000)} tracks.")

    slots = get_vibe_slot_ids()
    if len(slots) < min(len(genres), 5):
        raise RuntimeError("Set VIBE_1_ID through VIBE_5_ID for the daily vibe playlists.")

    for index, vibe in enumerate(genres[:5]):
        ids = list(mappings.get(vibe, []))
        random.shuffle(ids)
        selection = ids[:VIBE_PLAYLIST_LIMIT]
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
