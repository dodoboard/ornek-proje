"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useState } from "react";

import { GenerationGallery } from "@/components/image/GenerationGallery";
import { ImageEditForm } from "@/components/image/ImageEditForm";
import { ImageGenerateForm } from "@/components/image/ImageGenerateForm";
import { JobProgress } from "@/components/jobs/JobProgress";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { GENERATIONS_KEY, useGenerations } from "@/hooks/useGenerations";
import { useJob } from "@/hooks/useJob";
import { useModels } from "@/hooks/usePreferences";
import { api, type ApiError, type ImageEditRequest, type ImageGenerateRequest, type JobRead } from "@/lib/api/client";
import { availableModes, MODE_LABELS, supportsMode, type EditCapabilities, type StudioMode } from "@/lib/imageEdit";
import { findNavItem } from "@/lib/navigation";

type StartRequest = { mode: "generate"; body: ImageGenerateRequest } | { mode: "edit"; body: ImageEditRequest };

export default function ImageStudioPage() {
  const item = findNavItem("/image-studio");
  const queryClient = useQueryClient();
  const models = useModels();
  const generations = useGenerations({ kind: "image,image_edit", limit: 24 });
  const start = useMutation<JobRead, ApiError, StartRequest>({
    mutationFn: (req) => (req.mode === "generate" ? api.generate.image(req.body) : api.generate.imageEdit(req.body)),
  });
  const cancel = useMutation<JobRead, ApiError, string>({ mutationFn: api.jobs.cancel });
  const { job } = useJob(start.data?.id ?? null);
  const current = job ?? start.data ?? null;
  const [mode, setMode] = useState<StudioMode>("generate");

  useEffect(() => {
    if (current?.status === "completed") void queryClient.invalidateQueries({ queryKey: GENERATIONS_KEY });
  }, [current?.status, queryClient]);

  const imageKind = models.data?.kinds.find((k) => k.kind === "image");
  const ready = (imageKind?.providers ?? []).filter((p) => p.status === "available");
  const modes = availableModes(ready);
  const activeMode = modes.includes(mode) ? mode : "generate";
  const modeModels = ready.filter((p) => supportsMode((p.capabilities ?? {}) as EditCapabilities, activeMode));
  const defaultKey = modeModels.some((p) => p.key === imageKind?.default_key) ? (imageKind?.default_key ?? null) : null;

  return (
    <>
      <PageHeader
        title={item.label}
        description="Generate, edit, inpaint and outpaint with the local FLUX.2 model. Pixels outside the mask are kept exactly."
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="space-y-4">
          <Card title={MODE_LABELS[activeMode]}>
            {models.isPending && <p className="text-sm text-muted">Loading models…</p>}
            {models.error && <p className="text-sm text-danger">{models.error.message}</p>}
            {models.data && modes.length > 1 && (
              <div role="tablist" aria-label="Studio mode" className="mb-4 flex flex-wrap gap-1">
                {modes.map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="tab"
                    aria-selected={activeMode === m}
                    onClick={() => {
                      setMode(m);
                      start.reset();
                    }}
                    className={clsx(
                      "rounded-md border px-3 py-1.5 text-xs",
                      activeMode === m ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-raised",
                    )}
                  >
                    {MODE_LABELS[m]}
                  </button>
                ))}
              </div>
            )}
            {models.data &&
              (activeMode === "generate" ? (
                <ImageGenerateForm
                  key={`generate-${defaultKey ?? "none"}`}
                  models={modeModels}
                  defaultModelKey={defaultKey}
                  pending={start.isPending}
                  error={start.error?.message}
                  onSubmit={(body) => start.mutate({ mode: "generate", body })}
                />
              ) : (
                <ImageEditForm
                  key={`${activeMode}-${defaultKey ?? "none"}`}
                  mode={activeMode}
                  models={modeModels}
                  defaultModelKey={defaultKey}
                  recent={generations.data?.items ?? []}
                  pending={start.isPending}
                  error={start.error?.message}
                  onSubmit={(body) => start.mutate({ mode: "edit", body })}
                />
              ))}
          </Card>
          {current && (
            <Card title="Current job">
              <JobProgress job={current} onCancel={(j) => cancel.mutate(j.id)} cancelling={cancel.isPending} />
            </Card>
          )}
        </div>
        <Card title="Recent images">
          {generations.isPending && <p className="text-sm text-muted">Loading…</p>}
          {generations.error && <p className="text-sm text-danger">{generations.error.message}</p>}
          {generations.data && <GenerationGallery generations={generations.data.items} />}
        </Card>
      </div>
    </>
  );
}
