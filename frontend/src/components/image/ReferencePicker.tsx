"use client";

import { X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { api, type ApiError, type AssetRead } from "@/lib/api/client";

const ACCEPT = "image/jpeg,image/png,image/webp";

export function ReferencePicker({
  max,
  value,
  onChange,
}: {
  max: number;
  value: AssetRead[];
  onChange: (assets: AssetRead[]) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    setUploading(true);
    try {
      const room = Math.max(0, max - value.length);
      const uploaded: AssetRead[] = [];
      for (const file of Array.from(files).slice(0, room)) {
        uploaded.push(await api.assets.upload(file));
      }
      onChange([...value, ...uploaded]);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted">
        Reference images ({value.length}/{max})
      </p>
      <div className="flex flex-wrap gap-2">
        {value.map((asset) => (
          <div key={asset.id} className="relative size-16 overflow-hidden rounded-md border border-border">
            {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
            <img src={api.assets.thumbnailUrl(asset.id)} alt="Reference" className="size-full object-cover" />
            <button
              type="button"
              aria-label="Remove reference"
              onClick={() => onChange(value.filter((a) => a.id !== asset.id))}
              className="absolute right-0.5 top-0.5 rounded bg-black/60 p-0.5"
            >
              <X className="size-3" aria-hidden />
            </button>
          </div>
        ))}
        {value.length < max && (
          <Button variant="ghost" disabled={uploading} onClick={() => input.current?.click()} className="h-16">
            {uploading ? "Uploading…" : "Add"}
          </Button>
        )}
      </div>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        aria-label="Upload reference images"
        onChange={(e) => void handleFiles(e.target.files)}
      />
      {error && (
        <p role="alert" className="mt-1 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
