"use client";

import { useMemo } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";
import type { EmotionalArc, HitMoment } from "@/lib/types";
import { Zap } from "lucide-react";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

interface Props {
  arc: EmotionalArc;
  hitMoment: HitMoment | null;
  duration: number;
}

export default function EmotionalArcChart({ arc, hitMoment, duration }: Props) {
  const data = useMemo(() => {
    const labels = arc.timestamps.map((t) => {
      const m = Math.floor(t / 60);
      const s = Math.floor(t % 60);
      return `${m}:${String(s).padStart(2, "0")}`;
    });

    return {
      labels,
      datasets: [
        {
          label: "Energy",
          data: arc.energy,
          borderColor: "#f97316",
          backgroundColor: "rgba(249,115,22,0.08)",
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: "Tension",
          data: arc.tension,
          borderColor: "#ef4444",
          backgroundColor: "rgba(239,68,68,0.06)",
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: "Valence",
          data: arc.valence,
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59,130,246,0.06)",
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    };
  }, [arc]);

  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index" as const,
        intersect: false,
      },
      plugins: {
        legend: {
          position: "top" as const,
          labels: {
            color: "#a1a1aa",
            boxWidth: 12,
            padding: 16,
            usePointStyle: true,
            font: { size: 11 },
          },
        },
        tooltip: {
          backgroundColor: "#18181b",
          borderColor: "#27272a",
          borderWidth: 1,
          titleColor: "#e4e4e7",
          bodyColor: "#a1a1aa",
          padding: 10,
          cornerRadius: 8,
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: "#52525b",
            maxTicksLimit: 10,
            font: { size: 10 },
          },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: "rgba(63,63,70,0.3)" },
          ticks: {
            color: "#52525b",
            stepSize: 25,
            font: { size: 10 },
          },
        },
      },
    }),
    [],
  );

  return (
    <div className="rounded-2xl bg-card border border-card-border p-5 space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
        Emotional Arc
      </h3>

      <div className="chart-wrapper h-[220px]">
        <Line data={data} options={options} />
      </div>

      {hitMoment && (
        <div className="flex items-start gap-3 rounded-xl bg-accent-glow border border-accent/20 p-4">
          <Zap className="h-5 w-5 text-accent mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-accent">
              {hitMoment.label} at{" "}
              {Math.floor(hitMoment.time_seconds / 60)}:
              {String(Math.floor(hitMoment.time_seconds % 60)).padStart(2, "0")}
            </p>
            <p className="text-xs text-muted mt-1">{hitMoment.explanation}</p>
          </div>
        </div>
      )}
    </div>
  );
}
