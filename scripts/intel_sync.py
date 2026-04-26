import json
import os
from collections import defaultdict

from openai import OpenAI

from utils import fetch_playlist_tracks, get_sp, require_env, save_json


DEFAULT_MODEL = "gpt-4o-mini"
THEME_COUNT = 5
GENRE_DIVERSITY_RULES = (
    "The five vibe names must be meaningfully different from each other. "
    "Avoid near-synonyms, repeated mood words, repeated genre roots, or five variants of the same energy. "
    "Prefer a broad spread across tempo, mood, era, scene, instrumentation, and listening context. "
    "Each name should create a distinct playlist lane."
)


def _json_from_response(response):
    content = response.choices[0].message.content or "{}"
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
    return json.loads(content)


def _track_prompt_rows(tracks):
    return [{"id": t["id"], "name": t["name"], "artist": t["artist"]} for t in tracks]


def discover_genres(client, model, tracks):
    sample = _track_prompt_rows(tracks[:200])
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a music curator. Return strict JSON only. "
                    "Discover exactly five concise playlist vibe names from the supplied tracks. "
                    f"{GENRE_DIVERSITY_RULES}"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Return JSON in this shape: {\"genres\": [\"name1\", \"name2\", \"name3\", \"name4\", \"name5\"]}.\n"
                    "Before choosing the final names, force them to be distinct enough that a listener would immediately understand why each playlist exists.\n"
                    f"Tracks: {json.dumps(sample, ensure_ascii=True)}"
                ),
            },
        ],
    )
    data = _json_from_response(response)
    genres = [str(item).strip() for item in data.get("genres", []) if str(item).strip()]
    normalized = {genre.lower().replace("&", "and") for genre in genres}
    if len(genres) < THEME_COUNT:
        raise RuntimeError(f"OpenAI returned {len(genres)} genres; expected {THEME_COUNT}.")
    if len(normalized) < THEME_COUNT:
        raise RuntimeError("OpenAI returned duplicate or near-duplicate genre names.")
    return genres[:THEME_COUNT]


def classify_tracks(client, model, genres, tracks, batch_size=100):
    mappings = {genre: [] for genre in genres}

    for start in range(0, len(tracks), batch_size):
        batch = tracks[start:start + batch_size]
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {
                "role": "system",
                "content": (
                    "You classify tracks into exactly one of the allowed genres. "
                    "Return strict JSON only. Use track IDs exactly as provided. "
                    "Use the full spread of allowed genres when the tracks support it; do not collapse everything into one or two similar buckets."
                ),
            },
                {
                    "role": "user",
                    "content": (
                        "Return JSON in this shape: {\"assignments\": [{\"id\": \"track_id\", \"genre\": \"allowed genre\"}]}.\n"
                        f"Allowed genres: {json.dumps(genres, ensure_ascii=True)}\n"
                        f"Tracks: {json.dumps(_track_prompt_rows(batch), ensure_ascii=True)}"
                    ),
                },
            ],
        )
        data = _json_from_response(response)
        grouped = defaultdict(list)
        for item in data.get("assignments", []):
            track_id = str(item.get("id", "")).strip()
            genre = str(item.get("genre", "")).strip()
            if track_id and genre in mappings:
                grouped[genre].append(track_id)

        for genre, ids in grouped.items():
            mappings[genre].extend(ids)
        print(f"Classified {min(start + batch_size, len(tracks))}/{len(tracks)} tracks.")

    return mappings


def run_intel_sync():
    sample_limit = int(os.getenv("SYNC_SAMPLE_LIMIT", "1000"))
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    sp = get_sp()
    archive_source = require_env("ARCHIVE_PLAYLIST_ID")
    tracks = fetch_playlist_tracks(sp, archive_source, limit=sample_limit)
    if not tracks:
        raise RuntimeError(
            "No tracks were fetched from ARCHIVE_PLAYLIST_ID. "
            "Set it to a Spotify playlist ID/URL with tracks, or set it to 'liked' to use Liked Songs. "
            "If it is a private playlist, the refresh-token user must own or collaborate on it."
        )

    client = OpenAI(api_key=require_env("OPENAI_API_KEY"))
    genres = discover_genres(client, model, tracks)
    mappings = classify_tracks(client, model, genres, tracks)

    state = {
        "genres": genres,
        "mappings": mappings,
        "source_track_count": len(tracks),
        "model": model,
    }
    save_json("current_themes.json", state)
    print(f"Saved current_themes.json with {len(genres)} genres and {len(tracks)} sampled tracks.")


if __name__ == "__main__":
    run_intel_sync()
