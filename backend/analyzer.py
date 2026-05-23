"""Audio analysis pipeline — Week 2 upgrade.

Refactored from the Week 1 baseline to add:
  - HPSS (beat tracking on y_perc, chroma on y_harm)
  - Template-based chord detection with median smoothing
  - music21 Roman-numeral pass for theory_moments and progression summary
  - Composite emotional arc: Energy / Tension / Valence (0-100)
  - Hit-moment detector with structured plain-English explanation
  - Proactive del + gc.collect() to stay within 512MB container ceilings
"""

import gc

import librosa
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import medfilt

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

HOP = 512
SR = 22050

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler key profiles
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Section label → frontend CSS class
CLS = {
    "Intro": "seg-intro",
    "Verse": "seg-verse",
    "Pre-chorus": "seg-prechorus",
    "Chorus": "seg-chorus",
    "Bridge": "seg-bridge",
    "Outro": "seg-outro",
}

# Pitch-class → pitch name used by music21
_PC_TO_PITCH = {0: "C", 1: "C#", 2: "D", 3: "D#", 4: "E", 5: "F",
                6: "F#", 7: "G", 8: "G#", 9: "A", 10: "A#", 11: "B"}

# Binary chord templates: major = [root, M3, P5], minor = [root, m3, P5]
# Stored in insertion order (Python 3.7+) so index ↔ name is stable.
_CHORD_TEMPLATES: dict[str, np.ndarray] = {}
for _i, _note in enumerate(NOTES):
    _maj = np.zeros(12, dtype=float)
    _maj[[_i, (_i + 4) % 12, (_i + 7) % 12]] = 1.0
    _CHORD_TEMPLATES[_note] = _maj
    _min = np.zeros(12, dtype=float)
    _min[[_i, (_i + 3) % 12, (_i + 7) % 12]] = 1.0
    _CHORD_TEMPLATES[_note + "m"] = _min

_TEMPLATE_NAMES: list[str] = list(_CHORD_TEMPLATES.keys())  # 24 entries, stable order

# Pre-normalised template matrix: shape (24, 12). Each triad has exactly 3 active
# bins so ||t|| = sqrt(3); pre-dividing makes the cosine sim a pure dot product.
_TEMPLATE_MATRIX = np.array(
    [_CHORD_TEMPLATES[n] / np.sqrt(3.0) for n in _TEMPLATE_NAMES]
)

# Consonance scoring: intervals that add to (+) or subtract from (-) valence
_CONSONANT = frozenset({3, 4, 7, 8, 9})    # m3, M3, P5, m6, M6
_DISSONANT  = frozenset({1, 2, 6, 10, 11})  # m2, M2, TT, m7, M7

