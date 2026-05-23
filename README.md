# Strata — Music Structure Decomposer

Strata takes any uploaded song and produces an "X-ray" of how it's built —
structurally, emotionally, and compositionally. Upload an MP3/WAV and get an
interactive analysis across four layers: section structure, emotional arc, music
theory, and DNA similarity to other songs.

Built for musicians, producers, music students, and audio engineers who want to
understand how a song is constructed.

> **Status:** Week 2 complete — HPSS-powered pipeline, template chord detection,
> music21 theory analysis, and a full composite emotional arc (Energy / Tension /
> Valence) with hit-moment detection are all live.
> DNA fingerprint (Week 3) and the Next.js frontend (Week 4) are next.

## What works today

- **Upload → analyze → poll** async API (`/analyze`), so long-running analysis
  never blocks the HTTP request.
- **HPSS** — the signal is split into harmonic and percussive layers on load.
  Beat tracking runs on the percussive layer (no harmonic phase confusion);
  chroma and spectral features run on the harmonic layer (no drum-hit bleed).
- **Key + mode detection** via Krumhansl-Schmuckler profiles on harmonic chroma.
- **Template-based chord detection** — cosine similarity against 24 major/minor
  triad templates on every 0.5 s grid cell, median-filtered to suppress flicker.
- **music21 theory analysis** — detected chord sequence is mapped to Roman
  numerals in the song's key; non-diatonic chords are flagged as `theory_moments`.
- **Progression summary** — first four unique Roman numerals (e.g. `i–VI–III–VII`).
- **Composite emotional arc (0–100):**
  - *Energy* — normalised RMS from the full mix.
  - *Tension* — spectral flux + |dRMS/dt|, Gaussian-smoothed.
  - *Valence* — chroma consonance score (interval weighting) + spectral centroid
    brightness proxy, Gaussian-smoothed.
- **Hit-moment detector** — finds the steepest rolling positive delta of
  (Energy + Onset Density) that immediately follows a low-energy window (the
  classic "drop"), with a structured plain-English explanation.
- **Rule-based section segmentation** — uniform 0.5 s grid segmentation using
  energy + onset + chroma, boundaries snapped to beats, labeled Intro / Verse /
  Pre-chorus / Chorus / Bridge / Outro by relative energy.
- **Memory-safe pipeline** — proactive `del` + `gc.collect()` after each major
  feature extraction stage; safe to run in 512 MB containers.

## Tech stack

- Python 3.11+ · FastAPI · uvicorn
- librosa · numpy · scipy · soundfile · music21

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
| **1** ✅ | Core audio pipeline: upload → features → segmentation → async API + JSON contract |
| **2** ✅ | HPSS, template chord detection, music21 Roman-numeral theory, composite emotional arc (Energy / Tension / Valence), hit-moment detector, memory-safe GC |
| **3** | DNA fingerprint: MERT-v1-95M embeddings for a seed song database, cosine-similarity top-3 match with plain-English reasons |
| **4** | Next.js 14 frontend: Wavesurfer.js structure timeline, Chart.js emotional arc, theory moments list, DNA match cards; deploy to Railway + Vercel |

## Notes

- `essentia` from the original spec is permanently replaced: it has no reliable
  Windows pip wheels. Key detection uses librosa's chromagram +
  Krumhansl-Schmuckler profiles instead, which is equivalent for this use case.
- `music21` is used **only** for Roman-numeral mapping of pre-detected chord
  labels — not for score ingestion or audio processing. This sidesteps its
  audio-analysis limitations and keeps it fast.
- Week 3 will use `m-a-p/MERT-v1-95M` (Hugging Face) for audio embeddings —
  no training required, runs on CPU, installs via `transformers`.
