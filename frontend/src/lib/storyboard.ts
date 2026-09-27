import type { ScriptRead, ShotRead, ShotUpdate } from "@/lib/api/client";

type Choice<K extends keyof ShotUpdate> = NonNullable<ShotUpdate[K]>;

export const SHOT_TYPES: Record<Choice<"type">, string> = {
  hook: "Hook",
  talking_head: "Talking head",
  product_closeup: "Product close-up",
  product_in_use: "Product in use",
  broll: "B-roll",
  property_exterior: "Property exterior",
  property_interior: "Property interior",
  land_overview: "Land overview",
  text_card: "Text card",
  cta: "Call to action",
};

export const METHODS: Record<Choice<"generation_method">, string> = {
  ai_video: "AI video",
  ai_image: "AI image",
  lipsync: "Lip-sync presenter",
  product_composite: "Original product composite",
  ffmpeg_motion: "Motion graphics (no AI)",
  real_footage: "Real footage",
};

export const DISCLOSURES: Record<Choice<"disclosure_label">, string> = {
  ai_generated: "AI generated",
  ai_enhanced: "AI enhanced",
  representative_visualization: "Representative visualization",
  real_footage: "Real footage",
  no_ai: "No AI (graphics)",
};

export const CAMERAS: Record<Choice<"camera">, string> = {
  wide: "Wide",
  medium: "Medium",
  close_up: "Close-up",
  extreme_close_up: "Extreme close-up",
  over_the_shoulder: "Over the shoulder",
  top_down: "Top-down",
};

export const MOTIONS: Record<Choice<"camera_motion">, string> = {
  static: "Static",
  slow_push_in: "Slow push-in",
  pull_out: "Pull out",
  pan_left: "Pan left",
  pan_right: "Pan right",
  tilt_up: "Tilt up",
  tilt_down: "Tilt down",
  orbit: "Orbit",
  handheld: "Handheld",
};

export function options<T extends string>(labels: Record<T, string>) {
  return (Object.keys(labels) as T[]).map((value) => ({ value, label: labels[value] }));
}

export function labelOf(labels: Record<string, string>, value: string): string {
  return labels[value] ?? value.replace(/_/g, " ");
}

/** Move one id to a new index (used for drag-and-drop and the keyboard up/down buttons). */
export function move<T>(items: readonly T[], from: number, to: number): T[] {
  const next = [...items];
  const [item] = next.splice(from, 1);
  if (item === undefined) return next;
  next.splice(Math.max(0, Math.min(to, next.length)), 0, item);
  return next;
}

export function durationSummary(shots: Pick<ShotRead, "duration_s">[], target: number | undefined) {
  const total = Math.round(shots.reduce((sum, s) => sum + s.duration_s, 0) * 10) / 10;
  const diff = target ? Math.round((total - target) * 10) / 10 : 0;
  return { total, diff, ok: !target || Math.abs(diff) <= Math.max(1, target * 0.1) };
}

/** Human summary of how the script was produced (including why the LLM output was rejected). */
export function scriptOrigin(script: ScriptRead): { label: string; tone: "success" | "warning"; reasons: string[] } {
  const reasons = script.attempts.flatMap((a) => (Array.isArray(a.errors) ? (a.errors as string[]) : []));
  if (script.source === "llm") {
    const repaired = script.attempts.length > 1;
    return { label: `LLM · ${script.llm_model ?? "local"}${repaired ? " (repaired once)" : ""}`, tone: "success", reasons };
  }
  return { label: script.attempts.length ? "Template fallback" : "Template", tone: "warning", reasons };
}
