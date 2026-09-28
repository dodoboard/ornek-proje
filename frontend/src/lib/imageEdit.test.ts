import { describe, expect, it } from "vitest";

import {
  availableModes,
  editOutputSize,
  editSizeError,
  hasPaint,
  overlayToMask,
  referenceSlots,
  supportsMode,
} from "./imageEdit";

const KLEIN = { image_edit: true, inpainting: true, max_reference_images: 4, min_size: 256, max_size: 2048 };
const DEV_ONLY_T2I = { image_edit: false, inpainting: false, max_reference_images: 0 };

describe("modes", () => {
  it("derives modes from capabilities", () => {
    expect(supportsMode(KLEIN, "outpaint")).toBe(true);
    expect(supportsMode({ ...KLEIN, max_reference_images: 0 }, "edit")).toBe(false);
    expect(availableModes([{ capabilities: DEV_ONLY_T2I }])).toEqual(["generate"]);
    expect(availableModes([{ capabilities: DEV_ONLY_T2I }, { capabilities: KLEIN }])).toEqual([
      "generate",
      "edit",
      "inpaint",
      "outpaint",
    ]);
  });

  it("reserves one reference slot for the source in edit mode", () => {
    expect(referenceSlots(KLEIN, "edit")).toBe(3);
    expect(referenceSlots(KLEIN, "inpaint")).toBe(4);
  });
});

describe("sizes", () => {
  it("snaps the source and adds outpaint padding", () => {
    expect(editOutputSize({ width: 1001, height: 767 }, "inpaint")).toEqual({ width: 992, height: 752 });
    expect(
      editOutputSize({ width: 1024, height: 1024 }, "outpaint", { left: 128, top: 0, right: 64, bottom: 64 }),
    ).toEqual({ width: 1216, height: 1088 });
  });

  it("reports size and padding problems", () => {
    const src = { width: 1024, height: 1024 };
    expect(editSizeError(KLEIN, src, "outpaint", { left: 0, top: 0, right: 0, bottom: 0 })).toBe(
      "Extend at least one side.",
    );
    expect(editSizeError(KLEIN, src, "outpaint", { left: 1024, top: 0, right: 64, bottom: 0 })).toMatch(
      /width 2112px is outside 256-2048px/,
    );
    expect(editSizeError(KLEIN, { width: 200, height: 512 }, "inpaint")).toMatch(/width 192px/);
    expect(editSizeError(KLEIN, src, "edit")).toBeNull();
  });
});

describe("mask export", () => {
  it("turns painted pixels white and everything else opaque black", () => {
    const overlay = new Uint8ClampedArray([255, 0, 0, 200, 10, 10, 10, 0, 0, 0, 255, 127]);
    expect(Array.from(overlayToMask(overlay))).toEqual([255, 255, 255, 255, 0, 0, 0, 255, 0, 0, 0, 255]);
    expect(hasPaint(overlay)).toBe(true);
    expect(hasPaint(new Uint8ClampedArray([255, 255, 255, 10]))).toBe(false);
  });
});
