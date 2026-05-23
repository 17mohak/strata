"""Week 1 audio analysis pipeline.

Loads audio with librosa, extracts tempo / beats / RMS energy / onset strength /
chroma, detects key via the Krumhansl-Schmuckler profiles, and runs rule-based
section segmentation. No ML models — everything here is signal processing plus
heuristics, which is the Week 1 scope.

Returns a dict shaped to the API contract in CONTEXT.md. Week 2/3 fields
(emotional_arc, hit_moment, theory_moments, dna_matches) are stubbed out.
"""

import numpy as np
import librosa

HOP = 512
SR = 22050

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler key profiles (major / minor key strength per scale degree).
MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

# Section label -> frontend CSS class (see CONTEXT.md).
CLS = {
    "Intro": "seg-intro",
    "Verse": "seg-verse",
    "Pre-chorus": "seg-prechorus",
    "Chorus": "seg-chorus",
    "Bridge": "seg-bridge",
    "Outro": "seg-outro",
}


def run_analysis(path: str) -> dict:
    y, sr = librosa.load(path, sr=SR, mono=True)
    if y.size == 0:
        raise ValueError("Audio file is empty or could not be decoded.")

    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)

    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)  # expensive; computed once

    key, mode = _detect_key(chroma)

    segments = _segment(rms, onset_env, chroma, beat_times, duration, sr)

    return {
        "meta": {
            "title": None,
            "duration_seconds": round(duration, 2),
            "tempo": round(tempo),
            "key": key,
            "mode": mode,
            "time_signature": "4/4",  # detection deferred; 4/4 is the safe default
            "progression": None,  # Week 2 (music21)
        },
        "segments": segments,
        "beats": [round(float(t), 3) for t in beat_times],
        "emotional_arc": None,  # Week 2
        "hit_moment": None,  # Week 2
        "theory_moments": [],  # Week 2
        "dna_matches": [],  # Week 3
    }


def _detect_key(chroma_full: np.ndarray) -> tuple[str, str]:
    chroma = chroma_full.mean(axis=1)
    best_score = -np.inf
    best = ("C", "major")
    for i in range(12):
        maj = np.corrcoef(np.roll(MAJOR_PROFILE, i), chroma)[0, 1]
        minr = np.corrcoef(np.roll(MINOR_PROFILE, i), chroma)[0, 1]
        if maj > best_score:
            best_score, best = maj, (NOTES[i], "major")
        if minr > best_score:
            best_score, best = minr, (NOTES[i], "minor")
    return best


def _segment(rms, onset_env, chroma, beat_times, duration, sr):
    """Rule-based section segmentation on a fixed ~0.5s time grid.

    Stack energy + onset density + harmonic (chroma) content on a uniform grid
    that always spans the whole song (so beatless intros/outros still get
    covered), cut into k contiguous sections via agglomerative clustering, snap
    boundaries to nearby beats, then label each section by its relative energy
    (lowest at the edges -> intro/outro, high recurring -> chorus, etc.).
    """
    if duration < 12:
        return [_make_segment("Verse", 0.0, duration, rms, onset_env, beat_times, sr, 1)]

    m = min(len(rms), len(onset_env), chroma.shape[1])
    rms_m, onset_m, chroma_m = rms[:m], onset_env[:m], chroma[:, :m]
    frame_times = librosa.frames_to_time(np.arange(m), sr=sr, hop_length=HOP)

    # Downsample to a ~0.5s grid for stable, non-jittery boundaries.
    win = max(1, int(round(0.5 * sr / HOP)))
    starts = np.arange(0, m, win)
    rms_g = np.array([rms_m[i : i + win].mean() for i in starts])
    onset_g = np.array([onset_m[i : i + win].mean() for i in starts])
    chroma_g = np.array([chroma_m[:, i : i + win].mean(axis=1) for i in starts]).T
    grid_times = frame_times[starts]

    feat = np.vstack([_norm(rms_g), _norm(onset_g), librosa.util.normalize(chroma_g, axis=0)])

    k = int(np.clip(round(duration / 22.0), 4, 8))
    k = min(k, feat.shape[1] - 1)
    bounds = librosa.segment.agglomerative(feat, k)  # grid indices of section starts

    # Boundary grid indices -> times, snapped to nearby beats, anchored 0..duration.
    bound_times = [0.0]
    for b in bounds:
        t = float(grid_times[min(b, len(grid_times) - 1)])
        t = _snap_to_beat(t, beat_times)
        if t - bound_times[-1] > 3.0:  # drop near-zero-length sections
            bound_times.append(t)
    bound_times.append(duration)

    # Per-section mean energy, used for labeling.
    energies = np.array(
        [
            _window_mean(rms_g, grid_times, bound_times[i], bound_times[i + 1])
            for i in range(len(bound_times) - 1)
        ]
    )
    n = len(energies)

    high = np.percentile(energies, 60)
    labels = _assign_labels(energies, high, n)

    counts: dict[str, int] = {}
    segments = []
    for i, base in enumerate(labels):
        counts[base] = counts.get(base, 0) + 1
        idx = counts[base] if base in ("Verse", "Chorus") else None
        segments.append(
            _make_segment(
                base,
                bound_times[i],
                bound_times[i + 1],
                rms,
                onset_env,
                beat_times,
                sr,
                idx,
            )
        )
    return segments


