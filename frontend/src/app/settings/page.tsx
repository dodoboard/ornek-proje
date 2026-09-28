"use client";

import { GpuSection } from "@/components/settings/GpuSection";
import { PathField } from "@/components/settings/PathField";
import { PerformanceSection } from "@/components/settings/PerformanceSection";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SelectField } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Toggle } from "@/components/ui/Toggle";
import { usePreferences, useUpdatePreferences } from "@/hooks/usePreferences";
import { useSystem } from "@/hooks/useSystem";
import { API_BASE_URL } from "@/lib/api/client";
import { findNavItem } from "@/lib/navigation";
import { ASPECT_RATIOS, LANGUAGES } from "@/lib/projects";
import { formatGigabytes } from "@/lib/utils/format";

export default function SettingsPage() {
  const item = findNavItem("/settings");
  const prefs = usePreferences();
  const system = useSystem();
  const update = useUpdatePreferences();
  const pending = update.isPending;

  if (prefs.isPending || system.isPending) {
    return <p className="text-sm text-muted">Loading…</p>;
  }
  if (prefs.error || system.error) {
    return (
      <p role="alert" className="text-sm text-danger">
        {(prefs.error ?? system.error)?.message}
      </p>
    );
  }
  const p = prefs.data;
  const s = system.data;

  return (
    <>
      <PageHeader title={item.label} description={item.description} />
      {update.error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {update.error.message}
        </p>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="xl:col-span-2">
          <PerformanceSection
            value={p.performance_profile ?? "balanced"}
            disabled={pending}
            onChange={(performance_profile) => update.mutate({ performance_profile })}
          />
        </div>

        <GpuSection system={s} />

        <Card title="Storage">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Data folder</dt>
              <dd className="truncate" title={s.storage.data_dir}>
                {s.storage.data_dir}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Free space</dt>
              <dd>{formatGigabytes(s.storage.free_gb)}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-muted">Change DATA_DIR / MODELS_DIR in .env and restart to move storage.</p>
        </Card>

        <Card title="Generation defaults">
          <div className="grid gap-4 md:grid-cols-2">
            <SelectField
              label="Default format"
              options={ASPECT_RATIOS}
              value={p.default_aspect_ratio ?? "9:16"}
              disabled={pending}
              onChange={(e) =>
                update.mutate({ default_aspect_ratio: e.target.value as NonNullable<typeof p.default_aspect_ratio> })
              }
            />
            <SelectField
              label="Default language"
              options={LANGUAGES}
              value={p.default_language ?? "tr"}
              disabled={pending}
              onChange={(e) => update.mutate({ default_language: e.target.value })}
            />
          </div>
          <div className="mt-4">
            <Toggle
              label="Add an “AI generated” watermark to outputs"
              description="Disclosure metadata is always stored; this adds a visible label."
              checked={p.ai_watermark ?? false}
              disabled={pending}
              onChange={(ai_watermark) => update.mutate({ ai_watermark })}
            />
          </div>
        </Card>

        <Card title="FFmpeg" action={<Badge tone={s.ffmpeg.status === "ok" ? "success" : "warning"}>{s.ffmpeg.status}</Badge>}>
          <div className="space-y-3">
            <PathField
              key={`ffmpeg-${p.ffmpeg_path ?? ""}`}
              label="ffmpeg path (empty = use PATH)"
              current={p.ffmpeg_path}
              placeholder={s.ffmpeg.path ?? "C:/ffmpeg/bin/ffmpeg.exe"}
              disabled={pending}
              onSave={(ffmpeg_path) => update.mutate({ ffmpeg_path })}
            />
            <PathField
              key={`ffprobe-${p.ffprobe_path ?? ""}`}
              label="ffprobe path (empty = use PATH)"
              current={p.ffprobe_path}
              placeholder={s.ffprobe.path ?? "C:/ffmpeg/bin/ffprobe.exe"}
              disabled={pending}
              onSave={(ffprobe_path) => update.mutate({ ffprobe_path })}
            />
            {s.ffmpeg.version && <p className="truncate text-xs text-muted">{s.ffmpeg.version}</p>}
          </div>
        </Card>

        <Card title="Privacy">
          <div className="space-y-4">
            <Toggle
              label="Telemetry & analytics"
              description="Not implemented and never sent. Always off."
              checked={false}
              disabled
              onChange={() => undefined}
            />
            <Toggle
              label="Offline mode"
              description="Blocks model downloads; models must already be on disk. Restart the worker to apply."
              checked={p.offline_mode ?? false}
              disabled={pending}
              onChange={(offline_mode) => update.mutate({ offline_mode })}
            />
          </div>
        </Card>

        <Card title="Advanced">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Environment</dt>
              <dd>{s.app_env}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">API</dt>
              <dd>{API_BASE_URL}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Dev placeholder providers</dt>
              <dd>
                <Badge tone={s.fake_providers_enabled ? "warning" : "neutral"}>
                  {s.fake_providers_enabled ? "enabled" : "disabled"}
                </Badge>
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-muted">
            Model paths are set per model on the Models page. Env defaults live in the repo-root .env file.
          </p>
        </Card>
      </div>
    </>
  );
}
