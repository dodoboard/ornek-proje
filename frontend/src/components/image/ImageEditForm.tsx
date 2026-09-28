"use client";

import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import type { ApiError, AssetRead, GenerationRead, ImageEditRequest, ProviderInfo } from "@/lib/api/client";
import {
  DEFAULT_STRENGTH,
  editSizeError,
  referenceSlots,
  ZERO_PADDING,
  type EditCapabilities,
  type EditMode,
  type Padding,
} from "@/lib/imageEdit";
import { parseSeed } from "@/lib/imageSizes";

import { MaskEditor, type MaskHandle } from "./MaskEditor";
import { OutpaintControls } from "./OutpaintControls";
import { ReferencePicker } from "./ReferencePicker";
import { SourcePicker } from "./SourcePicker";

interface Capabilities extends EditCapabilities {
  guidance?: boolean;
  default_steps?: number;
  max_images_per_request?: number;
}

type SizedAsset = AssetRead & { width: number; height: number };

const PLACEHOLDERS: Record<EditMode, string> = {
  edit: "Change the jacket to red leather, keep everything else",
  inpaint: "A ceramic coffee cup on the table",
  outpaint: "Continue the beach and sky naturally",
};

function sized(asset: AssetRead | null): SizedAsset | null {
  return asset && asset.width && asset.height ? (asset as SizedAsset) : null;
}

