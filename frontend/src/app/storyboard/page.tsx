"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { JobProgress } from "@/components/jobs/JobProgress";
import { ScriptGenerateForm } from "@/components/storyboard/ScriptGenerateForm";
import { StoryboardEditor } from "@/components/storyboard/StoryboardEditor";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SelectField } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { useJob } from "@/hooks/useJob";
import { useModels } from "@/hooks/usePreferences";
import { useProjects } from "@/hooks/useProjects";
import { storyboardKeys, useLatestStoryboard, useScripts } from "@/hooks/useStoryboard";
import { api, type ApiError, type JobRead, type ScriptGenerateRequest, type ShotUpdate } from "@/lib/api/client";
import { findNavItem } from "@/lib/navigation";
import { durationSummary, scriptOrigin } from "@/lib/storyboard";

export default function StoryboardPage() {
  const item = findNavItem("/storyboard");
  const queryClient = useQueryClient();
  const projects = useProjects(100);
  const models = useModels();
  const [picked, setPicked] = useState<string | null>(null);
  const projectId = picked ?? projects.data?.items[0]?.id ?? null;
  const project = projects.data?.items.find((p) => p.id === projectId) ?? null;
  const storyboard = useLatestStoryboard(projectId);
  const scripts = useScripts(projectId);

  const refresh = () => {
    if (!projectId) return;
    void queryClient.invalidateQueries({ queryKey: storyboardKeys.latest(projectId) });
    void queryClient.invalidateQueries({ queryKey: storyboardKeys.scripts(projectId) });
  };
  const generate = useMutation<JobRead, ApiError, ScriptGenerateRequest>({
    mutationFn: (body) => api.storyboards.generateScript(projectId!, body),
  });
  const cancel = useMutation<JobRead, ApiError, string>({ mutationFn: api.jobs.cancel });
  const edit = useMutation<unknown, ApiError, () => Promise<unknown>>({ mutationFn: (fn) => fn(), onSettled: refresh });
  const { job } = useJob(generate.data?.id ?? null);
  const current = job ?? generate.data ?? null;
  useEffect(() => {
    if (current?.status === "completed") refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when a job finishes
  }, [current?.status]);

  const llmKind = models.data?.kinds.find((k) => k.kind === "llm");
  const llms = (llmKind?.providers ?? []).filter((p) => p.status === "available");
  const defaultLlm = llms.some((m) => m.key === llmKind?.default_key) ? (llmKind?.default_key ?? null) : null;
  const busy = generate.isPending || (current !== null && !["completed", "failed", "cancelled"].includes(current.status));
  const board = storyboard.data ?? null;
  const script = scripts.data?.find((s) => s.id === board?.script_id) ?? null;
  const origin = script ? scriptOrigin(script) : null;
  const target = project?.settings.duration_s;
  const summary = board ? durationSummary(board.shots, target) : null;

  return (
    <>
      <PageHeader title={item.label} description={item.description} />
      {projects.data && projects.data.items.length === 0 ? (
        <EmptyState title="No projects yet">Create a project on the Projects page first.</EmptyState>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="space-y-4">
            <Card title="Project">
              {projects.data && (
                <SelectField
                  label="Project"
                  options={projects.data.items.map((p) => ({ value: p.id, label: `${p.name} · ${p.type.replace("_", " ")}` }))}
                  value={projectId ?? ""}
                  onChange={(e) => {
                    setPicked(e.target.value);
                    generate.reset();
                  }}
                />
              )}
              {project && (
                <p className="mt-2 text-xs text-muted">
                  {project.settings.duration_s}s · {project.settings.aspect_ratio} · {project.settings.platform} ·{" "}
                  {project.settings.tone} · {project.settings.language}
                </p>
              )}
            </Card>
            <Card title="Script">
              {models.data && (
                <ScriptGenerateForm
                  key={defaultLlm ?? "none"}
                  models={llms}
                  defaultModelKey={defaultLlm}
                  busy={busy || !projectId}
                  onGenerate={(body) => generate.mutate(body)}
                />
              )}
              {generate.error && (
                <p role="alert" className="mt-2 text-sm text-danger">
                  {generate.error.message}
                </p>
              )}
              <p className="mt-3 text-xs text-muted">
                Facts (prices, sizes, features, locations) are inserted from your verified data. Scripts that type
                their own numbers or claims are rejected, repaired once, then replaced by the template.
              </p>
            </Card>
            {current && (
              <Card title="Current job">
                <JobProgress job={current} onCancel={(j) => cancel.mutate(j.id)} cancelling={cancel.isPending} />
              </Card>
            )}
          </div>

          <Card
            title={board ? `Storyboard v${board.version}` : "Storyboard"}
            action={
              board && summary ? (
                <Badge tone={summary.ok ? "success" : "warning"}>
                  {summary.total}s{target ? ` / ${target}s` : ""}
                </Badge>
              ) : null
            }
          >
            {storyboard.isPending && projectId && <p className="text-sm text-muted">Loading…</p>}
            {storyboard.error && <p className="text-sm text-danger">{storyboard.error.message}</p>}
            {board === null && !storyboard.isPending && (
              <EmptyState title="No storyboard yet">Generate a script to create the first storyboard.</EmptyState>
            )}
            {board && (
              <div className="space-y-3">
                {script && origin && (
                  <div className="rounded-md border border-border p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{script.title}</span>
                      <Badge tone={origin.tone}>{origin.label}</Badge>
                    </div>
                    {script.hook && <p className="text-muted">Hook: {script.hook}</p>}
                    {origin.reasons.length > 0 && (
                      <details className="mt-1 text-xs text-muted">
                        <summary>Why the LLM output was rejected ({origin.reasons.length})</summary>
                        <ul className="list-disc pl-4">
                          {origin.reasons.map((r) => (
                            <li key={r}>{r}</li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>
                )}
                {edit.error && (
                  <p role="alert" className="text-sm text-danger">
                    {edit.error.message}
                  </p>
                )}
                <StoryboardEditor
                  shots={board.shots}
                  pending={edit.isPending}
                  onReorder={(ids) => edit.mutate(() => api.storyboards.reorder(board.id, ids))}
                  onSave={(id, patch: ShotUpdate) => edit.mutate(() => api.storyboards.updateShot(id, patch))}
                  onDelete={(id) => edit.mutate(() => api.storyboards.deleteShot(id))}
                />
                <Button
                  variant="ghost"
                  disabled={edit.isPending}
                  onClick={() => edit.mutate(() => api.storyboards.addShot(board.id, { type: "broll", duration_s: 3 }))}
                >
                  <Plus className="size-4" aria-hidden /> Add shot
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
