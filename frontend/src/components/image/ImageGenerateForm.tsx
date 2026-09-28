"use client";

import clsx from "clsx";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import type { AssetRead, ImageGenerateRequest, ProviderInfo } from "@/lib/api/client";
import { ASPECT_PRESETS, parseSeed, presetById, type AspectId } from "@/lib/imageSizes";

import { ReferencePicker } from "./ReferencePicker";

interface Capabilities {
  max_reference_images?: number;
  guidance?: boolean;
  default_steps?: number;
  max_images_per_request?: number;
}

interface ImageGenerateFormProps {
  models: ProviderInfo[];
  defaultModelKey: string | null;
  onSubmit: (request: ImageGenerateRequest) => void;
  pending: boolean;
  error?: string | null;
}

export function ImageGenerateForm({ models, defaultModelKey, onSubmit, pending, error }: ImageGenerateFormProps) {
  const [modelKey, setModelKey] = useState(defaultModelKey ?? models[0]?.key ?? "");
  const model = models.find((m) => m.key === modelKey);
  const caps = (model?.capabilities ?? {}) as Capabilities;

  const [prompt, setPrompt] = useState("");
  const [aspect, setAspect] = useState<AspectId>("9:16");
  const [steps, setSteps] = useState<string>("");
  const [seed, setSeed] = useState("");
  const [count, setCount] = useState(1);
  const [guidance, setGuidance] = useState("4");
  const [references, setReferences] = useState<AssetRead[]>([]);

  const maxRefs = caps.max_reference_images ?? 0;
  const maxCount = caps.max_images_per_request ?? 4;
  const seedValue = seed.trim() ? parseSeed(seed) : null;
  const seedInvalid = seed.trim() !== "" && seedValue === null;
  const stepsValue = steps.trim() ? Number(steps) : null;
  const stepsInvalid = stepsValue !== null && !(Number.isInteger(stepsValue) && stepsValue >= 1 && stepsValue <= 150);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!prompt.trim() || !model || seedInvalid || stepsInvalid) return;
    const size = presetById(aspect);
    onSubmit({
      prompt: prompt.trim(),
      model_key: model.key,
      width: size.width,
      height: size.height,
      num_images: Math.min(count, maxCount),
      steps: stepsValue,
      seed: seedValue,
      guidance_scale: caps.guidance ? Number(guidance) : null,
      reference_asset_ids: references.slice(0, maxRefs).map((r) => r.id),
    });
  }

  if (models.length === 0) {
    return (
      <p className="text-sm text-muted">
        No image model is ready. Open the Models page: download a FLUX.2 model (and install the AI packages), or enable
        dev placeholders for UI testing.
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4" aria-label="Generate image">
      <SelectField
        label="Model"
        options={models.map((m) => ({ value: m.key, label: m.maturity === "dev_only" ? `${m.key} (dev placeholder)` : m.key }))}
        value={modelKey}
        onChange={(e) => {
          setModelKey(e.target.value);
          setReferences([]);
        }}
      />
      <div>
        <label htmlFor="prompt" className="mb-1 block text-xs font-medium text-muted">
          Prompt
        </label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          maxLength={2000}
          placeholder="Studio portrait of an adult woman, soft window light, 85mm"
          className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>

      <div>
        <p className="mb-1 text-xs font-medium text-muted">Format</p>
        <div role="radiogroup" aria-label="Format" className="flex flex-wrap gap-2">
          {ASPECT_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              role="radio"
              aria-checked={aspect === preset.id}
              onClick={() => setAspect(preset.id)}
              className={clsx(
                "rounded-md border px-3 py-1.5 text-xs",
                aspect === preset.id ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-raised",
              )}
            >
              {preset.label} <span className="text-muted">{preset.width}×{preset.height}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <TextField
          label={`Steps (default ${caps.default_steps ?? "model"})`}
          inputMode="numeric"
          value={steps}
          onChange={(e) => setSteps(e.target.value)}
          aria-invalid={stepsInvalid}
        />
        <TextField
          label="Seed (empty = random)"
          inputMode="numeric"
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          aria-invalid={seedInvalid}
        />
        <SelectField
          label="Images"
          options={Array.from({ length: maxCount }, (_, i) => ({ value: i + 1, label: String(i + 1) }))}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
        />
      </div>

      {caps.guidance && (
        <TextField
          label="Guidance scale"
          inputMode="decimal"
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
        />
      )}

      {maxRefs > 0 && <ReferencePicker max={maxRefs} value={references} onChange={setReferences} />}

      {(seedInvalid || stepsInvalid) && (
        <p role="alert" className="text-xs text-danger">
          {seedInvalid ? "Seed must be a whole number. " : ""}
          {stepsInvalid ? "Steps must be between 1 and 150." : ""}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" disabled={pending || !prompt.trim() || seedInvalid || stepsInvalid}>
        {pending ? "Queueing…" : "Generate"}
      </Button>
    </form>
  );
}
