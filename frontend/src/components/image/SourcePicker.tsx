"use client";

import clsx from "clsx";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { api, type ApiError, type AssetRead, type GenerationRead } from "@/lib/api/client";

const ACCEPT = "image/jpeg,image/png,image/webp";

/** Pick the image to edit: one of the recent outputs or a new upload. */
export function SourcePicker({
  recent,
  value,
  onChange,
}: {
  recent: GenerationRead[];
  value: AssetRead | null;
  onChange: (asset: AssetRead) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const assets = recent.flatMap((g) => g.assets ?? []).slice(0, 12);
  const options = value && !assets.some((a) => a.id === value.id) ? [value, ...assets] : assets;

  async function upload(file: File | undefined) {
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      onChange(await api.assets.upload(file));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted">Source image</p>
      <div role="radiogroup" aria-label="Source image" className="flex flex-wrap gap-2">
        {options.map((asset) => (
          <button
            key={asset.id}
            type="button"
            role="radio"
            aria-checked={value?.id === asset.id}
            aria-label={`Source ${asset.id}`}
            onClick={() => onChange(asset)}
            className={clsx(
              "size-16 overflow-hidden rounded-md border",
              value?.id === asset.id ? "border-accent ring-2 ring-accent" : "border-border",
            )}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
            <img src={api.assets.thumbnailUrl(asset.id)} alt="" className="size-full object-cover" />
          </button>
        ))}
        <Button variant="ghost" disabled={uploading} onClick={() => input.current?.click()} className="h-16">
          {uploading ? "Uploading…" : "Upload"}
        </Button>
      </div>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        hidden
        aria-label="Upload source image"
        onChange={(e) => void upload(e.target.files?.[0])}
      />
      {error && (
        <p role="alert" className="mt-1 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