def _assign_labels(energies, high, n):
    """Map per-section energy to musical section labels (heuristic)."""
    labels = []
    for i, e in enumerate(energies):
        if i == 0:
            labels.append("Intro")
        elif i == n - 1:
            labels.append("Outro")
        elif e >= high:
            labels.append("Chorus")
        else:
            labels.append("Verse")

    # A low-energy, non-chorus section in the back half (after a chorus) reads as a bridge.
    seen_chorus = False
    for i in range(1, n - 1):
        if labels[i] == "Chorus":
            seen_chorus = True
        elif seen_chorus and i >= n * 0.55 and energies[i] < np.median(energies):
            labels[i] = "Bridge"
            break

    # A rising verse immediately before a chorus reads as a pre-chorus.
    for i in range(1, n - 1):
        if (
            labels[i] == "Verse"
            and labels[i + 1] == "Chorus"
            and energies[i] > energies[i - 1]
        ):
            labels[i] = "Pre-chorus"
    return labels


def _make_segment(label, start, end, rms, onset_env, beat_times, sr, index):
    name = f"{label} {index}" if index else label
    notes = _describe(start, end, rms, onset_env, sr)
    return {
        "label": name,
        "cls": CLS.get(label, "seg-verse"),
        "start_seconds": round(float(start), 2),
        "end_seconds": round(float(end), 2),
        "notes": notes,
    }


def _describe(start, end, rms, onset_env, sr):
    """Plain-English arrangement note derived from energy + onset density."""
    s = int(start * sr / HOP)
    e = max(s + 1, int(end * sr / HOP))
    seg_rms = rms[s:e]
    seg_onset = onset_env[s:e]
    if seg_rms.size == 0:
        return "Section."

    energy = float(seg_rms.mean()) / (float(rms.mean()) + 1e-9)
    density = float(seg_onset.mean()) / (float(onset_env.mean()) + 1e-9)

    parts = []
    if energy < 0.6:
        parts.append("quiet, restrained dynamics")
    elif energy > 1.2:
        parts.append("loud, full mix")
    else:
        parts.append("moderate dynamics")

    if density < 0.6:
        parts.append("sparse rhythmic activity")
    elif density > 1.3:
        parts.append("dense onsets, busy arrangement")
    else:
        parts.append("steady rhythmic drive")

    return "; ".join(parts).capitalize() + "."


def _snap_to_beat(t, beat_times, tol=0.4):
    """Snap a boundary time to the nearest beat if one is within tol seconds."""
    if len(beat_times) == 0:
        return t
    i = int(np.argmin(np.abs(beat_times - t)))
    return float(beat_times[i]) if abs(beat_times[i] - t) <= tol else t


def _norm(x):
    x = np.asarray(x, dtype=float)
    rng = x.max() - x.min()
    if rng < 1e-9:
        return np.zeros_like(x)
    return (x - x.min()) / rng


def _window_mean(rms_sync, sync_times, start, end):
    mask = (sync_times >= start) & (sync_times < end)
    if not mask.any():
        return float(rms_sync.mean())
    return float(rms_sync[mask].mean())
