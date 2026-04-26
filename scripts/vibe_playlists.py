import random

from utils import get_sp, get_vibe_slot_ids, load_json, replace_playlist_tracks


VIBE_PLAYLIST_LIMIT = 50


def update_vibes():
    sp = get_sp()
    theme_data = load_json("current_themes.json", default={})
    genres = theme_data.get("genres", [])
    mappings = theme_data.get("mappings", {})
    slot_ids = get_vibe_slot_ids()

    if not mappings:
        raise RuntimeError("current_themes.json has no mappings. Run scripts/intel_sync.py first.")
    if len(slot_ids) < min(len(genres), 5):
        raise RuntimeError("Set VIBE_1_ID through VIBE_5_ID for the vibe playlists.")

    for index, genre in enumerate(genres[:5]):
        tracks = list(mappings.get(genre, []))
        random.shuffle(tracks)
        if not tracks:
            continue

        playlist_id = slot_ids[index]
        sp.playlist_change_details(playlist_id, name=f"Vibe: {genre}")
        selection = tracks[:VIBE_PLAYLIST_LIMIT]
        replace_playlist_tracks(sp, playlist_id, selection)
        print(f"Updated vibe slot {index + 1}: {genre} ({len(selection)} tracks).")


if __name__ == "__main__":
    update_vibes()
