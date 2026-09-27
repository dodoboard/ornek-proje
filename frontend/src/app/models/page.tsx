"use client";

import { ModelKindCard } from "@/components/models/ModelKindCard";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useModels, usePreferences, useUpdatePreferences } from "@/hooks/usePreferences";
import { findNavItem } from "@/lib/navigation";

export default function ModelsPage() {
  const item = findNavItem("/models");
  const models = useModels();
  const prefs = usePreferences();
  const update = useUpdatePreferences();

  return (
    <>
      <PageHeader
        title={item.label}
        description="Configured models, whether they are installed and downloaded, and which one each studio uses."
        action={models.data?.fake_providers_enabled ? <Badge tone="warning">dev placeholders enabled</Badge> : null}
      />
      {(models.error || prefs.error) && (
        <Card>
          <p role="alert" className="text-sm text-danger">
            {(models.error ?? prefs.error)?.message}
          </p>
        </Card>
      )}
      {update.error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {update.error.message}
        </p>
      )}
      {(models.isPending || prefs.isPending) && <p className="text-sm text-muted">Loading…</p>}
      {models.data && prefs.data && (
        <div className="grid gap-4 xl:grid-cols-2">
          {models.data.kinds.map((group) => (
            <ModelKindCard
              key={group.kind}
              group={group}
              localPaths={prefs.data.model_paths ?? {}}
              pending={update.isPending}
              onUpdate={(patch) => update.mutate(patch)}
            />
          ))}
        </div>
      )}
    </>
  );
}
