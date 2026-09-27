import type { JobRead } from "@/lib/api/client";

export function makeJob(overrides: Partial<JobRead> = {}): JobRead {
  return {
    id: "JOB_1",
    type: "diagnostics",
    status: "running",
    progress: 40,
    stage: "Encoding FFmpeg test clip",
    message: null,
    error_code: null,
    error_message: null,
    result: null,
    cancel_requested: false,
    attempts: 1,
    project_id: null,
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:00:01Z",
    started_at: "2026-09-27T10:00:00Z",
    finished_at: null,
    ...overrides,
  };
}
