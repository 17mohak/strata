"use client";

import type { TheoryMoment } from "@/lib/types";
import { BookOpen } from "lucide-react";

export default function TheoryMoments({
  moments,
}: {
  moments: TheoryMoment[];
}) {
  if (!moments.length) return null;

  return (
    <div className="rounded-2xl bg-card border border-card-border p-5 space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted flex items-center gap-2">
        <BookOpen className="h-4 w-4" />
        Theory Moments
      </h3>

      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {moments.map((m, i) => {
          const min = Math.floor(m.time_seconds / 60);
          const sec = Math.floor(m.time_seconds % 60);
          return (
            <div
              key={i}
              className="flex items-start gap-3 rounded-xl bg-card-border/20 p-3 hover:bg-card-border/40 transition"
            >
              <span className="shrink-0 mt-0.5 text-xs font-mono text-muted bg-card-border/60 px-2 py-0.5 rounded">
                {min}:{String(sec).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">{m.chord}</span>
                  <span className="text-accent text-xs font-mono">{m.roman}</span>
                  <span className="text-xs text-muted/70 bg-accent/10 px-1.5 py-0.5 rounded-md">
                    {m.label}
                  </span>
                </div>
                <p className="text-xs text-muted mt-0.5 leading-relaxed">
                  {m.detail}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
