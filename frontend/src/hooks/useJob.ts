"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, type ApiError, type JobRead } from "@/lib/api/client";
import { isTerminal } from "@/lib/jobs";

const POLL_INTERVAL_MS = 1000;

export type JobTransport = "sse" | "polling";

/**
 * Live job state. Prefers Server-Sent Events; falls back to polling if the stream
 * is unavailable. The stream is closed as soon as a terminal state arrives.
 */
export function useJob(jobId: string | null) {
  const sseSupported = typeof window !== "undefined" && "EventSource" in window;
  const [streamed, setStreamed] = useState<{ id: string; job: JobRead } | null>(null);
  const [failedStreamId, setFailedStreamId] = useState<string | null>(null);

  const transport: JobTransport = sseSupported && failedStreamId !== jobId ? "sse" : "polling";

  useEffect(() => {
    if (!jobId || transport !== "sse") return;
    const source = new EventSource(api.jobs.eventsUrl(jobId));
    source.addEventListener("job", (event) => {
      const job = JSON.parse((event as MessageEvent<string>).data) as JobRead;
      setStreamed({ id: jobId, job });
      if (isTerminal(job.status)) source.close();
    });
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) setFailedStreamId(jobId);
    };
    return () => source.close();
  }, [jobId, transport]);

  const polled = useQuery<JobRead, ApiError>({
    queryKey: ["job", jobId],
    queryFn: () => api.jobs.get(jobId as string),
    enabled: jobId !== null && transport === "polling",
    refetchInterval: (query) =>
      query.state.data && isTerminal(query.state.data.status) ? false : POLL_INTERVAL_MS,
  });

  const job = transport === "sse" ? (streamed?.id === jobId ? streamed.job : null) : (polled.data ?? null);
  return { job, transport, error: polled.error };
}
