"use client";

import type { Segment } from "@/lib/types";
import { Layers } from "lucide-react";

const CLS_DOT: Record<string, string> = {
  "seg-intro": "bg-purple-500",
  "seg-verse": "bg-blue-500",
  "seg-pre-chorus": "bg-amber-500",
  "seg-chorus": "bg-red-500",
  "seg-bridge": "bg-green-500",
  "seg-outro": "bg-purple-400",
};

export default function Sections({ segments }: { segments: Segment[] }) {
  if (!segments.length) return null;

  return (
    <div className="rounded-2xl bg-card border border-card-border p-5 space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted flex items-center gap-2">
        <Layers className="h-4 w-4" />
        Sections
      </h3>

      <div className="grid gap-2">
        {segments.map((seg, i) => {
          const dur = seg.end_seconds - seg.start_seconds;
          const fmt = (s: number) => {
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60);
            return `${m}:${String(sec).padStart(2, "0")}`;
          };
          return (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg bg-card-border/20 px-4 py-2.5"
            >
              <span
                className={`h-2.5 w-2.5 rounded-full shrink-0 ${CLS_DOT[seg.cls] ?? "bg-zinc-500"}`}
              />
              <span className="font-medium text-sm w-24">{seg.label}</span>
              <span className="text-xs font-mono text-muted">
                {fmt(seg.start_seconds)} - {fmt(seg.end_seconds)}
              </span>
              <span className="text-xs text-muted ml-auto">
                {Math.round(dur)}s
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
