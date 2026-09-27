"use client";

import clsx from "clsx";

import { Card } from "@/components/ui/Card";
import type { PerformanceProfile } from "@/lib/api/client";
import { PERFORMANCE_PROFILES } from "@/lib/settings";

export function PerformanceSection({
  value,
  onChange,
  disabled,
}: {
  value: PerformanceProfile;
  onChange: (profile: PerformanceProfile) => void;
  disabled: boolean;
}) {
  return (
    <Card title="Performance">
      <div role="radiogroup" aria-label="Performance profile" className="grid gap-2 md:grid-cols-3">
        {PERFORMANCE_PROFILES.map((profile) => {
          const selected = profile.value === value;
          return (
            <button
              key={profile.value}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(profile.value)}
              className={clsx(
                "rounded-md border p-3 text-left transition-colors disabled:opacity-60",
                selected ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-raised",
              )}
            >
              <span className="block text-sm font-medium">{profile.label}</span>
              <span className="mt-1 block text-xs text-muted">{profile.description}</span>
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-muted">Applied to the next job; the worker reloads models when it changes.</p>
    </Card>
  );
}
