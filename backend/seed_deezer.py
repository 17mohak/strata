#!/usr/bin/env python3
"""Populate the seed database from iTunes 30-second previews.

Usage
-----
# Process the built-in starter list (50 iconic songs):
  python seed_deezer.py

# Process a CSV file (artist,title per line):
  python seed_deezer.py --input songs.csv

# Limit to first 10 for testing:
  python seed_deezer.py --limit 10

# Adjust inter-request delay (default 0.5 s):
  python seed_deezer.py --delay 0.8

The iTunes Search API requires no authentication and works worldwide.
Keep the delay at >= 0.5 s to be a good citizen.
"""

import argparse
import csv
import gc
import io
import os
import sys
import tempfile
import time

import av
import numpy as np
import requests

from dna_engine import extract_from_audio, init_db, insert_song

DB_DEFAULT = os.path.join(os.path.dirname(__file__), "seed.db")

ITUNES_SEARCH = "https://itunes.apple.com/search"

DEFAULT_SONGS: list[tuple[str, str]] = [
    ("Queen", "Bohemian Rhapsody"),
    ("Billie Eilish", "Ocean Eyes"),
    ("The Beatles", "Hey Jude"),
    ("Adele", "Rolling in the Deep"),
    ("Ed Sheeran", "Shape of You"),
    ("Nirvana", "Smells Like Teen Spirit"),
    ("Michael Jackson", "Billie Jean"),
    ("Daft Punk", "Get Lucky"),
    ("The Weeknd", "Blinding Lights"),
    ("Fleetwood Mac", "Dreams"),
    ("Tame Impala", "The Less I Know the Better"),
    ("Radiohead", "Creep"),
    ("Arctic Monkeys", "Do I Wanna Know?"),
    ("Beyonce", "Halo"),
    ("Drake", "Hotline Bling"),
    ("Taylor Swift", "Blank Space"),
    ("Kendrick Lamar", "HUMBLE."),
    ("Amy Winehouse", "Rehab"),
    ("Coldplay", "Fix You"),
    ("Imagine Dragons", "Radioactive"),
    ("Post Malone", "Circles"),
    ("Bruno Mars", "Uptown Funk"),
    ("Dua Lipa", "Levitating"),
    ("Hozier", "Take Me to Church"),
    ("Lorde", "Royals"),
    ("Frank Ocean", "Thinkin Bout You"),
    ("SZA", "Kill Bill"),
    ("Harry Styles", "As It Was"),
    ("Olivia Rodrigo", "drivers license"),
    ("Rihanna", "Umbrella"),
    ("Kanye West", "Stronger"),
    ("Eminem", "Lose Yourself"),
    ("Lady Gaga", "Bad Romance"),
    ("Ariana Grande", "thank u, next"),
    ("The Chainsmokers", "Closer"),
    ("Maroon 5", "Sugar"),
    ("Sia", "Chandelier"),
    ("Calvin Harris", "Summer"),
    ("David Bowie", "Heroes"),
    ("Pink Floyd", "Comfortably Numb"),
    ("Led Zeppelin", "Stairway to Heaven"),
    ("Eagles", "Hotel California"),
    ("Bob Marley", "No Woman No Cry"),
    ("Stevie Wonder", "Superstition"),
    ("Prince", "Purple Rain"),
    ("Whitney Houston", "I Will Always Love You"),
    ("Elton John", "Rocket Man"),
    ("Bon Jovi", "Livin' on a Prayer"),
    ("Guns N' Roses", "Sweet Child O' Mine"),
    ("AC/DC", "Back in Black"),
]


