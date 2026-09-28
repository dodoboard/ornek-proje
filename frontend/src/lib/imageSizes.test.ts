import { describe, expect, it } from "vitest";

import { ASPECT_PRESETS, MAX_SEED, parseSeed, presetById } from "./imageSizes";

describe("image sizes", () => {
  it("every preset is a multiple of 16 and about one megapixel", () => {
    for (const preset of ASPECT_PRESETS) {
      expect(preset.width % 16).toBe(0);
      expect(preset.height % 16).toBe(0);
      expect(preset.width * preset.height).toBeGreaterThan(0.9e6);
      expect(preset.width * preset.height).toBeLessThan(1.1e6);
    }
  });

  it("falls back to the first preset", () => {
    expect(presetById("nope").id).toBe("1:1");
  });

  it("parses seeds strictly", () => {
    expect(parseSeed("42")).toBe(42);
    expect(parseSeed(" 7 ")).toBe(7);
    expect(parseSeed("-1")).toBeNull();
    expect(parseSeed("1.5")).toBeNull();
    expect(parseSeed(String(MAX_SEED + 1))).toBeNull();
  });
});
