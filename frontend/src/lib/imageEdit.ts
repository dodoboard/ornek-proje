/** Image Studio editing helpers (pure; mirrored by backend validation in ImageEditRequest). */

export type StudioMode = "generate" | "edit" | "inpaint" | "outpaint";
export type EditMode = Exclude<StudioMode, "generate">;

export interface EditCapabilities {
  text_to_image?: boolean;
  image_edit?: boolean;
  inpainting?: boolean;
  max_reference_images?: number;
  min_size?: number;
  max_size?: number;
  size_multiple?: number;
}

export const MODE_LABELS: Record<StudioMode, string> = {
  generate: "Generate",
  edit: "Edit",
  inpaint: "Inpaint",
  outpaint: "Outpaint",
};

/** Default strength per mode (backend DEFAULT_STRENGTH); instruction edits take none. */
export const DEFAULT_STRENGTH: Partial<Record<EditMode, number>> = { inpaint: 0.9, outpaint: 1 };

export function supportsMode(caps: EditCapabilities, mode: StudioMode): boolean {
  switch (mode) {
    case "generate":
      return caps.text_to_image !== false;
    case "edit":
      return caps.image_edit === true && (caps.max_reference_images ?? 0) >= 1;
    default:
      return caps.inpainting === true;
  }
}

/** Modes offered by at least one of the given models, in display order. */
export function availableModes(models: readonly { capabilities?: unknown }[]): StudioMode[] {
  const all: StudioMode[] = ["generate", "edit", "inpaint", "outpaint"];
  return all.filter((mode) => models.some((m) => supportsMode((m.capabilities ?? {}) as EditCapabilities, mode)));
}

/** Extra reference slots next to the source (edit mode: the source uses one slot). */
export function referenceSlots(caps: EditCapabilities, mode: EditMode): number {
  const max = caps.max_reference_images ?? 0;
  return Math.max(0, mode === "edit" ? max - 1 : max);
}

export interface Padding {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export const ZERO_PADDING: Padding = { left: 0, top: 0, right: 0, bottom: 0 };
export const PADDING_STEP = 64;
export const MAX_PADDING = 1024;

/** The backend crops sources down to a multiple of 16 before editing. */
export function snapDown(value: number, multiple = 16): number {
  return Math.floor(value / multiple) * multiple;
}

export function editOutputSize(
  source: { width: number; height: number },
  mode: EditMode,
  padding: Padding = ZERO_PADDING,
  multiple = 16,
): { width: number; height: number } {
  const width = snapDown(source.width, multiple);
  const height = snapDown(source.height, multiple);
  if (mode !== "outpaint") return { width, height };
  return { width: width + padding.left + padding.right, height: height + padding.top + padding.bottom };
}

/** Human-readable reason the edit cannot run, or null. */
export function editSizeError(
  caps: EditCapabilities,
  source: { width: number; height: number },
  mode: EditMode,
  padding: Padding = ZERO_PADDING,
): string | null {
  if (mode === "outpaint" && !Object.values(padding).some((v) => v > 0)) return "Extend at least one side.";
  const size = editOutputSize(source, mode, padding, caps.size_multiple ?? 16);
  const min = caps.min_size ?? 256;
  const max = caps.max_size ?? 2048;
  for (const [name, value] of [
    ["width", size.width],
    ["height", size.height],
  ] as const) {
    if (value < min || value > max) return `Result ${name} ${value}px is outside ${min}-${max}px for this model.`;
  }
  return null;
}

/**
 * Converts a painted overlay (any colour, alpha = coverage) into the mask format the backend expects:
 * opaque white where painted (alpha >= 128), opaque black elsewhere.
 */
export function overlayToMask(rgba: Uint8ClampedArray): Uint8ClampedArray<ArrayBuffer> {
  const out = new Uint8ClampedArray(rgba.length);
  for (let i = 0; i < rgba.length; i += 4) {
    const v = (rgba[i + 3] ?? 0) >= 128 ? 255 : 0;
    out[i] = v;
    out[i + 1] = v;
    out[i + 2] = v;
    out[i + 3] = 255;
  }
  return out;
}

export function hasPaint(rgba: Uint8ClampedArray): boolean {
  for (let i = 3; i < rgba.length; i += 4) if ((rgba[i] ?? 0) >= 128) return true;
  return false;
}
