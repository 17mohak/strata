# Strata — Music Structure Decomposer

Strata takes any uploaded song and produces an "X-ray" of how it's built —
structurally, emotionally, and compositionally. Upload an MP3/WAV and get an
interactive analysis across four layers: section structure, emotional arc, music
theory, and DNA similarity to other songs.

Built for musicians, producers, music students, and audio engineers who want to
understand how a song is constructed.

> **Status:** Week 1 — the core audio pipeline and analysis API are complete.
> Emotional arc, theory engine, and DNA fingerprint are stubbed and land in
> later milestones (see [Roadmap](#roadmap)).

## What works today

- **Upload → analyze → poll** async API (`/analyze`), so long-running analysis
  never blocks the HTTP request.
- **librosa pipeline:** audio load, tempo + beat tracking, RMS energy, onset
  strength, chromagram.
- **Key + mode detection** via Krumhansl-Schmuckler key profiles.
- **Rule-based section segmentation** (no ML): the song is cut on a uniform time
  grid using energy, onset density, and harmonic content, then each section is
  labeled Intro / Verse / Pre-chorus / Chorus / Bridge / Outro by its relative
  energy. Boundaries snap to detected beats.

## Tech stack

- Python 3.11+ · FastAPI · uvicorn
- librosa · numpy · scipy · soundfile

## Project structure

```
strata/
├─ backend/
│  ├─ main.py           # FastAPI app: /analyze (POST) + /analyze/{job_id} (GET)
│  ├─ analyzer.py       # librosa analysis pipeline + segmentation
│  └─ requirements.txt
└─ README.md
```

## Setup

```bash
cd backend
python -m venv .venv
# Windows (PowerShell): .\.venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is then available at `http://127.0.0.1:8000`.

## API

### `POST /analyze`

Accepts a multipart file upload (MP3 or WAV, max 20 MB). Returns a job ID
immediately and processes in the background.

```bash
curl -F "file=@song.mp3" http://127.0.0.1:8000/analyze
# { "job_id": "abc123", "status": "processing" }
```

### `GET /analyze/{job_id}`

Poll until `status` is `complete` (or `error`). Poll every ~2 seconds.

```bash
curl http://127.0.0.1:8000/analyze/abc123
```

Complete response (abridged):

```json
{
  "job_id": "abc123",
  "status": "complete",
  "meta": {
    "title": null,
    "duration_seconds": 200,
    "tempo": 171,
    "key": "Ab",
    "mode": "major",
    "time_signature": "4/4",
    "progression": null
  },
  "segments": [
    { "label": "Intro", "cls": "seg-intro", "start_seconds": 0, "end_seconds": 22, "notes": "..." }
  ],
  "beats": [0.35, 0.70, 1.05],
  "emotional_arc": null,
  "hit_moment": null,
  "theory_moments": [],
  "dna_matches": []
}
```

Fields returning `null` / `[]` (emotional arc, hit moment, theory moments, DNA
matches) are populated in later milestones.

## Roadmap

| Week | Scope |
|------|-------|
| **1** ✅ | Core audio pipeline: upload → features → segmentation → API + JSON contract |
| 2 | Emotional arc (energy/tension/valence), hit-moment detection, music theory engine (music21) |
| 3 | DNA fingerprint: embeddings for a seed song database + cosine-similarity matching |
| 4 | Next.js frontend (Wavesurfer.js timeline, Chart.js arc), polish, deploy |

## Notes

- `essentia` and `music21` from the original spec are intentionally deferred:
  `essentia` has no reliable Windows wheels, so Week 1 key detection uses
  librosa's chromagram instead. `music21` arrives with the Week 2 theory engine.