def search_itunes(artist: str, title: str) -> dict | None:
    """Search iTunes and return the first song match (or None)."""
    try:
        r = requests.get(
            ITUNES_SEARCH,
            params={
                "term": f"{artist} {title}",
                "media": "music",
                "entity": "song",
                "limit": 5,
            },
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        for hit in results:
            if hit.get("previewUrl"):
                return hit
        return results[0] if results else None
    except Exception as exc:
        print(f"  [WARN] iTunes search failed for {artist} - {title}: {exc}")
        return None


def m4a_to_wav(m4a_bytes: bytes) -> bytes:
    """Decode M4A/AAC bytes to WAV using PyAV."""
    input_buf = io.BytesIO(m4a_bytes)
    output_buf = io.BytesIO()

    with av.open(input_buf, format="mp4") as in_container:
        audio_stream = in_container.streams.audio[0]
        sample_rate = audio_stream.rate or 22050
        layout = audio_stream.layout

        with av.open(output_buf, mode="w", format="wav") as out_container:
            out_stream = out_container.add_stream("pcm_s16le", rate=sample_rate)
            out_stream.layout = layout

            for frame in in_container.decode(audio=0):
                frame.pts = None
                for packet in out_stream.encode(frame):
                    out_container.mux(packet)
            for packet in out_stream.encode(None):
                out_container.mux(packet)

    return output_buf.getvalue()


def download_preview(url: str, dest: str) -> bool:
    """Download a preview, convert M4A to WAV if needed, save to dest."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()

        if url.endswith(".m4a") or b"ftyp" in r.content[:32]:
            wav_data = m4a_to_wav(r.content)
            with open(dest, "wb") as f:
                f.write(wav_data)
        else:
            with open(dest, "wb") as f:
                f.write(r.content)
        return True
    except Exception as exc:
        print(f"  [WARN] Preview download/convert failed: {exc}")
        return False


def load_csv(path: str) -> list[tuple[str, str]]:
    songs: list[tuple[str, str]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            artist, title = row[0].strip(), row[1].strip()
            if artist.lower() == "artist" and title.lower() == "title":
                continue
            if artist and title:
                songs.append((artist, title))
    return songs


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Strata DNA database from iTunes previews.")
    parser.add_argument("--input", "-i", help="CSV file (artist,title per line)")
    parser.add_argument("--db",    default=DB_DEFAULT, help="SQLite output path")
    parser.add_argument("--limit", type=int, default=0, help="Max songs (0 = all)")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    args = parser.parse_args()

    songs = load_csv(args.input) if args.input else DEFAULT_SONGS
    if args.limit > 0:
        songs = songs[: args.limit]

    print(f"Processing {len(songs)} songs -> {args.db}")
    init_db(args.db)

    ok = 0
    skip = 0
    fail = 0

    for i, (artist, title) in enumerate(songs, 1):
        tag = f"[{i}/{len(songs)}]"
        print(f"{tag} {artist} -- {title} ...", end=" ", flush=True)

        hit = search_itunes(artist, title)
        if hit is None:
            print("NOT FOUND on iTunes")
            fail += 1
            time.sleep(args.delay)
            continue

        track_id    = hit.get("trackId", 0)
        d_title     = hit.get("trackName", title)
        d_artist    = hit.get("artistName", artist)
        preview_url = hit.get("previewUrl", "")
        album_art   = hit.get("artworkUrl100", "")

        if not preview_url:
            print("no preview URL")
            fail += 1
            time.sleep(args.delay)
            continue

        ext = ".wav"
        tmp = os.path.join(tempfile.gettempdir(), f"strata_seed_{track_id}{ext}")
        try:
            if not download_preview(preview_url, tmp):
                fail += 1
                time.sleep(args.delay)
                continue

            meta, vec = extract_from_audio(tmp)

            if np.all(vec == 0):
                print("zero vector -- skipping")
                skip += 1
                continue

            insert_song(
                args.db,
                deezer_id=track_id,
                title=d_title,
                artist=d_artist,
                genre=None,
                album_art_url=album_art or None,
                key=meta["key"],
                mode=meta["mode"],
                bpm=meta["bpm"],
                feature_vector=vec,
            )
            print(f"OK  key={meta['key']} {meta['mode']}  bpm={meta['bpm']}")
            ok += 1

        except Exception as exc:
            print(f"FAIL: {exc}")
            fail += 1
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
            gc.collect()

        time.sleep(args.delay)

    print(f"\nDone: {ok} added, {skip} skipped, {fail} failed  ->  {args.db}")


if __name__ == "__main__":
    main()
