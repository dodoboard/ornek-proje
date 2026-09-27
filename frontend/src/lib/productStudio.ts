/** Product Studio helpers (mirror backend app/services/compositing.place and product_studio.placed_size). */

import type { AssetLinkRead, GenerationRead } from "@/lib/api/client";

export interface Placement {
  x: number;
  y: number;
  height_ratio: number;
  native_scale: boolean;
}

export const DEFAULT_PLACEMENT: Placement = { x: 0.5, y: 0.85, height_ratio: 0.5, native_scale: false };

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Where the product lands on the canvas, or an error when it does not fit. */
export function placementBox(
  cutout: { width: number; height: number },
  canvas: { width: number; height: number },
  p: Placement,
): { box: Box; scale: number } | { error: string } {
  let width = cutout.width;
  let height = cutout.height;
  if (!p.native_scale) {
    height = Math.max(1, Math.round(p.height_ratio * canvas.height));
    width = Math.max(1, Math.round((cutout.width * height) / cutout.height));
  }
  if (width > canvas.width || height > canvas.height) {
    return {
      error: `The product (${width}x${height}px) does not fit the ${canvas.width}x${canvas.height}px image; lower its size or use a larger format.`,
    };
  }
  const left = Math.round(p.x * canvas.width - width / 2);
  const top = Math.round(p.y * canvas.height) - height;
  return {
    box: {
      left: Math.min(Math.max(left, 0), canvas.width - width),
      top: Math.min(Math.max(top, 0), canvas.height - height),
      width,
      height,
    },
    scale: height / cutout.height,
  };
}

export function assetsWithRole(links: AssetLinkRead[], role: string) {
  return links.filter((l) => l.role === role).map((l) => l.asset);
}

export interface PreservationReport {
  exact: boolean;
  scale: number;
  resampled: boolean;
  upscaled: boolean;
  protected_pixels: number;
  opaque_product_pixels: number;
  clamped_to_frame: boolean;
}

/** Preservation report for the n-th output of a product_scene generation. */
export function reportFor(generation: GenerationRead, index: number): PreservationReport | null {
  const reports = generation.params?.preservation;
  if (!Array.isArray(reports)) return null;
  const report = reports[index] as PreservationReport | undefined;
  return report ?? null;
}

export function scaleNote(report: PreservationReport): string {
  if (!report.resampled) return "1:1 original pixels";
  return `${report.upscaled ? "upscaled" : "scaled"} ×${report.scale.toFixed(2)} from the original`;
}
