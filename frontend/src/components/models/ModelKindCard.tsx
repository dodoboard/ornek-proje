"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { KindModels, PreferencesUpdate, ProviderInfo } from "@/lib/api/client";
import { KIND_LABELS, STATUS_LABELS, capabilityFlags, isSelectable, showVerification, statusTone } from "@/lib/models";

interface ModelKindCardProps {
  group: KindModels;
  localPaths: Record<string, string>;
  onUpdate: (patch: PreferencesUpdate) => void;
  pending: boolean;
}

function PathEditor({
  provider,
  current,
  onSave,
  pending,
}: {
  provider: ProviderInfo;
  current: string | undefined;
  onSave: (value: string | null) => void;
  pending: boolean;
}) {
  const [value, setValue] = useState(current ?? "");
  const dirty = value.trim() !== (current ?? "");
  return (
    <div className="mt-2 flex gap-2">
      <input
        aria-label={`Local path for ${provider.key}`}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Local model folder (optional, overrides the repo ID)"
        className="min-w-0 flex-1 rounded-md border border-border bg-surface-raised px-2 py-1 text-xs outline-none focus:border-accent"
      />
      <Button variant="ghost" disabled={!dirty || pending} onClick={() => onSave(value.trim() || null)}>
        Save path
      </Button>
    </div>
  );
}

export function ModelKindCard({ group, localPaths, onUpdate, pending }: ModelKindCardProps) {
  return (
    <Card title={KIND_LABELS[group.kind]}>
      <ul className="divide-y divide-border">
        {group.providers.map((provider) => {
          const flags = capabilityFlags(provider.capabilities);
          return (
            <li key={provider.key} className="py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <label className="flex min-w-0 items-start gap-3">
                  <input
                    type="radio"
                    name={`default-${group.kind}`}
                    className="mt-1 accent-[var(--color-accent)]"
                    checked={provider.is_default}
                    disabled={!isSelectable(provider) || pending}
                    onChange={() => onUpdate({ default_models: { [group.kind]: provider.key } })}
                    aria-label={`Use ${provider.key} as default`}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{provider.key}</span>
                    <span className="block truncate text-xs text-muted" title={provider.source ?? undefined}>
                      {provider.source ?? provider.provider}
                    </span>
                  </span>
                </label>
                <div className="flex flex-wrap gap-1">
                  <Badge tone={statusTone(provider.status)}>{STATUS_LABELS[provider.status]}</Badge>
                  {provider.maturity !== "stable" && (
                    <Badge tone={provider.maturity === "dev_only" ? "warning" : "accent"}>
                      {provider.maturity === "dev_only" ? "dev only" : "experimental"}
                    </Badge>
                  )}
                  {showVerification(provider.verification) && <Badge>{provider.verification}</Badge>}
                </div>
              </div>
              {provider.detail && <p className="mt-1 text-xs text-muted">{provider.detail}</p>}
              <p className="mt-1 text-xs text-muted">
                License (unverified claim): {provider.license_claim ?? "unknown — check the model card"}
              </p>
              {flags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {flags.map((flag) => (
                    <Badge key={flag}>{flag}</Badge>
                  ))}
                </div>
              )}
              {provider.maturity !== "dev_only" && (
                <PathEditor
                  key={localPaths[provider.key] ?? ""}
                  provider={provider}
                  current={localPaths[provider.key]}
                  pending={pending}
                  onSave={(path) => onUpdate({ model_paths: { [provider.key]: path } })}
                />
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