# Approximate grid-cell size used throughout (seconds)
_GRID_S = 0.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_analysis(path: str) -> dict:
    """Full analysis pipeline. Returns a dict matching the API contract."""

    # ── 1. Load ──────────────────────────────────────────────────────────────
    y, sr = librosa.load(path, sr=SR, mono=True)
    if y.size == 0:
        raise ValueError("Audio file is empty or could not be decoded.")
    duration = float(librosa.get_duration(y=y, sr=sr))

    # RMS from the full mix captures perceived dynamics including transients.
    rms_full = librosa.feature.rms(y=y, hop_length=HOP)[0]

    # ── 2. HPSS ──────────────────────────────────────────────────────────────
    y_harm, y_perc = librosa.effects.hpss(y)
    del y
    gc.collect()

    # ── 3. Percussive features ───────────────────────────────────────────────
    # Beat tracking on the percussive layer avoids harmonic phase confusion.
    tempo, beat_frames = librosa.beat.beat_track(y=y_perc, sr=sr, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)

    # Onset envelope from percussive: onset density is driven by transients.
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr, hop_length=HOP)
    del y_perc

    # ── 4. Harmonic features ─────────────────────────────────────────────────
    # Chroma from harmonic-only signal: suppresses drum-hit pitch bleed.
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=HOP)

    # STFT for spectral centroid (brightness) and spectral flux.
    S_harm = np.abs(librosa.stft(y_harm, hop_length=HOP, n_fft=2048))
    spec_centroid = librosa.feature.spectral_centroid(S=S_harm, sr=sr)[0]

    # Half-wave-rectified flux: sum of squared positive spectral deltas.
    pos_delta = np.maximum(np.diff(S_harm, axis=1), 0.0)
    flux = np.concatenate([[0.0], np.sqrt((pos_delta ** 2).sum(axis=0))])

    del S_harm, pos_delta, y_harm
    gc.collect()

    # ── 5. Key detection ─────────────────────────────────────────────────────
    key, mode = _detect_key(chroma)

    # ── 6. Uniform ~0.5s time grid ───────────────────────────────────────────
    m = min(len(rms_full), len(onset_env), chroma.shape[1],
            len(spec_centroid), len(flux))
    rms_full    = rms_full[:m]
    onset_env   = onset_env[:m]
    chroma      = chroma[:, :m]
    spec_centroid = spec_centroid[:m]
    flux        = flux[:m]
    frame_times = librosa.frames_to_time(np.arange(m), sr=sr, hop_length=HOP)

    win = max(1, int(round(_GRID_S * sr / HOP)))
    grid_starts = np.arange(0, m, win)

    def _gagg(arr1d: np.ndarray) -> np.ndarray:
        return np.array([arr1d[i: i + win].mean() for i in grid_starts])

    rms_g      = _gagg(rms_full)
    onset_g    = _gagg(onset_env)
    flux_g     = _gagg(flux)
    centroid_g = _gagg(spec_centroid)
    # chroma_g: (12, G) — mean chroma per grid cell
    chroma_g   = np.array(
        [chroma[:, i: i + win].mean(axis=1) for i in grid_starts]
    ).T
    grid_times = frame_times[grid_starts]

    # ── 7. Chord detection (template cosine similarity) ───────────────────────
    chord_labels = _detect_chords(chroma_g)

    # ── 8. Theory analysis via music21 ───────────────────────────────────────
    progression, theory_moments = _analyse_harmony(chord_labels, grid_times, key, mode)

    # ── 9. Section segmentation ───────────────────────────────────────────────
    # Passes frame-level arrays so _describe can compute per-segment notes.
    segments = _segment(rms_full, onset_env, chroma, beat_times, duration, sr)

    # ── 10. Emotional arc + hit moment ───────────────────────────────────────
    emotional_arc, hit_moment = _compute_emotional_arc(
        rms_g, flux_g, onset_g, chroma_g, centroid_g, grid_times
    )

    # Enrich hit-moment label with the segment it falls in.
    if hit_moment and segments:
        t_hit = hit_moment["time_seconds"]
        for seg in segments:
            if seg["start_seconds"] <= t_hit < seg["end_seconds"]:
                hit_moment["label"] = f"Drop into {seg['label']}"
                break

    # ── 11. Cleanup ───────────────────────────────────────────────────────────
    del chroma, rms_full, onset_env, spec_centroid, flux
    del rms_g, flux_g, onset_g, chroma_g, centroid_g
    gc.collect()

    return {
        "meta": {
            "title": None,
            "duration_seconds": round(duration, 2),
            "tempo": round(tempo),
            "key": key,
            "mode": mode,
            "time_signature": "4/4",
            "progression": progression,
        },
        "segments": segments,
        "beats": [round(float(t), 3) for t in beat_times],
        "emotional_arc": emotional_arc,
        "hit_moment": hit_moment,
        "theory_moments": theory_moments,
        "dna_matches": [],  # Week 3 (MERT embeddings)
    }


# ---------------------------------------------------------------------------
# Key detection
# ---------------------------------------------------------------------------

