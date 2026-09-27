"use client";

import { useMutation } from "@tanstack/react-query";

import { JobProgress } from "@/components/jobs/JobProgress";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useJob } from "@/hooks/useJob";
import { api, type ApiError, type JobRead } from "@/lib/api/client";

type CheckMap = Record<string, { status?: string } | Record<string, string>>;

function checkTone(status: string | undefined): BadgeTone {
  if (status === "ok" || status === "installed") return "success";
  if (status === "missing" || status === "warn") return "warning";
  if (status === "error") return "danger";
  return "neutral";
}

function Checks({ checks }: { checks: CheckMap }) {
  return (
    <dl className="mt-3 space-y-1.5 text-sm">
      {Object.entries(checks).map(([name, value]) => {
        const status = typeof value.status === "string" ? value.status : undefined;
        const nested = status === undefined ? Object.entries(value as Record<string, string>) : [];
        return (
          <div key={name} className="flex flex-wrap items-center justify-between gap-2">
            <dt className="text-muted">{name.replace(/_/g, " ")}</dt>
            <dd className="flex flex-wrap gap-1">
              {status !== undefined && <Badge tone={checkTone(status)}>{status}</Badge>}
              {nested.map(([pkg, pkgStatus]) => (
                <Badge key={pkg} tone={checkTone(pkgStatus)}>
                  {pkg}: {pkgStatus}
                </Badge>
              ))}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function DiagnosticsCard({ workerOnline }: { workerOnline: boolean }) {
  const start = useMutation<JobRead, ApiError>({ mutationFn: api.runDiagnostics });
  const cancel = useMutation<JobRead, ApiError, string>({ mutationFn: api.jobs.cancel });
  const { job } = useJob(start.data?.id ?? null);
  const current = job ?? start.data ?? null;
  const checks = (current?.status === "completed" ? current.result?.checks : undefined) as CheckMap | undefined;

  return (
    <Card
      title="Worker diagnostics"
      action={
        <Button onClick={() => start.mutate()} disabled={start.isPending}>
          Run diagnostics
        </Button>
      }
    >
      {!workerOnline && (
        <p className="mb-3 text-xs text-warning">
          Worker is offline — the job will wait in the queue until a worker starts.
        </p>
      )}
      {start.error && (
        <p role="alert" className="text-sm text-danger">
          {start.error.message}
        </p>
      )}
      {current ? (
        <>
          <JobProgress job={current} onCancel={(j) => cancel.mutate(j.id)} cancelling={cancel.isPending} />
          {checks && <Checks checks={checks} />}
        </>
      ) : (
        <p className="text-sm text-muted">
          Runs a real end-to-end job on the worker: storage, disk space, an FFmpeg H.264 test encode, GPU driver and
          ML packages.
        </p>
      )}
    </Card>
  );
}
