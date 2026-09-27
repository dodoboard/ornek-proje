"use client";

import { X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { api, type ApiError } from "@/lib/api/client";

const MAX_REFERENCES = 8;

export function ReferencesPanel({
  characterId,
  assetIds,
  onChanged,
}: {
  characterId: string;
  assetIds: string[];
  onChanged: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function upload(files: FileList | null) {
    const list = Array.from(files ?? []).slice(0, MAX_REFERENCES - assetIds.length);
    for (const file of list) {
      const asset = await api.assets.upload(file);
      await api.characters.attachAsset(characterId, asset.id, "reference");
    }
  }

  return (
    <div>
      <p className="mb-2 text-xs text-muted">
        Optional photos that define the look (used when generating candidates). Real people require consent.
      </p>
      <div className="flex flex-wrap gap-2">
        {assetIds.map((id) => (
          <div key={id} className="relative size-16 overflow-hidden rounded-md border border-border">
            {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
            <img src={api.assets.thumbnailUrl(id)} alt="Reference" className="size-full object-cover" />
            <button
              type="button"
              aria-label="Remove reference"
              disabled={busy}
              onClick={() => void run(() => api.characters.detachAsset(characterId, id))}
              className="absolute right-0.5 top-0.5 rounded bg-black/60 p-0.5"
            >
              <X className="size-3" aria-hidden />
            </button>
          </div>
        ))}
        {assetIds.length < MAX_REFERENCES && (
          <Button variant="ghost" className="h-16" disabled={busy} onClick={() => input.current?.click()}>
            {busy ? "Uploading…" : "Add photo"}
          </Button>
        )}
      </div>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        aria-label="Upload reference photos"
        onChange={(e) => void run(() => upload(e.target.files))}
      />
      {error && (
        <p role="alert" className="mt-1 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