export function ImageEditForm({
  mode,
  models,
  defaultModelKey,
  recent,
  onSubmit,
  pending,
  error,
}: {
  mode: EditMode;
  models: ProviderInfo[];
  defaultModelKey: string | null;
  recent: GenerationRead[];
  onSubmit: (request: ImageEditRequest) => void;
  pending: boolean;
  error?: string | null;
}) {
  const [modelKey, setModelKey] = useState(defaultModelKey ?? models[0]?.key ?? "");
  const model = models.find((m) => m.key === modelKey) ?? models[0];
  const caps = (model?.capabilities ?? {}) as Capabilities;

  const [source, setSource] = useState<AssetRead | null>(null);
  const [prompt, setPrompt] = useState("");
  const [padding, setPadding] = useState<Padding>({ ...ZERO_PADDING, bottom: 256 });
  const [strength, setStrength] = useState(String(DEFAULT_STRENGTH[mode] ?? ""));
  const [feather, setFeather] = useState("8");
  const [steps, setSteps] = useState("");
  const [seed, setSeed] = useState("");
  const [count, setCount] = useState(1);
  const [guidance, setGuidance] = useState("4");
  const [references, setReferences] = useState<AssetRead[]>([]);
  const [painted, setPainted] = useState(false);
  const [maskBusy, setMaskBusy] = useState(false);
  const [maskError, setMaskError] = useState<string | null>(null);
  const mask = useRef<MaskHandle | null>(null);

  const src = sized(source);
  const refSlots = referenceSlots(caps, mode);
  const maxCount = caps.max_images_per_request ?? 4;
  const seedValue = seed.trim() ? parseSeed(seed) : null;
  const stepsValue = steps.trim() ? Number(steps) : null;
  const strengthValue = Number(strength);
  const featherValue = Number(feather);

  const problems = [
    seed.trim() && seedValue === null ? "Seed must be a whole number." : null,
    stepsValue !== null && !(Number.isInteger(stepsValue) && stepsValue >= 1 && stepsValue <= 150)
      ? "Steps must be between 1 and 150."
      : null,
    mode !== "edit" && !(strengthValue >= 0.05 && strengthValue <= 1) ? "Strength must be between 0.05 and 1." : null,
    mode !== "edit" && !(Number.isInteger(featherValue) && featherValue >= 0 && featherValue <= 64)
      ? "Feather must be 0-64 px."
      : null,
    source && !src ? "This file has no readable image size; pick another source." : null,
    src ? editSizeError(caps, src, mode, padding) : null,
  ].filter((p): p is string => p !== null);

  const ready = Boolean(model && src && prompt.trim() && problems.length === 0 && (mode !== "inpaint" || painted));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready || !model || !src) return;
    let maskId: string | null = null;
    if (mode === "inpaint") {
      setMaskError(null);
      setMaskBusy(true);
      try {
        maskId = (await mask.current!.exportMask()).id;
      } catch (e) {
        setMaskError((e as ApiError | Error).message);
        return;
      } finally {
        setMaskBusy(false);
      }
    }
    onSubmit({
      mode,
      source_asset_id: src.id,
      prompt: prompt.trim(),
      model_key: model.key,
      mask_asset_id: maskId,
      padding: mode === "outpaint" ? padding : null,
      strength: mode === "edit" ? null : strengthValue,
      feather: mode === "edit" ? 8 : featherValue,
      steps: stepsValue,
      seed: seedValue,
      num_images: Math.min(count, maxCount),
      guidance_scale: caps.guidance ? Number(guidance) : null,
      reference_asset_ids: references.slice(0, refSlots).map((r) => r.id),
    });
  }

  if (models.length === 0) {
    return <p className="text-sm text-muted">No ready image model supports this mode.</p>;
  }

  return (
    <form onSubmit={submit} className="space-y-4" aria-label={`${mode} image`}>
      <SelectField
        label="Model"
        options={models.map((m) => ({ value: m.key, label: m.maturity === "dev_only" ? `${m.key} (dev placeholder)` : m.key }))}
        value={model?.key ?? ""}
        onChange={(e) => {
          setModelKey(e.target.value);
          setReferences([]);
        }}
      />
      <SourcePicker recent={recent} value={source} onChange={setSource} />

      {mode === "inpaint" && src && <MaskEditor source={src} handle={mask} onPaintedChange={setPainted} />}
      {mode === "outpaint" && src && <OutpaintControls source={src} value={padding} onChange={setPadding} />}

      <div>
        <label htmlFor="edit-prompt" className="mb-1 block text-xs font-medium text-muted">
          {mode === "edit" ? "Instruction" : "Prompt for the new area"}
        </label>
        <textarea
          id="edit-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          maxLength={2000}
          placeholder={PLACEHOLDERS[mode]}
          className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>

      {mode !== "edit" && (
        <div className="grid gap-4 md:grid-cols-2">
          <TextField
            label="Strength (0.05-1)"
            inputMode="decimal"
            value={strength}
            onChange={(e) => setStrength(e.target.value)}
          />
          <TextField
            label="Edge feather (px)"
            inputMode="numeric"
            value={feather}
            onChange={(e) => setFeather(e.target.value)}
          />
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <TextField
          label={`Steps (default ${caps.default_steps ?? "model"})`}
          inputMode="numeric"
          value={steps}
          onChange={(e) => setSteps(e.target.value)}
        />
        <TextField label="Seed (empty = random)" inputMode="numeric" value={seed} onChange={(e) => setSeed(e.target.value)} />
        <SelectField
          label="Images"
          options={Array.from({ length: maxCount }, (_, i) => ({ value: i + 1, label: String(i + 1) }))}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
        />
      </div>

      {caps.guidance && (
        <TextField label="Guidance scale" inputMode="decimal" value={guidance} onChange={(e) => setGuidance(e.target.value)} />
      )}
      {refSlots > 0 && <ReferencePicker max={refSlots} value={references} onChange={setReferences} />}

      {problems.length > 0 && (
        <p role="alert" className="text-xs text-danger">
          {problems.join(" ")}
        </p>
      )}
      {mode === "inpaint" && src && !painted && <p className="text-xs text-muted">Paint a mask to continue.</p>}
      {(maskError || error) && (
        <p role="alert" className="text-sm text-danger">
          {maskError ?? error}
        </p>
      )}
      <Button type="submit" disabled={!ready || pending || maskBusy}>
        {maskBusy ? "Uploading mask…" : pending ? "Queueing…" : mode === "edit" ? "Apply edit" : `Run ${mode}`}
      </Button>
    </form>
  );
}
