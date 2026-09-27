"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { GenerationGallery } from "@/components/image/GenerationGallery";
import { ImageGenerateForm } from "@/components/image/ImageGenerateForm";
import { JobProgress } from "@/components/jobs/JobProgress";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { GENERATIONS_KEY, useGenerations } from "@/hooks/useGenerations";
import { useJob } from "@/hooks/useJob";
import { useModels } from "@/hooks/usePreferences";
import { api, type ApiError, type ImageGenerateRequest, type JobRead } from "@/lib/api/client";
import { findNavItem } from "@/lib/navigation";

export default function ImageStudioPage() {
  const item = findNavItem("/image-studio");
  const queryClient = useQueryClient();
  const models = useModels();
  const generations = useGenerations({ kind: "image", limit: 24 });
  const start = useMutation<JobRead, ApiError, ImageGenerateRequest>({ mutationFn: api.generate.image });
  const cancel = useMutation<JobRead, ApiError, string>({ mutationFn: api.jobs.cancel });
  const { job } = useJob(start.data?.id ?? null);
  const current = job ?? start.data ?? null;

  useEffect(() => {
    if (current?.status === "completed") void queryClient.invalidateQueries({ queryKey: GENERATIONS_KEY });
  }, [current?.status, queryClient]);

  const imageKind = models.data?.kinds.find((k) => k.kind === "image");
  const ready = (imageKind?.providers ?? []).filter((p) => p.status === "available");
  const defaultKey = ready.some((p) => p.key === imageKind?.default_key) ? (imageKind?.default_key ?? null) : null;

  return (
    <>
      <PageHeader
        title={item.label}
        description="Text-to-image with the local FLUX.2 model. Editing and inpainting arrive in Phase 7."
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="space-y-4">
          <Card title="Generate">
            {models.isPending && <p className="text-sm text-muted">Loading models…</p>}
            {models.error && <p className="text-sm text-danger">{models.error.message}</p>}
            {models.data && (
              <ImageGenerateForm
                key={defaultKey ?? "none"}
                models={ready}
                defaultModelKey={defaultKey}
                pending={start.isPending}
                error={start.error?.message}
                onSubmit={(body) => start.mutate(body)}
              />
            )}
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
