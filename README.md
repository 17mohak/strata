# Strata — Music Structure Decomposer

Strata takes any uploaded song and produces an "X-ray" of how it's built —
structurally, emotionally, and compositionally. Upload an MP3/WAV and get an
interactive analysis across four layers: section structure, emotional arc, music
theory, and DNA similarity to other songs.

Built for musicians, producers, music students, and audio engineers who want to
understand how a song is constructed.

> **Status:** Week 4 complete — full-stack app with dark music-app frontend,
> interactive waveform with section overlays, emotional arc chart, theory
> moments, DNA match cards, and a 50-song FAISS-powered similarity engine.

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
- **DNA fingerprint engine** — 73-dimensional feature vector (chroma, tonality,
  timbre, brightness, width, rolloff, rhythm, energy contour, percussiveness,
  spectral flux, harmonic stability) with FAISS IndexFlatIP cosine-similarity
  search over a z-score-standardised seed database.
- **Seed database** — 50 iconic songs across decades and genres, seeded from
  iTunes 30-second previews via an automated pipeline (`seed_deezer.py`).
  Scales to 10,000+ songs via CSV input on Kaggle.
- **Per-group explainability** — match reasons explain *which* sonic dimensions
  drove the similarity (e.g. "Both tracks share timbral fingerprint and
  harmonic character"), with a dominant match type (harmonic / timbral /
  rhythmic / tension_curve).

## Tech stack

**Backend:** Python 3.11+ · FastAPI · uvicorn · librosa · numpy · scipy · soundfile · music21 · FAISS · PyAV

**Frontend:** Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · wavesurfer.js · Chart.js · Lucide Icons

## Project structure

```
strata/
├─ backend/
│  ├─ main.py           # FastAPI app: /analyze (POST) + /analyze/{job_id} (GET)
│  ├─ analyzer.py       # librosa analysis pipeline + segmentation
│  ├─ dna_engine.py     # FAISS-backed DNA fingerprint engine + SQLite store
│  ├─ seed_deezer.py    # Batch seeder: iTunes API -> preview -> features -> DB
│  ├─ seed.db           # Pre-built seed database (50 songs, git-ignored)
│  └─ requirements.txt
├─ frontend/
│  ├─ app/
│  │  ├─ components/    # FileUpload, WaveformPlayer, EmotionalArcChart,
│  │  │                 # DNAMatches, TheoryMoments, Sections, MetaBar
│  │  ├─ layout.tsx     # Root layout with dark theme
│  │  ├─ page.tsx       # Main upload -> analysis -> results page
│  │  └─ globals.css    # Dark music-app theme
│  ├─ lib/
│  │  ├─ api.ts         # Upload + polling API client
│  │  └─ types.ts       # TypeScript types matching backend contract
│  └─ package.json
└─ README.md
```

## Setup

```bash
# Backend
cd backend
python -m venv .venv
# Windows (PowerShell): .\.venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt
python seed_deezer.py          # seed the DNA database (50 songs, ~2 min)

# Frontend
cd ../frontend
npm install
```

## Run

```bash
# Terminal 1 — Backend (port 8000)
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend (port 3000)
cd frontend
npm run dev
```

Open `http://localhost:3000` in your browser.

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
  "dna_matches": [
    {
      "title": "No Woman, No Cry",
      "artist": "Bob Marley & The Wailers",
      "similarity": 0.58,
      "match_reason": "Both tracks share rhythmic density and drive and frequency distribution.",
      "match_type": "timbral",
      "album_art_url": "https://..."
    }
  ]
}
```

## Roadmap

| Week | Scope |
|------|-------|
| **1** ✅ | Core audio pipeline: upload → features → segmentation → async API + JSON contract |
| **2** ✅ | HPSS, template chord detection, music21 Roman-numeral theory, composite emotional arc (Energy / Tension / Valence), hit-moment detector, memory-safe GC |
| **3** ✅ | DNA fingerprint: 73D feature vectors, FAISS cosine-similarity, z-score standardisation, 50-song iTunes seed DB, per-group explainability |
| **4** ✅ | Next.js 16 frontend: dark music-app UI, wavesurfer.js waveform + section overlay, Chart.js emotional arc, theory moments, DNA match cards with album art, drag-and-drop upload |

## Notes

- `essentia` from the original spec is permanently replaced: it has no reliable
  Windows pip wheels. Key detection uses librosa's chromagram +
  Krumhansl-Schmuckler profiles instead, which is equivalent for this use case.
- `music21` is used **only** for Roman-numeral mapping of pre-detected chord
  labels — not for score ingestion or audio processing. This sidesteps its
  audio-analysis limitations and keeps it fast.
- Week 3 uses hand-crafted 73D feature vectors (chroma, MFCC, spectral stats,
  energy contour) instead of MERT embeddings — lighter weight, no GPU needed,
  and the per-group explainability gives richer match reasons than a single
  opaque embedding would.
- Seed database ships with 50 songs; scale to 10K+ by providing a CSV to
  `seed_deezer.py --input songs.csv` (designed for Kaggle batch runs).
- iTunes Search API is used instead of Deezer (Deezer is geo-restricted in
  India). PyAV handles M4A→WAV conversion for the iTunes AAC previews.
