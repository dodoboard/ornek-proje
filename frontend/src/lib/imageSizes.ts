/** Aspect presets sized to multiples of 16 (FLUX.2 requirement) at roughly 1 megapixel. */
export const ASPECT_PRESETS = [
  { id: "1:1", label: "1:1", width: 1024, height: 1024 },
  { id: "4:5", label: "4:5", width: 896, height: 1120 },
  { id: "9:16", label: "9:16", width: 768, height: 1360 },
  { id: "16:9", label: "16:9", width: 1360, height: 768 },
] as const;

export type AspectId = (typeof ASPECT_PRESETS)[number]["id"];

export function presetById(id: string) {
  return ASPECT_PRESETS.find((preset) => preset.id === id) ?? ASPECT_PRESETS[0];
}

export const MAX_SEED = 2 ** 32 - 17;

export function parseSeed(raw: string): number | null {
  const trimmed = raw.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const value = Number(trimmed);
  return Number.isSafeInteger(value) && value <= MAX_SEED ? value : null;
}
