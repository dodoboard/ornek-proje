import type { Option } from "@/components/ui/Field";
import type { ProjectSettings, ProjectType } from "@/lib/api/client";

export const PROJECT_TYPES: readonly Option<ProjectType>[] = [
  { value: "product_ad", label: "Product ad" },
  { value: "real_estate", label: "Real estate" },
  { value: "land", label: "Land" },
  { value: "social", label: "Social" },
  { value: "custom", label: "Custom" },
];

export const PLATFORMS: readonly Option<NonNullable<ProjectSettings["platform"]>>[] = [
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "youtube_shorts", label: "YouTube Shorts" },
  { value: "youtube", label: "YouTube" },
  { value: "generic", label: "Generic" },
];

export const ASPECT_RATIOS: readonly Option<NonNullable<ProjectSettings["aspect_ratio"]>>[] = [
  { value: "9:16", label: "9:16 (vertical)" },
  { value: "16:9", label: "16:9 (landscape)" },
  { value: "1:1", label: "1:1 (square)" },
  { value: "4:5", label: "4:5 (portrait)" },
];

export const DURATIONS: readonly Option<NonNullable<ProjectSettings["duration_s"]>>[] = [
  { value: 15, label: "15 s" },
  { value: 30, label: "30 s" },
  { value: 60, label: "60 s" },
];

export const TONES: readonly Option<NonNullable<ProjectSettings["tone"]>>[] = [
  { value: "professional", label: "Professional" },
  { value: "luxury", label: "Luxury" },
  { value: "friendly", label: "Friendly" },
  { value: "energetic", label: "Energetic" },
  { value: "minimal", label: "Minimal" },
  { value: "cinematic", label: "Cinematic" },
];

export const LANGUAGES: readonly Option<string>[] = [
  { value: "tr", label: "Türkçe" },
  { value: "en", label: "English" },
];

export function projectTypeLabel(type: ProjectType): string {
  return PROJECT_TYPES.find((option) => option.value === type)?.label ?? type;
}