def _detect_key(chroma_full: np.ndarray) -> tuple[str, str]:
    """Krumhansl-Schmuckler correlation against all 24 key profiles."""
    chroma = chroma_full.mean(axis=1)
    best_score = -np.inf
    best: tuple[str, str] = ("C", "major")
    for i in range(12):
        maj  = np.corrcoef(np.roll(MAJOR_PROFILE, i), chroma)[0, 1]
        minr = np.corrcoef(np.roll(MINOR_PROFILE, i), chroma)[0, 1]
        if maj > best_score:
            best_score, best = maj, (NOTES[i], "major")
        if minr > best_score:
            best_score, best = minr, (NOTES[i], "minor")
    return best


# ---------------------------------------------------------------------------
# Chord detection
# ---------------------------------------------------------------------------

def _detect_chords(chroma_g: np.ndarray) -> list[str]:
    """Cosine similarity between each 0.5s chroma cell and 24 triad templates.

    Returns a list of G chord-label strings after median-filter smoothing to
    suppress single-cell flicker.
    """
    G = chroma_g.shape[1]
    norms = np.linalg.norm(chroma_g, axis=0, keepdims=True)  # (1, G)
    # Replace near-zero norms to avoid division by zero.
    safe_norms = np.where(norms < 1e-9, 1.0, norms)
    chroma_n = chroma_g / safe_norms           # (12, G) unit vectors

    # _TEMPLATE_MATRIX (24, 12) · chroma_n (12, G) → sims (24, G)
    sims = _TEMPLATE_MATRIX @ chroma_n
    indices = np.argmax(sims, axis=0).astype(float)  # (G,) float for medfilt

    # Median filter: kernel_size must be odd; 7 cells ≈ 3.5s context window.
    kernel = min(7, G if G % 2 == 1 else G - 1)
    kernel = max(kernel, 1)
    if kernel % 2 == 0:
        kernel -= 1
    smoothed = medfilt(indices, kernel_size=kernel).astype(int)
    smoothed = np.clip(smoothed, 0, len(_TEMPLATE_NAMES) - 1)
    return [_TEMPLATE_NAMES[int(i)] for i in smoothed]


# ---------------------------------------------------------------------------
# Harmony analysis (music21)
# ---------------------------------------------------------------------------

def _analyse_harmony(
    chord_labels: list[str],
    grid_times: np.ndarray,
    key_str: str,
    mode_str: str,
) -> tuple[str | None, list[dict]]:
    """Map chord sequence to Roman numerals and flag non-diatonic chords.

    music21 is only used here — for Roman-numeral labelling — never for score
    ingestion or audio analysis. Falls back gracefully if music21 is absent or
    if the key is enharmonically ambiguous.
    """
    try:
        from music21 import chord as m21chord, key as m21key, roman
        k = m21key.Key(key_str, mode_str)
        scale_pcs = frozenset(p.pitchClass for p in k.pitches)
    except Exception:
        return _fallback_progression(chord_labels), []

    # Run-length encoded chord changes (time, label).
    changes: list[tuple[float, str]] = []
    prev = None
    for t, label in zip(grid_times, chord_labels):
        if label != prev:
            changes.append((float(t), label))
            prev = label

    progression_rn: list[str] = []
    seen_rn: set[str] = set()
    theory_moments: list[dict] = []
    seen_nondiatonic: set[str] = set()

    for t, label in changes:
        template = _CHORD_TEMPLATES.get(label)
        if template is None:
            continue
        pcs = [int(i) for i in np.where(template > 0)[0]]
        if not pcs:
            continue
        try:
            cs = m21chord.Chord([_PC_TO_PITCH[pc] for pc in pcs])
            rn = roman.romanNumeralFromChord(cs, k)
            rn_fig = rn.figure

            if rn_fig not in seen_rn and len(progression_rn) < 6:
                progression_rn.append(rn_fig)
                seen_rn.add(rn_fig)

            # Non-diatonic: chord contains at least one note outside the scale.
            if not frozenset(pcs).issubset(scale_pcs) and label not in seen_nondiatonic:
                seen_nondiatonic.add(label)
                theory_moments.append({
                    "time_seconds": round(t, 2),
                    "label": f"Non-diatonic chord — {rn_fig}",
                    "detail": (
                        f"{label} chord contains notes outside the "
                        f"{key_str} {mode_str} scale, lending it a "
                        f"borrowed or chromatic colour."
                    ),
                })
        except Exception:
            continue

    prog = (
        "–".join(progression_rn[:4])
        if progression_rn
        else _fallback_progression(chord_labels)
    )
    return prog, theory_moments


