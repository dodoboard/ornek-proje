import type { BadgeTone } from "@/components/ui/Badge";
import type { ProviderInfo, ProviderKind, ProviderStatus } from "@/lib/api/client";

export const KIND_LABELS: Record<ProviderKind, string> = {
  image: "Image generation",
  video: "Video generation",
  llm: "Script LLM",
  tts: "Text-to-speech",
  lipsync: "Lip-sync",
  asr: "Captions (speech recognition)",
  segmentation: "Segmentation",
  upscale: "Upscaling",
};

export const STATUS_LABELS: Record<ProviderStatus, string> = {
  available: "Ready",
  model_missing: "Not downloaded",
  not_installed: "Packages missing",
  not_implemented: "Not implemented",
  disabled: "Disabled",
};

export function statusTone(status: ProviderStatus): BadgeTone {
  switch (status) {
    case "available":
      return "success";
    case "model_missing":
    case "not_installed":
      return "warning";
    default:
      return "neutral";
  }
}

/** A model can be chosen as default only if an integration exists for it. */
export function isSelectable(provider: ProviderInfo): boolean {
  return provider.status !== "not_implemented" && provider.status !== "disabled";
}

/** Human-readable list of enabled boolean capabilities (e.g. "image edit", "inpainting"). */
export function capabilityFlags(capabilities: ProviderInfo["capabilities"]): string[] {
  if (!capabilities) return [];
  return Object.entries(capabilities)
    .filter(([, value]) => value === true)
    .map(([key]) => key.replace(/_/g, " "));
}

/** Verification labels already conveyed by the maturity badge (or "verified") are not repeated. */
export function showVerification(verification: string): boolean {
  return !["verified", "experimental", "dev-only"].includes(verification);
}
