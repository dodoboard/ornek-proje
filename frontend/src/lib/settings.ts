import type { PerformanceProfile } from "@/lib/api/client";

export const PERFORMANCE_PROFILES: readonly { value: PerformanceProfile; label: string; description: string }[] = [
  {
    value: "performance",
    label: "Performance",
    description: "Keeps the model fully on the GPU. Fastest, needs the most VRAM.",
  },
  {
    value: "balanced",
    label: "Balanced",
    description: "Moves model parts to the GPU only while they run (model CPU offload). Recommended for 16 GB.",
  },
  {
    value: "low_vram",
    label: "Low VRAM",
    description:
      "Sequential offload, VAE tiling, attention slicing, and unloads the model after every job. Much slower.",
  },
];