def _fallback_progression(chord_labels: list[str]) -> str | None:
    """First 4 unique chord names in order — used when music21 is unavailable."""
    seen: list[str] = []
    for c in chord_labels:
        if c not in seen:
            seen.append(c)
        if len(seen) >= 4:
            break
    return "–".join(seen) if seen else None


# ---------------------------------------------------------------------------
# Emotional arc
# ---------------------------------------------------------------------------

def _compute_emotional_arc(
    rms_g: np.ndarray,
    flux_g: np.ndarray,
    onset_g: np.ndarray,
    chroma_g: np.ndarray,
    centroid_g: np.ndarray,
    grid_times: np.ndarray,
) -> tuple[dict, dict | None]:
    """Compute Energy / Tension / Valence curves and detect the hit moment."""
    G = len(rms_g)

    # ── Energy: normalised RMS → 0-100 ──────────────────────────────────────
    energy_n = _norm(rms_g)                          # 0-1
    energy_100 = (energy_n * 100.0).astype(int)

    # ── Tension: spectral flux + |dRMS/dt| → 0-100 ──────────────────────────
    flux_n      = _norm(flux_g)
    rms_deriv_n = _norm(np.abs(np.gradient(rms_g)))
    tension_raw = 0.6 * flux_n + 0.4 * rms_deriv_n
    tension_100 = (_norm(tension_raw) * 100.0).astype(int)

    # ── Valence: chroma consonance + spectral brightness → 0-100 ────────────
    cons_scores = np.array([_consonance_score(chroma_g[:, j]) for j in range(G)])
    valence_raw = 0.55 * _norm(cons_scores) + 0.45 * _norm(centroid_g)
    valence_100 = (_norm(valence_raw) * 100.0).astype(int)

    # ── Smooth all curves with a Gaussian (σ=2 grid cells ≈ 1s) ────────────
    sigma = 2.0
    energy_s  = np.clip(gaussian_filter1d(energy_100.astype(float),  sigma), 0, 100).astype(int)
    tension_s = np.clip(gaussian_filter1d(tension_100.astype(float), sigma), 0, 100).astype(int)
    valence_s = np.clip(gaussian_filter1d(valence_100.astype(float), sigma), 0, 100).astype(int)

    arc = {
        "timestamps": [round(float(t), 2) for t in grid_times],
        "energy":     energy_s.tolist(),
        "tension":    tension_s.tolist(),
        "valence":    valence_s.tolist(),
    }

    hit = _find_hit_moment(energy_n, onset_g, flux_g, centroid_g, grid_times)
    return arc, hit


def _consonance_score(chroma_cell: np.ndarray) -> float:
    """Signed consonance score for a 12D chroma vector.

    Sums pairwise chroma products weighted +1 for consonant intervals and -1
    for dissonant intervals. A positive score indicates a brighter, more
    resolved harmony; negative indicates tension or dissonance.
    """
    score = 0.0
    for i in range(12):
        vi = float(chroma_cell[i])
        if vi < 1e-9:
            continue
        for j in range(i + 1, 12):
            interval = (j - i) % 12
            w = vi * float(chroma_cell[j])
            if interval in _CONSONANT:
                score += w
            elif interval in _DISSONANT:
                score -= w
    return score


