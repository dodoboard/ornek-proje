import { describe, expect, it } from "vitest";

import { elapsedMs, formatDuration, isTerminal, jobTypeLabel } from "./jobs";

describe("jobs utils", () => {
  it("detects terminal states", () => {
    expect(isTerminal("completed")).toBe(true);
    expect(isTerminal("cancelled")).toBe(true);
    expect(isTerminal("generating_video")).toBe(false);
  });

  it("computes elapsed time", () => {
    const start = "2026-09-27T10:00:00Z";
    expect(elapsedMs({ started_at: null, finished_at: null }, 0)).toBeNull();
    expect(elapsedMs({ started_at: start, finished_at: "2026-09-27T10:01:05Z" }, 0)).toBe(65_000);
    expect(elapsedMs({ started_at: start, finished_at: null }, Date.parse(start) + 3_000)).toBe(3_000);
  });

  it("formats durations", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(65_000)).toBe("1:05");
    expect(formatDuration(3_725_000)).toBe("1:02:05");
  });

  it("labels job types", () => {
    expect(jobTypeLabel("product_ad.render")).toBe("Product ad render");
  });
});
