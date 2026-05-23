"""DNA fingerprint engine — FAISS-backed song similarity.

Provides:
  - build_vector()         : assemble a 73D feature vector from pre-computed arrays
  - extract_from_audio()   : load audio → HPSS → features → vector  (seed script)
  - DNAEngine              : FAISS index + query + per-group explainability
  - get_engine()           : module-level singleton accessor
"""

import gc
import os
import sqlite3

import faiss
import librosa
import numpy as np

from analyzer import _detect_key, HOP, SR

# ---------------------------------------------------------------------------
# Feature vector layout — 73 dimensions
# ---------------------------------------------------------------------------

FEATURE_DIM = 73

FEATURE_GROUPS = [
    # (name, start, end, human_desc)
    ("harmonic_profile",  0,  12, "harmonic character (key centres and chord qualities)"),
    ("tonality",         12,  14, "tonal foundation (key and mode)"),
    ("timbral_mean",     14,  27, "timbral fingerprint (instrument and vocal texture)"),
    ("timbral_var",      27,  40, "timbral dynamics throughout the track"),
    ("brightness",       40,  42, "spectral brightness (mix clarity and air)"),
    ("width",            42,  44, "spectral width (fullness of the mix)"),
    ("rolloff",          44,  46, "frequency distribution (high-frequency energy)"),
    ("rhythm",           46,  47, "rhythmic density and drive"),
    ("energy_contour",   47,  57, "energy arc (dynamic flow of the track)"),
    ("percussiveness",   57,  59, "percussive character (transient punch)"),
    ("spectral_change",  59,  61, "rate of spectral change (harmonic movement)"),
    ("harmonic_stability", 61, 73, "harmonic variation and consistency"),
]

_MATCH_TYPE_MAP = {
    "harmonic_profile": "harmonic", "tonality": "harmonic",
    "timbral_mean": "timbral", "timbral_var": "timbral",
    "brightness": "timbral", "width": "timbral", "rolloff": "timbral",
    "rhythm": "rhythmic", "energy_contour": "tension_curve",
    "percussiveness": "rhythmic", "spectral_change": "timbral",
    "harmonic_stability": "harmonic",
}


# ---------------------------------------------------------------------------
# Feature vector construction
# ---------------------------------------------------------------------------

def build_vector(
    chroma: np.ndarray,
    mode: str,
    tempo: float,
    mfcc: np.ndarray,
    centroid: np.ndarray,
    bandwidth: np.ndarray,
    rolloff: np.ndarray,
    onset_env: np.ndarray,
    rms: np.ndarray,
    zcr: np.ndarray,
    flux: np.ndarray,
) -> np.ndarray:
    """Assemble the canonical 73D feature vector from pre-computed frame arrays.

    Every path that creates a vector — live uploads AND the seed script — must
    call this function so the feature layout is always identical.
    """
    return np.concatenate([
        chroma.mean(axis=1),                                 # 12  harmonic profile
        [1.0 if mode == "major" else 0.0],                   #  1  mode
        [tempo / 200.0],                                     #  1  normalised BPM
        mfcc.mean(axis=1),                                   # 13  timbral means
        mfcc.var(axis=1),                                    # 13  timbral variance
        [centroid.mean(), centroid.var()],                    #  2  brightness
        [bandwidth.mean(), bandwidth.var()],                  #  2  spectral width
        [rolloff.mean(), rolloff.var()],                      #  2  frequency distribution
        [onset_env.mean()],                                  #  1  onset density
        _resample(rms, 10),                                  # 10  energy contour
        [zcr.mean(), zcr.var()],                             #  2  percussiveness
        [flux.mean() if flux.size else 0.0,                  #  2  spectral flux
         flux.var()  if flux.size else 0.0],
        chroma.var(axis=1),                                  # 12  harmonic stability
    ]).astype(np.float32)                                    # Σ = 73


def extract_from_audio(path: str) -> tuple[dict, np.ndarray]:
    """Full HPSS pipeline on an audio file → (metadata, 73D vector).

    Used by seed_deezer.py. The live path calls build_vector() directly with
    features already computed by run_analysis().
    """
    y, sr = librosa.load(path, sr=SR, mono=True)
    if y.size == 0:
        raise ValueError("Audio file is empty.")

    rms  = librosa.feature.rms(y=y, hop_length=HOP)[0]
    y_harm, y_perc = librosa.effects.hpss(y)
    del y

    tempo, _ = librosa.beat.beat_track(y=y_perc, sr=sr, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr, hop_length=HOP)
    del y_perc

    chroma    = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=HOP)
    S         = np.abs(librosa.stft(y_harm, hop_length=HOP, n_fft=2048))
    mfcc      = librosa.feature.mfcc(S=librosa.power_to_db(S ** 2), sr=sr, n_mfcc=13)
    centroid  = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)[0]
    rolloff   = librosa.feature.spectral_rolloff(S=S, sr=sr)[0]
    zcr       = librosa.feature.zero_crossing_rate(y_harm, hop_length=HOP)[0]

    pos_d = np.maximum(np.diff(S, axis=1), 0.0)
    flux  = np.sqrt((pos_d ** 2).sum(axis=0))

    del S, pos_d, y_harm
    gc.collect()

    key, mode = _detect_key(chroma)
    vec = build_vector(chroma, mode, tempo, mfcc, centroid, bandwidth,
                       rolloff, onset_env, rms, zcr, flux)

    meta = {"key": key, "mode": mode, "bpm": round(tempo)}
    return meta, vec


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    deezer_id       INTEGER UNIQUE,
    title           TEXT    NOT NULL,
    artist          TEXT    NOT NULL,
    genre           TEXT,
    album_art_url   TEXT,
    key             TEXT,
    mode            TEXT,
    bpm             REAL,
    feature_vector  BLOB    NOT NULL,
    created_at      TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_deezer_id ON songs(deezer_id);
