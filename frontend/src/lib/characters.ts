import type { AssetRead, CharacterPurpose, GenerationRead, ViewRole } from "@/lib/api/client";

export const VIEW_LABELS: Record<ViewRole, string> = {
  canonical: "Canonical portrait",
  front: "Front view",
  three_quarter: "3/4 view",
  full_body: "Full body",
};

export const VIEW_PURPOSES: readonly Exclude<ViewRole, "canonical">[] = ["front", "three_quarter", "full_body"];

export interface GeneratedImage {
  asset: AssetRead;
  generation: GenerationRead;
  seed: number | null;
}

/** Newest-first images produced for a character by one workflow step. */
export function imagesForPurpose(generations: GenerationRead[], purpose: CharacterPurpose): GeneratedImage[] {
  return generations
    .filter((g) => g.params?.purpose === purpose)
    .flatMap((generation) =>
      (generation.assets ?? []).map((asset) => ({
        asset,
        generation,
        seed: typeof asset.metadata?.seed === "number" ? asset.metadata.seed : null,
      })),
    );
}

/** Parse one trait per line or comma; trims and drops empties. */
export function parseTraits(text: string): string[] {
  return text
    .split(/[\n,]/)
    .map((t) => t.trim())
    .filter(Boolean);
}
