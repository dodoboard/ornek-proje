"use client";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Meter } from "@/components/ui/Meter";
import { useNow } from "@/hooks/useNow";
import type { JobRead, JobStatus } from "@/lib/api/client";
import { JOB_STATUS_LABELS, elapsedMs, formatDuration, isTerminal, jobTypeLabel } from "@/lib/jobs";

function statusTone(status: JobStatus): BadgeTone {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "cancelled" || status === "queued") return "neutral";
  return "accent";
}

interface JobProgressProps {
  job: JobRead;
  onCancel?: (job: JobRead) => void;
  cancelling?: boolean;
  compact?: boolean;
}

export function JobProgress({ job, onCancel, cancelling = false, compact = false }: JobProgressProps) {
  const terminal = isTerminal(job.status);
  const now = useNow(!terminal);
  const canCancel = !terminal && !job.cancel_requested && onCancel !== undefined;

  return (
    <div className="space-y-2" data-testid="job-progress">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{jobTypeLabel(job.type)}</p>
          {!compact && <p className="truncate text-xs text-muted">{job.stage ?? "Waiting for worker…"}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-xs tabular-nums text-muted" aria-label="Elapsed time">
            {formatDuration(elapsedMs(job, now))}
          </span>
          <Badge tone={statusTone(job.status)}>
            {job.cancel_requested && !terminal ? "Cancelling…" : JOB_STATUS_LABELS[job.status]}
          </Badge>
          {canCancel && (
            <Button variant="ghost" onClick={() => onCancel(job)} disabled={cancelling}>
              Cancel
            </Button>
          )}
        </div>
      </div>
      <Meter label="Progress" value={job.progress} max={100} caption={`${job.progress}%`} variant="progress" />
      {job.status === "failed" && (
        <p role="alert" className="text-xs text-danger">
          {job.error_code ? `${job.error_code}: ` : ""}
          {job.error_message ?? "The job failed."}
        </p>
      )}
    </div>
  );
}
