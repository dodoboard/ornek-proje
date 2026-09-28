import type { JobRead, JobStatus } from "@/lib/api/client";

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  loading_model: "Loading model",
  generating_script: "Writing script",
  generating_storyboard: "Building storyboard",
  generating_image: "Generating image",
  processing_product: "Processing product",
  generating_video: "Generating video",
  generating_audio: "Generating audio",
  lip_sync: "Lip-sync",
  creating_captions: "Creating captions",
  encoding: "Encoding",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const TERMINAL: ReadonlySet<JobStatus> = new Set<JobStatus>(["completed", "failed", "cancelled"]);

export function isTerminal(status: JobStatus): boolean {
  return TERMINAL.has(status);
}

export function jobTypeLabel(type: string): string {
  return type.replace(/[_.-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Elapsed run time: started → finished (or now while running). Null before start. */
export function elapsedMs(job: Pick<JobRead, "started_at" | "finished_at">, now: number): number | null {
  if (!job.started_at) return null;
  const start = Date.parse(job.started_at);
  const end = job.finished_at ? Date.parse(job.finished_at) : now;
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.max(0, end - start);
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
