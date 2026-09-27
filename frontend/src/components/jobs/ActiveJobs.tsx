"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { api, type ApiError, type JobRead, type Page } from "@/lib/api/client";

import { JobProgress } from "./JobProgress";

const ACTIVE_KEY = ["jobs", "active"] as const;

export function ActiveJobs() {
  const queryClient = useQueryClient();
  const { data, error, isPending } = useQuery<Page<JobRead>, ApiError>({
    queryKey: ACTIVE_KEY,
    queryFn: () => api.jobs.list({ active: true, limit: 10 }),
    refetchInterval: 2000,
  });
  const cancel = useMutation<JobRead, ApiError, string>({
    mutationFn: api.jobs.cancel,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ACTIVE_KEY }),
  });

  return (
    <Card title="Active Jobs" action={data && data.total > 0 ? <Badge tone="accent">{data.total}</Badge> : null}>
      {isPending && <p className="text-sm text-muted">Loading…</p>}
      {error && <Badge tone="danger">{error.code}</Badge>}
      {cancel.error && (
        <p role="alert" className="mb-2 text-xs text-danger">
          {cancel.error.message}
        </p>
      )}
      {data && data.items.length === 0 && <EmptyState title="No active jobs">Queued and running jobs appear here.</EmptyState>}
      {data && data.items.length > 0 && (
        <ul className="space-y-4">
          {data.items.map((job) => (
            <li key={job.id}>
              <JobProgress
                job={job}
                compact
                cancelling={cancel.isPending && cancel.variables === job.id}
                onCancel={(j) => cancel.mutate(j.id)}
              />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
