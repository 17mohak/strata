"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import type { Segment } from "@/lib/types";
import { Play, Pause, SkipBack } from "lucide-react";

const SEG_COLORS: Record<string, string> = {
  "seg-intro": "rgba(139,92,246,0.15)",
  "seg-verse": "rgba(59,130,246,0.15)",
  "seg-pre-chorus": "rgba(245,158,11,0.15)",
  "seg-chorus": "rgba(239,68,68,0.15)",
  "seg-bridge": "rgba(34,197,94,0.15)",
  "seg-outro": "rgba(139,92,246,0.10)",
};

const SEG_BORDER: Record<string, string> = {
  "seg-intro": "#8b5cf6",
  "seg-verse": "#3b82f6",
  "seg-pre-chorus": "#f59e0b",
  "seg-chorus": "#ef4444",
  "seg-bridge": "#22c55e",
  "seg-outro": "#8b5cf6",
};

interface Props {
  audioUrl: string;
  segments: Segment[];
  duration: number;
}

export default function WaveformPlayer({ audioUrl, segments, duration }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<any>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurTime] = useState(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;

    import("wavesurfer.js").then((WaveSurfer) => {
      if (cancelled || !containerRef.current) return;

      const ws = WaveSurfer.default.create({
        container: containerRef.current,
        waveColor: "#3f3f46",
        progressColor: "#8b5cf6",
        cursorColor: "#8b5cf6",
        cursorWidth: 2,
        height: 80,
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        normalize: true,
        url: audioUrl,
      });

      ws.on("ready", () => {
        if (!cancelled) setReady(true);
      });
      ws.on("play", () => setPlaying(true));
      ws.on("pause", () => setPlaying(false));
      ws.on("timeupdate", (t: number) => setCurTime(t));

      wsRef.current = ws;
    });

    return () => {
      cancelled = true;
      wsRef.current?.destroy();
      wsRef.current = null;
      setReady(false);
    };
  }, [audioUrl]);

  const toggle = useCallback(() => wsRef.current?.playPause(), []);
  const restart = useCallback(() => {
    wsRef.current?.seekTo(0);
    wsRef.current?.play();
  }, []);

  const fmt = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div className="rounded-2xl bg-card border border-card-border p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-muted">{fmt(currentTime)}</span>
        <div className="flex gap-2">
          <button
            onClick={restart}
            disabled={!ready}
            className="p-2 rounded-lg bg-card-border/50 hover:bg-accent/20 transition disabled:opacity-40"
          >
            <SkipBack className="h-4 w-4" />
          </button>
          <button
            onClick={toggle}
            disabled={!ready}
            className="p-2 rounded-lg bg-accent text-white hover:bg-accent/80 transition disabled:opacity-40"
          >
            {playing ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </button>
        </div>
        <span className="text-xs font-mono text-muted">{fmt(duration)}</span>
      </div>

      <div ref={containerRef} className="w-full" />

      {/* Section overlay bar */}
      <div className="relative h-8 rounded-lg overflow-hidden bg-card-border/30">
        {segments.map((seg, i) => {
          const left = (seg.start_seconds / duration) * 100;
          const width = ((seg.end_seconds - seg.start_seconds) / duration) * 100;
          const bg = SEG_COLORS[seg.cls] ?? "rgba(255,255,255,0.05)";
          const border = SEG_BORDER[seg.cls] ?? "#52525b";
          return (
            <div
              key={i}
              className="absolute top-0 h-full flex items-center justify-center text-[10px] font-medium tracking-wide uppercase border-r"
              style={{
                left: `${left}%`,
                width: `${width}%`,
                background: bg,
                borderColor: border,
              }}
              title={seg.notes}
            >
              {width > 6 && (
                <span style={{ color: border }}>{seg.label}</span>
              )}
            </div>
          );
        })}

        {/* Playhead */}
        <div
          className="absolute top-0 h-full w-0.5 bg-accent z-10 transition-[left] duration-100"
          style={{ left: `${(currentTime / duration) * 100}%` }}
        />
      </div>
    </div>
  );
}
