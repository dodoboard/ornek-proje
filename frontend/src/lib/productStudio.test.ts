import { describe, expect, it } from "vitest";

import { placementBox, scaleNote } from "./productStudio";

const CUTOUT = { width: 101, height: 221 };

describe("placementBox", () => {
  it("keeps native size and anchors the product's bottom edge", () => {
    expect(placementBox(CUTOUT, { width: 512, height: 512 }, { x: 0.5, y: 0.9, height_ratio: 0.5, native_scale: true })).toEqual({
      box: { left: 206, top: 240, width: 101, height: 221 },
      scale: 1,
    });
  });

  it("scales to the height ratio and clamps into the frame (like the backend)", () => {
    const result = placementBox(CUTOUT, { width: 512, height: 512 }, { x: 0.95, y: 1, height_ratio: 0.6, native_scale: false });
    expect(result).toEqual({ box: { left: 372, top: 205, width: 140, height: 307 }, scale: 307 / 221 });
  });

  it("reports a product that does not fit", () => {
    const result = placementBox(CUTOUT, { width: 256, height: 1024 }, { x: 0.5, y: 0.5, height_ratio: 1, native_scale: false });
    expect(result).toEqual({ error: expect.stringMatching(/does not fit the 256x1024px image/) });
  });
});

describe("scaleNote", () => {
  it("describes resampling honestly", () => {
    const base = { exact: true, protected_pixels: 1, opaque_product_pixels: 1, clamped_to_frame: false };
    expect(scaleNote({ ...base, scale: 1, resampled: false, upscaled: false })).toBe("1:1 original pixels");
    expect(scaleNote({ ...base, scale: 1.389, resampled: true, upscaled: true })).toBe("upscaled ×1.39 from the original");
  });
});
