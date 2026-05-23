import type { AnalysisResult } from "./types";

const API =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function uploadFile(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API}/analyze`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Upload failed");
  }
  const data = await res.json();
  return data.job_id as string;
}

export async function pollJob(jobId: string): Promise<AnalysisResult> {
  const res = await fetch(`${API}/analyze/${jobId}`);
  if (!res.ok) throw new Error("Poll failed");
  return res.json();
}

/**
 * Upload, then poll until complete or error.
 * Calls `onProgress` on each poll tick so the UI can update.
 */
export async function analyzeFile(
  file: File,
  onProgress?: (status: string) => void,
): Promise<AnalysisResult> {
  onProgress?.("Uploading...");
  const jobId = await uploadFile(file);
  onProgress?.("Analyzing...");

  for (let i = 0; i < 120; i++) {
    await new Promise((r) => setTimeout(r, 2500));
    const result = await pollJob(jobId);
    if (result.status === "complete") return result;
    if (result.status === "error") throw new Error(result.error ?? "Analysis failed");
    onProgress?.(`Analyzing... (${i + 1})`);
  }
  throw new Error("Analysis timed out");
}
