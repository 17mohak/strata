"use client";

import type { DNAMatch } from "@/lib/types";
import { Dna, Music } from "lucide-react";

const TYPE_COLOR: Record<string, string> = {
  harmonic: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  timbral: "text-purple-400 bg-purple-400/10 border-purple-400/20",
  rhythmic: "text-orange-400 bg-orange-400/10 border-orange-400/20",
  tension_curve: "text-red-400 bg-red-400/10 border-red-400/20",
};

function SimBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-card-border/50 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent to-purple-400 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-muted w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function DNAMatches({ matches }: { matches: DNAMatch[] }) {
  if (!matches.length) return null;

  return (
    <div className="rounded-2xl bg-card border border-card-border p-5 space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted flex items-center gap-2">
        <Dna className="h-4 w-4" />
        DNA Matches
      </h3>

      <div className="grid gap-3">
        {matches.map((m, i) => {
          const typeClass =
            TYPE_COLOR[m.match_type] ?? "text-zinc-400 bg-zinc-400/10 border-zinc-400/20";
          return (
            <div
              key={i}
              className="flex gap-4 rounded-xl bg-card-border/20 p-4 hover:bg-card-border/40 transition"
            >
              {/* Album art */}
              <div className="shrink-0 h-16 w-16 rounded-lg overflow-hidden bg-card-border/50 flex items-center justify-center">
                {m.album_art_url ? (
                  <img
                    src={m.album_art_url}
                    alt={`${m.artist} - ${m.title}`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <Music className="h-6 w-6 text-muted" />
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0 space-y-1.5">
                <div>
                  <p className="font-semibold text-sm leading-tight truncate">
                    {m.title}
                  </p>
                  <p className="text-xs text-muted truncate">{m.artist}</p>
                </div>

                <SimBar value={m.similarity} />

                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-md border ${typeClass}`}
                  >
                    {m.match_type.replace("_", " ")}
                  </span>
                </div>

                <p className="text-[11px] text-muted leading-relaxed">
                  {m.match_reason}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
