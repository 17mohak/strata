"use client";

import { useState, useCallback } from "react";
import type { AnalysisResult } from "@/lib/types";
import { analyzeFile } from "@/lib/api";
import FileUpload from "./components/FileUpload";
import MetaBar from "./components/MetaBar";
import WaveformPlayer from "./components/WaveformPlayer";
import EmotionalArcChart from "./components/EmotionalArcChart";
import TheoryMoments from "./components/TheoryMoments";
import DNAMatches from "./components/DNAMatches";
import Sections from "./components/Sections";
import { Layers, RotateCcw } from "lucide-react";

export default function Home() {
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    setResult(null);
    setFileName(file.name);

    // Create object URL for waveform playback
    const url = URL.createObjectURL(file);
    setAudioUrl(url);

    try {
      const res = await analyzeFile(file, setStatus);
      setResult(res);
    } catch (e: any) {
      setError(e.message ?? "Something went wrong");
    } finally {
      setStatus(null);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
    setStatus(null);
    setFileName("");
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
  }, [audioUrl]);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-card-border bg-card/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Layers className="h-5 w-5 text-accent" />
            <span className="text-lg font-bold tracking-tight">Strata</span>
          </div>
          {result && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 text-sm text-muted hover:text-foreground transition"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              New analysis
            </button>
          )}
        </div>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-8">
        {/* Upload state */}
        {!result && !error && (
          <div className="max-w-xl mx-auto space-y-6">
            <div className="text-center space-y-2">
              <h1 className="text-3xl font-bold tracking-tight">
                X-ray any song
              </h1>
              <p className="text-muted">
                Upload a track and get a complete structural, emotional, and
                harmonic breakdown in seconds.
              </p>
            </div>
            <FileUpload onFile={handleFile} status={status} />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="max-w-xl mx-auto space-y-4 text-center">
            <div className="rounded-2xl bg-red-500/10 border border-red-500/20 p-6">
              <p className="text-red-400 font-medium">{error}</p>
            </div>
            <button
              onClick={reset}
              className="text-sm text-accent hover:underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Results */}
        {result?.status === "complete" && result.meta && (
          <div className="space-y-6 animate-in fade-in duration-500">
            {/* Meta */}
            <MetaBar meta={result.meta} fileName={fileName} />

            {/* Waveform */}
            {audioUrl && result.segments && (
              <WaveformPlayer
                audioUrl={audioUrl}
                segments={result.segments}
                duration={result.meta.duration_seconds}
              />
            )}

            {/* Two-column grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left column */}
              <div className="space-y-6">
                {/* Emotional arc */}
                {result.emotional_arc && (
                  <EmotionalArcChart
                    arc={result.emotional_arc}
                    hitMoment={result.hit_moment ?? null}
                    duration={result.meta.duration_seconds}
                  />
                )}

                {/* DNA matches */}
                {result.dna_matches && result.dna_matches.length > 0 && (
                  <DNAMatches matches={result.dna_matches} />
                )}
              </div>

              {/* Right column */}
              <div className="space-y-6">
                {/* Sections */}
                {result.segments && result.segments.length > 0 && (
                  <Sections segments={result.segments} />
                )}

                {/* Theory moments */}
                {result.theory_moments && result.theory_moments.length > 0 && (
                  <TheoryMoments moments={result.theory_moments} />
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-card-border py-4">
        <p className="text-center text-xs text-muted">
          Strata — Music Structure Decomposer
        </p>
      </footer>
    </div>
  );
}