def _find_hit_moment(
    energy_n: np.ndarray,
    onset_g: np.ndarray,
    flux_g: np.ndarray,
    centroid_g: np.ndarray,
    grid_times: np.ndarray,
) -> dict | None:
    """Locate the steepest positive rolling delta that follows a low-energy window.

    Algorithm:
      combined = 0.6*energy + 0.4*onset_density
      For every position i >= 2W:
        pre_mean  = mean(combined[i-2W : i-W])   ← the "quiet build" window
        post_mean = mean(combined[i-W  : i])      ← the "drop" window
        delta = post_mean - pre_mean
      Candidate must have pre_mean <= p40 AND delta > 0.
      Best candidate (max delta) is the hit moment.
    """
    onset_n   = _norm(onset_g)
    flux_n    = _norm(flux_g)
    centroid_n = _norm(centroid_g)
    combined  = 0.6 * energy_n + 0.4 * onset_n

    W = max(3, int(round(2.5 / _GRID_S)))          # ≈5 cells = 2.5s
    low_thresh = float(np.percentile(combined, 40))

    best_i     = -1
    best_delta = -np.inf

    for i in range(2 * W, len(combined)):
        pre  = combined[i - 2 * W: i - W]
        post = combined[i - W: i]
        if pre.size == 0 or post.size == 0:
            continue
        pre_mean  = float(pre.mean())
        post_mean = float(post.mean())
        delta = post_mean - pre_mean
        if delta > best_delta and pre_mean <= low_thresh:
            best_delta = delta
            best_i = i - W  # leading edge of the rise

    # Fallback: overall energy peak when no valid drop is found.
    if best_i < 0 or best_delta <= 0:
        best_i = int(np.argmax(combined))

    best_i = int(np.clip(best_i, 0, len(grid_times) - 1))
    t_hit  = float(grid_times[best_i])

    # ── Explain the hit moment ────────────────────────────────────────────
    ctx_s = max(0, best_i - W)
    ctx_e = min(len(combined) - 1, best_i + W)

    reasons: list[str] = []
    if onset_n[ctx_e] - onset_n[ctx_s] > 0.15:
        reasons.append("sudden onset density surge (percussion or new instruments enter)")
    if centroid_n[ctx_e] - centroid_n[ctx_s] > 0.15:
        reasons.append("sharp rise in spectral brightness")
    if energy_n[ctx_e] - energy_n[ctx_s] > 0.20:
        reasons.append("significant RMS energy surge")
    if float(flux_n[best_i]) > 0.65:
        reasons.append("dense harmonic activity (elevated spectral flux)")
    if not reasons:
        reasons.append("combined energy and onset activity peak")

    return {
        "time_seconds": round(t_hit, 2),
        "label": f"Peak energy moment at {round(t_hit)}s",  # enriched later in run_analysis
        "reason": "Triggered by: " + "; ".join(reasons) + ".",
    }


# ---------------------------------------------------------------------------
# Section segmentation (unchanged from Week 1)
# ---------------------------------------------------------------------------