"""


def init_db(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    con.executescript(_SCHEMA)
    con.close()


def insert_song(db_path: str, *, deezer_id: int, title: str, artist: str,
                genre: str | None, album_art_url: str | None,
                key: str, mode: str, bpm: float,
                feature_vector: np.ndarray) -> None:
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT OR IGNORE INTO songs "
        "(deezer_id, title, artist, genre, album_art_url, key, mode, bpm, feature_vector) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (deezer_id, title, artist, genre, album_art_url,
         key, mode, bpm, feature_vector.tobytes()),
    )
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# FAISS engine
# ---------------------------------------------------------------------------

class DNAEngine:
    """Loads song vectors from SQLite into a FAISS inner-product index.

    Raw vectors are z-score standardised per dimension so that high-magnitude
    features (spectral centroid ~10^6) don't drown out low-magnitude ones
    (chroma ~0-1).  The standardised vectors are then L2-normalised for cosine
    similarity via IndexFlatIP.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.index = faiss.IndexFlatIP(FEATURE_DIM)
        self.songs: list[dict] = []
        self._raw_vectors = np.empty((0, FEATURE_DIM), dtype=np.float32)
        self._mean = np.zeros(FEATURE_DIM, dtype=np.float32)
        self._std  = np.ones(FEATURE_DIM, dtype=np.float32)

        if os.path.exists(db_path):
            self._load()

    @property
    def size(self) -> int:
        return self.index.ntotal

    def _load(self) -> None:
        con = sqlite3.connect(self.db_path)
        rows = con.execute(
            "SELECT id, title, artist, genre, album_art_url, key, mode, bpm, "
            "feature_vector FROM songs"
        ).fetchall()
        con.close()

        if not rows:
            return

        raw: list[np.ndarray] = []
        for row in rows:
            self.songs.append({
                "id": row[0], "title": row[1], "artist": row[2],
                "genre": row[3], "album_art_url": row[4],
                "key": row[5], "mode": row[6], "bpm": row[7],
            })
            raw.append(np.frombuffer(row[8], dtype=np.float32).copy())

        self._raw_vectors = np.vstack(raw)

        self._mean = self._raw_vectors.mean(axis=0)
        self._std  = self._raw_vectors.std(axis=0)
        self._std[self._std < 1e-9] = 1.0

        normed = self._standardise(self._raw_vectors)
        faiss.normalize_L2(normed)
        self.index.add(normed)

    def _standardise(self, vecs: np.ndarray) -> np.ndarray:
        out = ((vecs - self._mean) / self._std).astype(np.float32)
        return np.ascontiguousarray(out)

    def query(self, feature_vec: np.ndarray, top_k: int = 3) -> list[dict]:
        if self.index.ntotal == 0:
            return []

        q = self._standardise(feature_vec.reshape(1, -1))
        faiss.normalize_L2(q)

        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q, k)

        results: list[dict] = []
        for rank in range(k):
            idx = int(indices[0][rank])
            if idx < 0:
                continue
            sim = float(scores[0][rank])
            song = self.songs[idx]
            match_vec = self._raw_vectors[idx]
            reason = self._explain(feature_vec, match_vec)
            mtype  = self._match_type(feature_vec, match_vec)
            results.append({
                "title":        song["title"],
                "artist":       song["artist"],
                "similarity":   round(max(0.0, sim), 2),
                "match_reason": reason,
                "match_type":   mtype,
                "album_art_url": song.get("album_art_url"),
            })
        return results

    # ── Explainability ────────────────────────────────────────────────────

    def _explain(self, q: np.ndarray, m: np.ndarray) -> str:
        ranked = self._rank_groups(q, m)
        top2 = ranked[:2]
        parts = [desc for _, desc, _ in top2]
        return "Both tracks share " + " and ".join(parts) + "."

    def _match_type(self, q: np.ndarray, m: np.ndarray) -> str:
        ranked = self._rank_groups(q, m)
        top3_names = [name for name, _, _ in ranked[:3]]
        types = [_MATCH_TYPE_MAP.get(n, "timbral") for n in top3_names]
        return max(set(types), key=types.count)

    @staticmethod
    def _rank_groups(q: np.ndarray, m: np.ndarray) -> list[tuple[str, str, float]]:
        """Return feature groups sorted by similarity (most similar first)."""
        results: list[tuple[str, str, float]] = []
        for name, start, end, desc in FEATURE_GROUPS:
            qs, ms = q[start:end], m[start:end]
            nq, nm = np.linalg.norm(qs), np.linalg.norm(ms)
            if nq < 1e-9 or nm < 1e-9:
                sim = 0.0
            else:
                sim = float(np.dot(qs, ms) / (nq * nm))
            results.append((name, desc, sim))
        results.sort(key=lambda x: x[2], reverse=True)
        return results


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_engine: DNAEngine | None = None


def get_engine(db_path: str | None = None) -> DNAEngine:
    global _engine
    if _engine is None:
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "seed.db")
        _engine = DNAEngine(db_path)
    return _engine


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resample(arr: np.ndarray, n_bins: int) -> np.ndarray:
    if arr.size == 0:
        return np.zeros(n_bins, dtype=float)
    splits = np.array_split(np.arange(len(arr)), n_bins)
    return np.array([float(arr[s].mean()) for s in splits])
