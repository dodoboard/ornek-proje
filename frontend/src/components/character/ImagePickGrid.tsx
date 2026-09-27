import clsx from "clsx";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { api } from "@/lib/api/client";
import type { GeneratedImage } from "@/lib/characters";

export function ImagePickGrid({
  images,
  selectedId,
  actionLabel,
  onPick,
  pending,
  emptyText,
}: {
  images: GeneratedImage[];
  selectedId: string | null;
  actionLabel: string;
  onPick: (assetId: string) => void;
  pending: boolean;
  emptyText: string;
}) {
  if (images.length === 0) return <EmptyState title="Nothing generated yet">{emptyText}</EmptyState>;
  return (
    <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {images.map(({ asset, seed }) => {
        const selected = asset.id === selectedId;
        const placeholder = asset.metadata?.dev_placeholder === true;
        return (
          <li
            key={asset.id}
            className={clsx(
              "overflow-hidden rounded-md border bg-surface-raised",
              selected ? "border-accent ring-1 ring-accent" : "border-border",
            )}
          >
            <a href={api.assets.contentUrl(asset.id)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
              <img src={api.assets.thumbnailUrl(asset.id)} alt="" className="aspect-[4/5] w-full object-cover" />
            </a>
            <div className="flex items-center justify-between gap-2 p-2">
              <span className="truncate text-xs text-muted">
                {placeholder ? "dev · " : ""}
                {seed !== null ? `seed ${seed}` : ""}
              </span>
              {selected ? (
                <span className="text-xs font-medium text-accent">Selected</span>
              ) : (
                <Button variant="ghost" className="px-2 py-1 text-xs" disabled={pending} onClick={() => onPick(asset.id)}>
                  {actionLabel}
                </Button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