def _segment(
    rms: np.ndarray,
    onset_env: np.ndarray,
    chroma: np.ndarray,
    beat_times: np.ndarray,
    duration: float,
    sr: int,
) -> list[dict]:
    """Rule-based section segmentation on a fixed ~0.5s time grid."""
    if duration < 12:
        return [_make_segment("Verse", 0.0, duration, rms, onset_env, beat_times, sr, 1)]

    m = min(len(rms), len(onset_env), chroma.shape[1])
    rms_m, onset_m, chroma_m = rms[:m], onset_env[:m], chroma[:, :m]
    frame_times = librosa.frames_to_time(np.arange(m), sr=sr, hop_length=HOP)

    win    = max(1, int(round(_GRID_S * sr / HOP)))
    starts = np.arange(0, m, win)

    rms_g    = np.array([rms_m[i: i + win].mean() for i in starts])
    onset_g  = np.array([onset_m[i: i + win].mean() for i in starts])
    chroma_g = np.array([chroma_m[:, i: i + win].mean(axis=1) for i in starts]).T
    grid_times = frame_times[starts]

    feat = np.vstack([_norm(rms_g), _norm(onset_g), librosa.util.normalize(chroma_g, axis=0)])

    k = int(np.clip(round(duration / 22.0), 4, 8))
    k = min(k, feat.shape[1] - 1)
    bounds = librosa.segment.agglomerative(feat, k)

    bound_times = [0.0]
    for b in bounds:
        t = float(grid_times[min(b, len(grid_times) - 1)])
        t = _snap_to_beat(t, beat_times)
        if t - bound_times[-1] > 3.0:
            bound_times.append(t)
    bound_times.append(duration)

    energies = np.array([
        _window_mean(rms_g, grid_times, bound_times[i], bound_times[i + 1])
        for i in range(len(bound_times) - 1)
    ])
    n = len(energies)

    labels = _assign_labels(energies, float(np.percentile(energies, 60)), n)

    counts: dict[str, int] = {}
    segments: list[dict] = []
    for i, base in enumerate(labels):
        counts[base] = counts.get(base, 0) + 1
        idx = counts[base] if base in ("Verse", "Chorus") else None
        segments.append(
            _make_segment(base, bound_times[i], bound_times[i + 1],
                          rms, onset_env, beat_times, sr, idx)
        )
    return segments


def _assign_labels(energies: np.ndarray, high: float, n: int) -> list[str]:
    labels: list[str] = []
    for i, e in enumerate(energies):
        if i == 0:
            labels.append("Intro")
        elif i == n - 1:
            labels.append("Outro")
        elif e >= high:
            labels.append("Chorus")
        else:
            labels.append("Verse")

    seen_chorus = False
    for i in range(1, n - 1):
        if labels[i] == "Chorus":
            seen_chorus = True
        elif seen_chorus and i >= n * 0.55 and energies[i] < float(np.median(energies)):
            labels[i] = "Bridge"
            break

    for i in range(1, n - 1):
        if (labels[i] == "Verse" and labels[i + 1] == "Chorus"
                and energies[i] > energies[i - 1]):
            labels[i] = "Pre-chorus"
    return labels


def _make_segment(
    label: str,
    start: float,
    end: float,
    rms: np.ndarray,
    onset_env: np.ndarray,
    beat_times: np.ndarray,
    sr: int,
    index: int | None,
) -> dict:
    name = f"{label} {index}" if index else label
    return {
        "label": name,
        "cls": CLS.get(label, "seg-verse"),
        "start_seconds": round(float(start), 2),
        "end_seconds":   round(float(end),   2),
        "notes": _describe(start, end, rms, onset_env, sr),
    }


def _describe(start: float, end: float, rms: np.ndarray,
              onset_env: np.ndarray, sr: int) -> str:
    s = int(start * sr / HOP)
    e = max(s + 1, int(end * sr / HOP))
    seg_rms   = rms[s:e]
    seg_onset = onset_env[s:e]
    if seg_rms.size == 0:
        return "Section."

    energy  = float(seg_rms.mean())   / (float(rms.mean())       + 1e-9)
    density = float(seg_onset.mean()) / (float(onset_env.mean()) + 1e-9)

    parts: list[str] = []
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


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _snap_to_beat(t: float, beat_times: np.ndarray, tol: float = 0.4) -> float:
    if len(beat_times) == 0:
        return t
    i = int(np.argmin(np.abs(beat_times - t)))
    return float(beat_times[i]) if abs(beat_times[i] - t) <= tol else t


def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    rng = x.max() - x.min()
    if rng < 1e-9:
        return np.zeros_like(x)
    return (x - x.min()) / rng


def _window_mean(arr: np.ndarray, times: np.ndarray,
                 start: float, end: float) -> float:
    mask = (times >= start) & (times < end)
    if not mask.any():
        return float(arr.mean())
    return float(arr[mask].mean())
