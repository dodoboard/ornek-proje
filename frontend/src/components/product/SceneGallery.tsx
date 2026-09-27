import { Download } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { api, type GenerationRead } from "@/lib/api/client";
import { reportFor, scaleNote } from "@/lib/productStudio";

export function SceneGallery({ generations }: { generations: GenerationRead[] }) {
  const items = generations.flatMap((generation) =>
    (generation.assets ?? []).map((asset, index) => ({ generation, asset, report: reportFor(generation, index) })),
  );
  if (items.length === 0) {
    return <EmptyState title="No scenes yet">Scenes with your product appear here.</EmptyState>;
  }
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {items.map(({ generation, asset, report }) => {
        const placeholder = asset.metadata?.dev_placeholder === true;
        const background = asset.metadata?.background === "user_photo" ? "your photo" : "AI background";
        return (
          <li key={asset.id} className="overflow-hidden rounded-md border border-border bg-surface-raised">
            <a href={api.assets.contentUrl(asset.id)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
              <img
                src={api.assets.thumbnailUrl(asset.id)}
                alt={String(generation.params?.scene ?? "Product scene")}
                className="aspect-square w-full object-cover"
                loading="lazy"
              />
            </a>
            <div className="space-y-1 p-2">
              <div className="flex flex-wrap items-center gap-1">
                {report?.exact ? (
                  <Badge tone="success">Product pixels verified</Badge>
                ) : (
                  <Badge tone="danger">Not verified</Badge>
                )}
                {placeholder && <Badge tone="warning">DEV PLACEHOLDER</Badge>}
                <a
                  href={api.assets.contentUrl(asset.id)}
                  download
                  aria-label="Download scene"
                  className="ml-auto text-muted hover:text-fg"
                >
                  <Download className="size-4" aria-hidden />
                </a>
              </div>
              <p className="text-xs text-muted">
                {report ? scaleNote(report) : "no report"} · {background}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
