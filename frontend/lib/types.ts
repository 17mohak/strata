/* ── Strata API response types ─────────────────────────────────── */

export interface Meta {
  title: string | null;
  duration_seconds: number;
  tempo: number;
  key: string;
  mode: string;
  time_signature: string;
  progression: string | null;
}

export interface Segment {
  label: string;
  cls: string;
  start_seconds: number;
  end_seconds: number;
  notes: string;
}

export interface EmotionalArc {
  timestamps: number[];
  energy: number[];
  tension: number[];
  valence: number[];
}

export interface HitMoment {
  time_seconds: number;
  label: string;
  explanation: string;
}

export interface TheoryMoment {
  time_seconds: number;
  chord: string;
  roman: string;
  label: string;
  detail: string;
}

export interface DNAMatch {
  title: string;
  artist: string;
  similarity: number;
  match_reason: string;
  match_type: string;
  album_art_url?: string | null;
}

export interface AnalysisResult {
  job_id: string;
  status: "processing" | "complete" | "error";
  error?: string;
  meta?: Meta;
  segments?: Segment[];
  beats?: number[];
  emotional_arc?: EmotionalArc | null;
  hit_moment?: HitMoment | null;
  theory_moments?: TheoryMoment[];
  dna_matches?: DNAMatch[];
}
