"use client";

import { useCallback, useState } from "react";
import { Upload, Music, Loader2 } from "lucide-react";

interface Props {
  onFile: (file: File) => void;
  status: string | null;
}

export default function FileUpload({ onFile, status }: Props) {
  const [drag, setDrag] = useState(false);

  const handle = useCallback(
    (file: File) => {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext !== "mp3" && ext !== "wav") {
        alert("Only MP3 or WAV files are accepted.");
        return;
      }
      if (file.size > 20 * 1024 * 1024) {
        alert("File exceeds the 20 MB limit.");
        return;
      }
      onFile(file);
    },
    [onFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDrag(false);
      const f = e.dataTransfer.files[0];
      if (f) handle(f);
    },
    [handle],
  );

  const busy = status !== null;

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      className={`
        relative flex flex-col items-center justify-center gap-4 rounded-2xl
        border-2 border-dashed px-8 py-16 cursor-pointer transition-all
        ${
          drag
            ? "border-accent bg-accent-glow scale-[1.01]"
            : "border-card-border bg-card hover:border-accent/50 hover:bg-accent-glow/50"
        }
        ${busy ? "pointer-events-none opacity-60" : ""}
      `}
    >
      <input
        type="file"
        accept=".mp3,.wav"
        className="hidden"
        disabled={busy}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handle(f);
        }}
      />

      {busy ? (
        <Loader2 className="h-10 w-10 text-accent animate-spin" />
      ) : (
        <div className="flex items-center justify-center h-16 w-16 rounded-full bg-accent/10 border border-accent/20">
          <Upload className="h-7 w-7 text-accent" />
        </div>
      )}

      <div className="text-center">
        <p className="text-lg font-medium">
          {busy ? status : "Drop your track here"}
        </p>
        <p className="text-sm text-muted mt-1">
          {busy ? "This usually takes 10-20 seconds" : "MP3 or WAV, up to 20 MB"}
        </p>
      </div>

      {!busy && (
        <div className="flex items-center gap-2 mt-2 text-xs text-muted">
          <Music className="h-3.5 w-3.5" />
          <span>or click to browse</span>
        </div>
      )}
    </label>
  );
}
