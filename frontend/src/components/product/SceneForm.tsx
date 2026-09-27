"use client";

import clsx from "clsx";
import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { Toggle } from "@/components/ui/Toggle";
import { api, type ApiError, type AssetRead, type ProductSceneRequest, type ProviderInfo } from "@/lib/api/client";
import { ASPECT_PRESETS, parseSeed, presetById, type AspectId } from "@/lib/imageSizes";
import { DEFAULT_PLACEMENT, placementBox, type Placement } from "@/lib/productStudio";

interface Capabilities {
  inpainting?: boolean;
  default_steps?: number;
  max_images_per_request?: number;
}

type SizedAsset = AssetRead & { width: number; height: number };
type BackgroundMode = "generate" | "photo";

function Slider({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block text-xs text-muted">
      <span className="flex justify-between">
        {label}
        <span className="tabular-nums">{format(value)}</span>
      </span>
      <input
        type="range"
        className="w-full"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

export function SceneForm({
  cutout,
  models,
  defaultModelKey,
  onSubmit,
  pending,
  error,
}: {
  cutout: SizedAsset;
  models: ProviderInfo[];
  defaultModelKey: string | null;
  onSubmit: (body: ProductSceneRequest) => void;
  pending: boolean;
  error?: string | null;
}) {
  const [modelKey, setModelKey] = useState(defaultModelKey ?? models[0]?.key ?? "");
  const model = models.find((m) => m.key === modelKey) ?? models[0];
  const caps = (model?.capabilities ?? {}) as Capabilities;

  const [scene, setScene] = useState("");
  const [aspect, setAspect] = useState<AspectId>("4:5");
  const [mode, setMode] = useState<BackgroundMode>(models.length ? "generate" : "photo");
  const [background, setBackground] = useState<AssetRead | null>(null);
  const [placement, setPlacement] = useState<Placement>(DEFAULT_PLACEMENT);
  const [shadow, setShadow] = useState(true);
  const [shadowOpacity, setShadowOpacity] = useState(0.45);
  const [harmonize, setHarmonize] = useState(false);
  const [ringPx, setRingPx] = useState(6);
  const [strength, setStrength] = useState(0.35);
  const [count, setCount] = useState(1);
  const [seed, setSeed] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const size = presetById(aspect);
  const canvas = { width: size.width, height: size.height };
  const placed = placementBox(cutout, canvas, placement);
  const canHarmonize = Boolean(model && caps.inpainting);
  const useHarmonize = harmonize && canHarmonize;
  const needsModel = mode === "generate" || useHarmonize;
  const maxCount = mode === "photo" && !useHarmonize ? 1 : (caps.max_images_per_request ?? 4);
  const seedValue = seed.trim() ? parseSeed(seed) : null;

  const problems = [
    "error" in placed ? placed.error : null,
    needsModel && !model ? "No image model is ready; use your own background photo." : null,
    mode === "photo" && !background ? "Upload a background photo." : null,
    seed.trim() && seedValue === null ? "Seed must be a whole number." : null,
  ].filter((p): p is string => p !== null);
  const ready = scene.trim() !== "" && problems.length === 0;

  function set<K extends keyof Placement>(key: K, value: Placement[K]) {
    setPlacement((p) => ({ ...p, [key]: value }));
  }

  async function uploadBackground(file: File | undefined) {
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    try {
      setBackground(await api.assets.upload(file));
    } catch (e) {
      setUploadError((e as ApiError).message);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    onSubmit({
      cutout_asset_id: cutout.id,
      scene: scene.trim(),
      width: size.width,
      height: size.height,
      placement,
      shadow,
      shadow_opacity: shadowOpacity,
      harmonize: { enabled: useHarmonize, ring_px: ringPx, strength },
      background_asset_id: mode === "photo" ? (background?.id ?? null) : null,
      model_key: needsModel ? (model?.key ?? null) : null,
      num_images: Math.min(count, maxCount),
      seed: seedValue,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4" aria-label="Product scene">
      <TextField
        label="Scene"
        placeholder="marble bathroom counter, morning window light, eucalyptus leaves"
        value={scene}
        onChange={(e) => setScene(e.target.value)}
        maxLength={1000}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-muted">Background</p>
          <div role="radiogroup" aria-label="Background" className="flex gap-2">
            {(
              [
                ["generate", "Generate with AI"],
                ["photo", "My photo"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mode === value}
                disabled={value === "generate" && models.length === 0}
                onClick={() => setMode(value)}
                className={clsx(
                  "rounded-md border px-3 py-1.5 text-xs disabled:opacity-50",
                  mode === value ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-raised",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {mode === "photo" && (
            <div className="mt-2 flex items-center gap-2">
              <Button variant="ghost" disabled={uploading} onClick={() => input.current?.click()}>
                {uploading ? "Uploading…" : background ? "Replace photo" : "Upload background"}
              </Button>
              {background && <span className="truncate text-xs text-muted">{background.original_filename ?? background.id}</span>}
              <input
                ref={input}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                hidden
                aria-label="Upload background photo"
                onChange={(e) => void uploadBackground(e.target.files?.[0])}
              />
            </div>
          )}
          {uploadError && <p className="mt-1 text-xs text-danger">{uploadError}</p>}
        </div>
        {models.length > 0 && (
          <SelectField
            label="Image model"
            options={models.map((m) => ({ value: m.key, label: m.maturity === "dev_only" ? `${m.key} (dev placeholder)` : m.key }))}
            value={model?.key ?? ""}
            onChange={(e) => setModelKey(e.target.value)}
          />
        )}
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
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-3">
          <Slider label="Horizontal position" value={placement.x} min={0} max={1} step={0.01} format={pct} onChange={(v) => set("x", v)} />
          <Slider label="Standing line" value={placement.y} min={0.1} max={1} step={0.01} format={pct} onChange={(v) => set("y", v)} />
          <Slider
            label="Product height"
            value={placement.height_ratio}
            min={0.05}
            max={1}
            step={0.01}
            format={pct}
            onChange={(v) => set("height_ratio", v)}
          />
          <Toggle
            label="Original size (1:1 pixels)"
            description="No resampling at all; the height slider is ignored."
            checked={placement.native_scale}
            onChange={(v) => set("native_scale", v)}
          />
          <Toggle label="Contact shadow" checked={shadow} onChange={setShadow} />
          {shadow && (
            <Slider label="Shadow strength" value={shadowOpacity} min={0} max={0.9} step={0.05} format={pct} onChange={setShadowOpacity} />
          )}
          <Toggle
            label="Blend edges with AI"
            description={
              canHarmonize
                ? "Repaints only a thin ring around the silhouette; the product interior stays untouched."
                : "Needs an image model with inpainting."
            }
            checked={useHarmonize}
            disabled={!canHarmonize}
            onChange={setHarmonize}
          />
          {useHarmonize && (
            <div className="grid grid-cols-2 gap-3">
              <Slider label="Edge band" value={ringPx} min={2} max={16} step={1} format={(v) => `${v}px`} onChange={setRingPx} />
              <Slider label="Blend strength" value={strength} min={0.1} max={0.8} step={0.05} format={(v) => v.toFixed(2)} onChange={setStrength} />
            </div>
          )}
        </div>

        <div>
          <div
            data-testid="scene-preview"
            className="relative mx-auto w-full max-w-xs overflow-hidden rounded-md border border-dashed border-accent bg-surface-raised"
            style={{ aspectRatio: `${canvas.width} / ${canvas.height}` }}
          >
            {"box" in placed && (
              // eslint-disable-next-line @next/next/no-img-element -- local API image (keeps alpha)
              <img
                src={api.assets.contentUrl(cutout.id)}
                alt="Product placement"
                className="absolute"
                style={{
                  left: `${(placed.box.left / canvas.width) * 100}%`,
                  top: `${(placed.box.top / canvas.height) * 100}%`,
                  width: `${(placed.box.width / canvas.width) * 100}%`,
                  height: `${(placed.box.height / canvas.height) * 100}%`,
                }}
              />
            )}
          </div>
          <p className="mt-1 text-center text-xs text-muted">
            {`${canvas.width}×${canvas.height}px` +
              ("box" in placed
                ? ` · product ${placed.box.width}×${placed.box.height}px${placed.scale > 1 ? " (upscaled — may look soft)" : ""}`
                : "")}
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <SelectField
          label="Images"
          options={Array.from({ length: maxCount }, (_, i) => ({ value: i + 1, label: String(i + 1) }))}
          value={Math.min(count, maxCount)}
          onChange={(e) => setCount(Number(e.target.value))}
        />
        <TextField label="Seed (empty = random)" inputMode="numeric" value={seed} onChange={(e) => setSeed(e.target.value)} />
      </div>

      {problems.length > 0 && (
        <p role="alert" className="text-xs text-danger">
          {problems.join(" ")}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" disabled={!ready || pending}>
        {pending ? "Queueing…" : "Create scene"}
      </Button>
    </form>
  );
}
