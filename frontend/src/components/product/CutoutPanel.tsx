"use client";

import clsx from "clsx";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField } from "@/components/ui/Field";
import { api, type ApiError, type ProductCutoutRequest, type ProductRead, type ProviderInfo } from "@/lib/api/client";
import { assetsWithRole } from "@/lib/productStudio";

const ACCEPT = "image/jpeg,image/png,image/webp";
const CHECKERBOARD =
  "bg-[conic-gradient(#8884_25%,transparent_0_50%,#8884_0_75%,transparent_0)] bg-[length:16px_16px]";

export function CutoutPanel({
  product,
  models,
  busy,
  selectedCutoutId,
  onSelectCutout,
  onCutout,
  onChanged,
}: {
  product: ProductRead;
  models: ProviderInfo[];
  busy: boolean;
  selectedCutoutId: string | null;
  onSelectCutout: (assetId: string) => void;
  onCutout: (body: ProductCutoutRequest) => void;
  onChanged: () => void;
}) {
  const photos = assetsWithRole(product.assets, "product_photo");
  const cutouts = assetsWithRole(product.assets, "cutout");
  const input = useRef<HTMLInputElement>(null);
  const [photoId, setPhotoId] = useState<string | null>(null);
  const [modelKey, setModelKey] = useState(models.find((m) => m.is_default)?.key ?? models[0]?.key ?? "");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activePhoto = photoId ?? photos.at(-1)?.id ?? null;

  async function upload(file: File | undefined) {
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const asset = await api.assets.upload(file);
      await api.products.attachAsset(product.id, asset.id, "product_photo");
      setPhotoId(asset.id);
      onChanged();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-1 text-xs font-medium text-muted">Product photos</p>
        <div role="radiogroup" aria-label="Product photo" className="flex flex-wrap gap-2">
          {photos.map((asset) => (
            <button
              key={asset.id}
              type="button"
              role="radio"
              aria-checked={activePhoto === asset.id}
              aria-label={`Photo ${asset.id}`}
              onClick={() => setPhotoId(asset.id)}
              className={clsx(
                "size-20 overflow-hidden rounded-md border",
                activePhoto === asset.id ? "border-accent ring-2 ring-accent" : "border-border",
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
              <img src={api.assets.thumbnailUrl(asset.id)} alt="" className="size-full object-cover" />
            </button>
          ))}
          <Button variant="ghost" className="h-20" disabled={uploading} onClick={() => input.current?.click()}>
            {uploading ? "Uploading…" : "Upload photo"}
          </Button>
        </div>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          hidden
          aria-label="Upload product photo"
          onChange={(e) => void upload(e.target.files?.[0])}
        />
      </div>

      {models.length === 0 ? (
        <p className="text-sm text-muted">
          No segmentation model is ready. Install <code>requirements/segmentation.txt</code> and download a model
          (Models page), or pick the classical colour key for plain backgrounds.
        </p>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-56 flex-1">
            <SelectField
              label="Background removal"
              options={models.map((m) => ({ value: m.key, label: m.note ? `${m.key} — ${m.note}` : m.key }))}
              value={modelKey}
              onChange={(e) => setModelKey(e.target.value)}
            />
          </div>
          <Button
            disabled={busy || !activePhoto || !modelKey}
            onClick={() => activePhoto && onCutout({ source_asset_id: activePhoto, model_key: modelKey })}
          >
            Cut out product
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}

      <div>
        <p className="mb-1 text-xs font-medium text-muted">Cutouts (original pixels, transparent background)</p>
        {cutouts.length === 0 ? (
          <p className="text-sm text-muted">No cutout yet.</p>
        ) : (
          <div role="radiogroup" aria-label="Cutout" className="flex flex-wrap gap-2">
            {cutouts.map((asset) => (
              <button
                key={asset.id}
                type="button"
                role="radio"
                aria-checked={selectedCutoutId === asset.id}
                aria-label={`Cutout ${asset.id}`}
                onClick={() => onSelectCutout(asset.id)}
                className={clsx(
                  "size-24 overflow-hidden rounded-md border p-1",
                  CHECKERBOARD,
                  selectedCutoutId === asset.id ? "border-accent ring-2 ring-accent" : "border-border",
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- local API image (keeps alpha) */}
                <img src={api.assets.contentUrl(asset.id)} alt="" className="size-full object-contain" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
