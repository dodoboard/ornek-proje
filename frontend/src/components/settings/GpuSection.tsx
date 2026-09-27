import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { SystemResponse } from "@/lib/api/client";
import { formatMegabytes } from "@/lib/utils/format";

type Runtime = {
  device?: string;
  dtype?: string;
  torch_version?: string | null;
  cuda_version?: string | null;
  gpu_name?: string | null;
  capability?: string | null;
  arch_supported?: boolean | null;
  notes?: string[];
};

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

export function GpuSection({ system }: { system: SystemResponse }) {
  const device = system.gpu.devices?.[0];
  const runtime = (system.worker?.runtime ?? null) as Runtime | null;
  return (
    <Card title="GPU">
      <dl className="space-y-2">
        <Row label="Driver (nvidia-smi)">
          {device ? `${device.name} · ${formatMegabytes(device.memory_total_mb)}` : (system.gpu.detail ?? "—")}
        </Row>
        {runtime ? (
          <>
            <Row label="Worker device">
              <Badge tone={runtime.device === "cuda" ? "success" : "warning"}>
                {runtime.device} · {runtime.dtype}
              </Badge>
            </Row>
            <Row label="PyTorch / CUDA">
              {runtime.torch_version ?? "not installed"}
              {runtime.cuda_version ? ` / ${runtime.cuda_version}` : ""}
            </Row>
            {runtime.capability && (
              <Row label="Compute capability">
                {runtime.capability}{" "}
                <Badge tone={runtime.arch_supported ? "success" : "danger"}>
                  {runtime.arch_supported ? "supported by this build" : "unsupported by this build"}
                </Badge>
              </Row>
            )}
          </>
        ) : (
          <Row label="Worker">Start the worker to see PyTorch/CUDA details.</Row>
        )}
      </dl>
      {runtime?.notes && runtime.notes.length > 0 && (
        <ul className="mt-3 list-disc pl-5 text-xs text-warning">
          {runtime.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}
