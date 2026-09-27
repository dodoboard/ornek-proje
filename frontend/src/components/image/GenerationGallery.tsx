import { Download } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { api, type GenerationRead } from "@/lib/api/client";

export function GenerationGallery({ generations }: { generations: GenerationRead[] }) {
  const items = generations.flatMap((generation) =>
    (generation.assets ?? []).map((asset) => ({ generation, asset })),
  );
  if (items.length === 0) {
    return <EmptyState title="No images yet">Generated images appear here.</EmptyState>;
  }
  return (
    <ul className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
      {items.map(({ generation, asset }) => {
        const placeholder = asset.metadata?.dev_placeholder === true;
        const seed = typeof asset.metadata?.seed === "number" ? asset.metadata.seed : null;
        return (
          <li key={asset.id} className="overflow-hidden rounded-md border border-border bg-surface-raised">
            <a href={api.assets.contentUrl(asset.id)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
              <img
                src={api.assets.thumbnailUrl(asset.id)}
                alt={String(generation.params?.prompt ?? "Generated image")}
                className="aspect-square w-full object-cover"
                loading="lazy"
              />
            </a>
            <div className="space-y-1 p-2">
              <div className="flex items-center justify-between gap-2">
                <Badge tone={placeholder ? "warning" : "accent"}>{placeholder ? "DEV PLACEHOLDER" : "AI generated"}</Badge>
                <a
                  href={api.assets.contentUrl(asset.id)}
                  download
                  aria-label="Download image"
                  className="text-muted hover:text-fg"
                >
                  <Download className="size-4" aria-hidden />
                </a>
              </div>
              <p className="truncate text-xs text-muted" title={generation.model_key}>
                {generation.model_key}
                {seed !== null ? ` · seed ${seed}` : ""}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
