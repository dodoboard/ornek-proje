"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { BiblePanel } from "@/components/character/BiblePanel";
import { ImagePickGrid } from "@/components/character/ImagePickGrid";
import { ReferencesPanel } from "@/components/character/ReferencesPanel";
import { JobProgress } from "@/components/jobs/JobProgress";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SelectField, TextField } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { characterKeys, useCharacter, useCharacterBible, useCharacterGenerations } from "@/hooks/useCharacters";
import { useJob } from "@/hooks/useJob";
import {
  api,
  type ApiError,
  type CharacterBibleUpdate,
  type CharacterGenerateRequest,
  type CharacterPurpose,
  type JobRead,
  type ViewRole,
} from "@/lib/api/client";
import { VIEW_LABELS, VIEW_PURPOSES, imagesForPurpose } from "@/lib/characters";

const COUNTS = [1, 2, 3, 4].map((n) => ({ value: n, label: String(n) }));

export default function CharacterPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const character = useCharacter(id);
  const bible = useCharacterBible(id);
  const generations = useCharacterGenerations(id);

  const [active, setActive] = useState<{ job: JobRead; purpose: CharacterPurpose } | null>(null);
  const [candidateCount, setCandidateCount] = useState(4);
  const [scene, setScene] = useState("");
  const [sceneCount, setSceneCount] = useState(2);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: characterKeys.detail(id) });
    void queryClient.invalidateQueries({ queryKey: characterKeys.bible(id) });
    void queryClient.invalidateQueries({ queryKey: characterKeys.generations(id) });
  };

  const generate = useMutation<JobRead, ApiError, CharacterGenerateRequest>({
    mutationFn: (body) => api.characters.generate(id, body),
    onSuccess: (job, body) => setActive({ job, purpose: body.purpose }),
  });
  const cancel = useMutation<JobRead, ApiError, string>({ mutationFn: api.jobs.cancel });
  const setView = useMutation<unknown, ApiError, { role: ViewRole; assetId: string }>({
    mutationFn: ({ role, assetId }) => api.characters.setView(id, role, assetId),
    onSuccess: refresh,
  });
  const saveBible = useMutation<unknown, ApiError, CharacterBibleUpdate>({
    mutationFn: (patch) => api.characters.updateBible(id, patch),
    onSuccess: refresh,
  });

  const { job } = useJob(active?.job.id ?? null);
  const current = job ?? active?.job ?? null;
  useEffect(() => {
    if (current?.status === "completed") refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when a job finishes
  }, [current?.status]);

  if (character.isPending || bible.isPending) return <p className="text-sm text-muted">Loading…</p>;
  if (character.error || bible.error) {
    return (
      <p role="alert" className="text-sm text-danger">
        {(character.error ?? bible.error)?.message}
      </p>
    );
  }

  const c = character.data;
  const b = bible.data;
  const all = generations.data?.items ?? [];
  const views = b.views as Record<ViewRole, string | null>;
  const hasCanonical = Boolean(views.canonical);
  const busy = generate.isPending || (current !== null && !["completed", "failed", "cancelled"].includes(current.status));
  const error = generate.error?.message ?? setView.error?.message;

  return (
    <>
      <PageHeader
        title={c.name}
        description={`${c.adult_age} · ${c.presentation || "adult"} · ${c.default_language}`}
        action={c.is_real_person ? <Badge tone="warning">real person · consent on file</Badge> : null}
      />
      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-4">
          {current && (
            <Card title={`Running: ${active?.purpose.replace("_", " ")}`}>
              <JobProgress job={current} onCancel={(j) => cancel.mutate(j.id)} cancelling={cancel.isPending} />
            </Card>
          )}

          <Card
            title="1 · Canonical portrait"
            action={
              <div className="flex items-end gap-2">
                <div className="w-20">
                  <SelectField
                    label="Images"
                    options={COUNTS}
                    value={candidateCount}
                    onChange={(e) => setCandidateCount(Number(e.target.value))}
                  />
                </div>
                <Button
                  disabled={busy}
                  onClick={() => generate.mutate({ purpose: "candidates", num_images: candidateCount })}
                >
                  Generate candidates
                </Button>
              </div>
            }
          >
            <ReferencesPanel
              characterId={id}
              assetIds={b.reference_asset_ids}
              onChanged={refresh}
            />
            <div className="mt-4">
              <ImagePickGrid
                images={imagesForPurpose(all, "candidates")}
                selectedId={views.canonical}
                actionLabel="Use as canonical"
                pending={setView.isPending}
                onPick={(assetId) => setView.mutate({ role: "canonical", assetId })}
                emptyText="Generate portrait candidates, then pick the one that defines this influencer."
              />
            </div>
          </Card>

          <Card title="2 · Views">
            {!hasCanonical && <p className="mb-3 text-sm text-muted">Pick a canonical portrait first.</p>}
            <div className="space-y-5">
              {VIEW_PURPOSES.map((role) => (
                <section key={role}>
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="text-sm font-medium">{VIEW_LABELS[role]}</h3>
                    <Button
                      variant="ghost"
                      aria-label={`Generate ${VIEW_LABELS[role]}`}
                      disabled={busy || !hasCanonical}
                      onClick={() => generate.mutate({ purpose: role, num_images: 2 })}
                    >
                      Generate
                    </Button>
                  </div>
                  <ImagePickGrid
                    images={imagesForPurpose(all, role)}
                    selectedId={views[role]}
                    actionLabel="Use"
                    pending={setView.isPending}
                    onPick={(assetId) => setView.mutate({ role, assetId })}
                    emptyText="Generated from the canonical portrait as reference."
                  />
                </section>
              ))}
            </div>
          </Card>

          <Card title="3 · Same influencer, new scene">
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (scene.trim()) generate.mutate({ purpose: "scene", scene: scene.trim(), num_images: sceneCount });
              }}
            >
              <TextField
                label="Scene"
                placeholder="sitting at a seaside café in Bodrum, morning light"
                value={scene}
                onChange={(e) => setScene(e.target.value)}
                maxLength={1000}
              />
              <div className="flex items-end gap-2">
                <div className="w-20">
                  <SelectField
                    label="Images"
                    options={COUNTS}
                    value={sceneCount}
                    onChange={(e) => setSceneCount(Number(e.target.value))}
                  />
                </div>
                <Button type="submit" disabled={busy || !hasCanonical || !scene.trim()}>
                  Generate scene
                </Button>
              </div>
            </form>
            <div className="mt-4">
              <ImagePickGrid
                images={imagesForPurpose(all, "scene")}
                selectedId={null}
                actionLabel="Use as canonical"
                pending={setView.isPending}
                onPick={(assetId) => setView.mutate({ role: "canonical", assetId })}
                emptyText="Scenes use the canonical portrait and all chosen views as references."
              />
            </div>
          </Card>
        </div>

        <BiblePanel
          key={[b.immutable_traits.join("|"), b.mutable_traits.join("|"), b.prompt_template].join("::")}
          bible={b}
          pending={saveBible.isPending}
          error={saveBible.error?.message}
          onSave={(patch) => saveBible.mutate(patch)}
        />
      </div>
    </>
  );
}
