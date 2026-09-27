"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { JobProgress } from "@/components/jobs/JobProgress";
import { CutoutPanel } from "@/components/product/CutoutPanel";
import { SceneForm } from "@/components/product/SceneForm";
import { SceneGallery } from "@/components/product/SceneGallery";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useJob } from "@/hooks/useJob";
import { useModels } from "@/hooks/usePreferences";
import { productKeys, useProduct, useProductScenes } from "@/hooks/useProducts";
import {
  api,
  type ApiError,
  type AssetRead,
  type JobRead,
  type ProductCutoutRequest,
  type ProductSceneRequest,
} from "@/lib/api/client";
import { assetsWithRole } from "@/lib/productStudio";

type Start = { kind: "cutout"; body: ProductCutoutRequest } | { kind: "scene"; body: ProductSceneRequest };

export default function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const product = useProduct(id);
  const scenes = useProductScenes(id);
  const models = useModels();
  const [cutoutId, setCutoutId] = useState<string | null>(null);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: productKeys.detail(id) });
    void queryClient.invalidateQueries({ queryKey: productKeys.scenes(id) });
  };
  const start = useMutation<JobRead, ApiError, Start>({
    mutationFn: (s) => (s.kind === "cutout" ? api.products.cutout(id, s.body) : api.products.scene(id, s.body)),
    onSuccess: (_, s) => {
      if (s.kind === "cutout") setCutoutId(null); // the newest cutout becomes the selection
    },
  });
  const cancel = useMutation<JobRead, ApiError, string>({ mutationFn: api.jobs.cancel });
  const { job } = useJob(start.data?.id ?? null);
  const current = job ?? start.data ?? null;
  useEffect(() => {
    if (current?.status !== "completed") return;
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when a job finishes
  }, [current?.status]);

  if (product.isPending) return <p className="text-sm text-muted">Loading…</p>;
  if (product.error) {
    return (
      <p role="alert" className="text-sm text-danger">
        {product.error.message}
      </p>
    );
  }

  const p = product.data;
  const kinds = models.data?.kinds ?? [];
  const ready = (kind: string) => (kinds.find((k) => k.kind === kind)?.providers ?? []).filter((m) => m.status === "available");
  const imageKind = kinds.find((k) => k.kind === "image");
  const imageModels = ready("image");
  const defaultImage = imageModels.some((m) => m.key === imageKind?.default_key) ? (imageKind?.default_key ?? null) : null;
  const cutouts = assetsWithRole(p.assets, "cutout");
  const cutout = cutouts.find((a) => a.id === cutoutId) ?? cutouts.at(-1) ?? null;
  const sized = cutout?.width && cutout.height ? (cutout as AssetRead & { width: number; height: number }) : null;
  const busy = start.isPending || (current !== null && !["completed", "failed", "cancelled"].includes(current.status));

  return (
    <>
      <PageHeader
        title={p.name}
        description={p.description || "Product facts you enter are used as-is; nothing about the product is generated."}
        action={p.brand ? <Badge>{p.brand}</Badge> : null}
      />
      {start.error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {start.error.message}
        </p>
      )}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-4">
          {current && (
            <Card title="Current job">
              <JobProgress job={current} onCancel={(j) => cancel.mutate(j.id)} cancelling={cancel.isPending} />
            </Card>
          )}
          <Card title="1 · Photo → cutout">
            {models.data && (
              <CutoutPanel
                product={p}
                models={ready("segmentation")}
                busy={busy}
                selectedCutoutId={cutout?.id ?? null}
                onSelectCutout={setCutoutId}
                onCutout={(body) => start.mutate({ kind: "cutout", body })}
                onChanged={refresh}
              />
            )}
          </Card>
          <Card title="2 · Scene">
            {!sized && <p className="text-sm text-muted">Create a cutout first.</p>}
            {sized && models.data && (
              <SceneForm
                key={`${sized.id}-${defaultImage ?? "none"}`}
                cutout={sized}
                models={imageModels}
                defaultModelKey={defaultImage}
                pending={start.isPending}
                error={null}
                onSubmit={(body) => start.mutate({ kind: "scene", body })}
              />
            )}
          </Card>
        </div>
        <Card title="Scenes">
          {scenes.isPending && <p className="text-sm text-muted">Loading…</p>}
          {scenes.error && <p className="text-sm text-danger">{scenes.error.message}</p>}
          {scenes.data && <SceneGallery generations={scenes.data.items} />}
          <p className="mt-3 text-xs text-muted">
            Every scene is checked after rendering: the product&apos;s protected pixels must equal the cutout exactly,
            otherwise the job fails. Only a thin edge band may be repainted when AI blending is on.
          </p>
        </Card>
      </div>
    </>
  );
}
