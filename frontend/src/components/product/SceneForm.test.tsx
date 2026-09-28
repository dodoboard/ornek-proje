import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AssetRead, GenerationRead, ProviderInfo } from "@/lib/api/client";

import { SceneForm } from "./SceneForm";
import { SceneGallery } from "./SceneGallery";

function model(key: string, inpainting: boolean): ProviderInfo {
  return {
    kind: "image",
    key,
    provider: key,
    status: "available",
    detail: null,
    maturity: "stable",
    verification: "verified",
    license_claim: null,
    note: null,
    source: null,
    is_default: true,
    is_local: true,
    capabilities: { inpainting, max_images_per_request: 4, default_steps: 4 },
  };
}

const CUTOUT = {
  id: "AST_CUT",
  kind: "image",
  source: "derived",
  mime: "image/png",
  size_bytes: 1,
  checksum_sha256: "x",
  width: 101,
  height: 221,
  duration_s: null,
  original_filename: null,
  ai_generated: false,
  metadata: {},
  created_at: "2026-09-27T10:00:00Z",
  updated_at: "2026-09-27T10:00:00Z",
} satisfies AssetRead;

describe("SceneForm", () => {
  it("sends placement, shadow and a generated background", async () => {
    const onSubmit = vi.fn();
    render(<SceneForm cutout={CUTOUT} models={[model("klein", true)]} defaultModelKey="klein" onSubmit={onSubmit} pending={false} />);
    await userEvent.type(screen.getByLabelText("Scene"), "marble counter");
    await userEvent.click(screen.getByRole("radio", { name: "1:1" }));
    await userEvent.click(screen.getByRole("switch", { name: "Blend edges with AI" }));
    await userEvent.click(screen.getByRole("button", { name: "Create scene" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        cutout_asset_id: "AST_CUT",
        scene: "marble counter",
        width: 1024,
        height: 1024,
        placement: { x: 0.5, y: 0.85, height_ratio: 0.5, native_scale: false },
        shadow: true,
        harmonize: { enabled: true, ring_px: 6, strength: 0.35 },
        background_asset_id: null,
        model_key: "klein",
      }),
    );
    expect(screen.getByText(/product 234×512px \(upscaled/)).toBeInTheDocument();
  });

  it("disables edge blending without inpainting and needs a photo without models", async () => {
    render(<SceneForm cutout={CUTOUT} models={[]} defaultModelKey={null} onSubmit={vi.fn()} pending={false} />);
    expect(screen.getByRole("switch", { name: "Blend edges with AI" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Generate with AI" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Scene"), "desk");
    expect(screen.getByRole("alert")).toHaveTextContent("Upload a background photo.");
    expect(screen.getByRole("button", { name: "Create scene" })).toBeDisabled();
  });

  it("keeps original pixels when native size is chosen", async () => {
    render(<SceneForm cutout={CUTOUT} models={[model("klein", false)]} defaultModelKey="klein" onSubmit={vi.fn()} pending={false} />);
    await userEvent.click(screen.getByRole("switch", { name: "Original size (1:1 pixels)" }));
    expect(screen.getByText(/product 101×221px$/)).toBeInTheDocument();
  });
});

describe("SceneGallery", () => {
  it("shows the preservation result per image", () => {
    const generation = {
      id: "GEN_1",
      kind: "product_scene",
      job_id: null,
      project_id: null,
      character_id: null,
      product_id: "PRD_1",
      provider: "flux2_diffusers",
      model_key: "klein",
      model_source: null,
      params: {
        scene: "counter",
        preservation: [{ exact: true, scale: 1, resampled: false, upscaled: false, protected_pixels: 5, opaque_product_pixels: 5, clamped_to_frame: false }],
      },
      seeds: [1],
      input_asset_ids: [],
      output_asset_ids: ["AST_1"],
      duration_ms: 1,
      assets: [{ ...CUTOUT, id: "AST_1", metadata: { background: "user_photo" } }],
      created_at: "2026-09-27T10:00:00Z",
      updated_at: "2026-09-27T10:00:00Z",
    } satisfies GenerationRead;
    render(<SceneGallery generations={[generation]} />);
    expect(screen.getByText("Product pixels verified")).toBeInTheDocument();
    expect(screen.getByText("1:1 original pixels · your photo")).toBeInTheDocument();
  });
});
