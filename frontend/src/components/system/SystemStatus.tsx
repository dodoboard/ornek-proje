"use client";

import type { ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Meter } from "@/components/ui/Meter";
import { useSystem } from "@/hooks/useSystem";
import type { SystemResponse } from "@/lib/api/client";
import { formatGigabytes, formatMegabytes } from "@/lib/utils/format";

import { DiagnosticsCard } from "./DiagnosticsCard";

type ComponentStatus = SystemResponse["gpu"]["status"];

const STATUS_TONE: Record<ComponentStatus, BadgeTone> = {
  ok: "success",
  missing: "warning",
  error: "danger",
  unknown: "neutral",
};

function StatusBadge({ status }: { status: ComponentStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{status}</Badge>;
}

function GpuCard({ gpu }: { gpu: SystemResponse["gpu"] }) {
  const device = gpu.devices?.[0];
  return (
    <Card title="GPU" action={<StatusBadge status={gpu.status} />}>
      {device ? (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium">{device.name}</p>
            <p className="text-xs text-muted">Driver {device.driver_version}</p>
          </div>
          <Meter
            label="VRAM used"
            value={device.memory_used_mb}
            max={device.memory_total_mb}
            caption={`${formatMegabytes(device.memory_used_mb)} / ${formatMegabytes(device.memory_total_mb)}`}
          />
        </div>
      ) : (
        <p className="text-sm text-muted">{gpu.detail ?? "No GPU detected."}</p>
      )}
    </Card>
  );
}

function StorageCard({ storage }: { storage: SystemResponse["storage"] }) {
  return (
    <Card title="Storage">
      <Meter
        label="Disk used"
        value={storage.used_gb}
        max={storage.total_gb}
        caption={`${formatGigabytes(storage.free_gb)} free`}
      />
      <p className="mt-3 truncate text-xs text-muted" title={storage.data_dir}>
        {storage.data_dir}
      </p>
    </Card>
  );
}

function RuntimeCard({ system }: { system: SystemResponse }) {
  const workerOnline = system.worker?.status === "online";
  const rows: [string, ReactNode][] = [
    [
      "Worker",
      <Badge key="worker" tone={workerOnline ? "success" : "warning"}>
        {workerOnline ? "online" : "offline"}
      </Badge>,
    ],
    ["FFmpeg", <StatusBadge key="ffmpeg" status={system.ffmpeg.status} />],
    ["FFprobe", <StatusBadge key="ffprobe" status={system.ffprobe.status} />],
    ["Telemetry", <Badge key="tel" tone="success">{system.privacy.telemetry_enabled ? "on" : "off"}</Badge>],
    ["Offline mode", <Badge key="off">{system.privacy.offline_mode ? "on" : "off"}</Badge>],
    ["Profile", <Badge key="profile">{system.performance_profile}</Badge>],
  ];
  if (system.fake_providers_enabled) {
    rows.push(["Fake providers", <Badge key="fake" tone="warning">dev only</Badge>]);
  }
  return (
    <Card title="Runtime">
      <dl className="space-y-2 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between">
            <dt className="text-muted">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export function SystemStatus() {
  const { data, error, isPending } = useSystem();

  if (isPending) {
    return <Card title="System">Loading system status…</Card>;
  }
  if (error) {
    return (
      <Card title="System" action={<Badge tone="danger">{error.code}</Badge>}>
        <p className="text-sm text-muted">{error.message}</p>
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <GpuCard gpu={data.gpu} />
        <StorageCard storage={data.storage} />
        <RuntimeCard system={data} />
      </div>
      <DiagnosticsCard workerOnline={data.worker?.status === "online"} />
    </div>
  );
}
