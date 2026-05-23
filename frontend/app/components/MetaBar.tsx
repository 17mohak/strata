"use client";

import type { Meta } from "@/lib/types";
import { Music2, Clock, Gauge, Key } from "lucide-react";

function Pill({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-xl bg-card border border-card-border px-4 py-2.5">
      <Icon className="h-4 w-4 text-accent" />
      <span className="text-xs text-muted uppercase tracking-wider">{label}</span>
      <span className="text-sm font-semibold">{value}</span>
    </div>
  );
}

export default function MetaBar({ meta, fileName }: { meta: Meta; fileName?: string }) {
  const mins = Math.floor(meta.duration_seconds / 60);
  const secs = Math.floor(meta.duration_seconds % 60);

  return (
    <div className="space-y-3">
      <h2 className="text-xl font-bold tracking-tight">
        {meta.title ?? fileName ?? "Untitled Track"}
      </h2>

      <div className="flex flex-wrap gap-2">
        <Pill icon={Key} label="Key" value={`${meta.key} ${meta.mode}`} />
        <Pill icon={Gauge} label="BPM" value={String(meta.tempo)} />
        <Pill icon={Clock} label="Duration" value={`${mins}:${String(secs).padStart(2, "0")}`} />
        <Pill icon={Music2} label="Time" value={meta.time_signature} />
        {meta.progression && (
          <Pill icon={Music2} label="Prog" value={meta.progression} />
        )}
      </div>
    </div>
  );
}
