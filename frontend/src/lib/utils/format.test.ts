import { describe, expect, it } from "vitest";

import { formatGigabytes, formatMegabytes, percent } from "./format";

describe("format", () => {
  it("formats megabytes", () => {
    expect(formatMegabytes(512)).toBe("512 MB");
    expect(formatMegabytes(16303)).toBe("15.9 GB");
    expect(formatMegabytes(-1)).toBe("—");
  });

  it("formats gigabytes", () => {
    expect(formatGigabytes(29.54)).toBe("29.5 GB");
    expect(formatGigabytes(Number.NaN)).toBe("—");
  });

  it("clamps percentages", () => {
    expect(percent(5, 10)).toBe(50);
    expect(percent(20, 10)).toBe(100);
    expect(percent(1, 0)).toBe(0);
  });
});
