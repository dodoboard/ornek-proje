import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { makeJob } from "@/test/jobFixture";

import { JobProgress } from "./JobProgress";

describe("JobProgress", () => {
  it("shows stage, progress and allows cancel while running", async () => {
    const onCancel = vi.fn();
    const job = makeJob();
    render(<JobProgress job={job} onCancel={onCancel} />);
    expect(screen.getByText("Encoding FFmpeg test clip")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Progress" })).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText("Running")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledWith(job);
  });

  it("shows cancelling state and hides the button once requested", () => {
    render(<JobProgress job={makeJob({ cancel_requested: true })} onCancel={vi.fn()} />);
    expect(screen.getByText("Cancelling…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("shows a user-facing error for failed jobs", () => {
    const job = makeJob({
      status: "failed",
      error_code: "VRAM_OOM",
      error_message: "The GPU ran out of memory.",
      finished_at: "2026-09-27T10:00:30Z",
    });
    render(<JobProgress job={job} onCancel={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("VRAM_OOM: The GPU ran out of memory.");
    expect(screen.getByLabelText("Elapsed time")).toHaveTextContent("0:30");
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });
});
