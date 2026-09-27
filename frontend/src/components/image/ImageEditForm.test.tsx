import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AssetRead, GenerationRead, ProviderInfo } from "@/lib/api/client";

import { ImageEditForm } from "./ImageEditForm";

const KLEIN = {
  kind: "image",
  key: "flux2_klein_4b",
  provider: "flux2_diffusers",
  status: "available",
  detail: null,
  maturity: "stable",
  verification: "verified",
  license_claim: null,
  note: null,
  source: null,
  is_default: true,
  is_local: true,
  capabilities: {
    image_edit: true,
    inpainting: true,
    max_reference_images: 4,
    min_size: 256,
    max_size: 2048,
    default_steps: 4,
    max_images_per_request: 4,
    guidance: false,
  },
} satisfies ProviderInfo;

const SOURCE: AssetRead = {
  id: "AST_SRC",
  kind: "image",
  source: "generated",
  mime: "image/png",
  size_bytes: 1,
  checksum_sha256: "x",
  width: 1024,
  height: 1024,
  duration_s: null,
  original_filename: null,
  ai_generated: true,
  metadata: {},
  created_at: "2026-09-27T10:00:00Z",
  updated_at: "2026-09-27T10:00:00Z",
};

const RECENT: GenerationRead[] = [
  {
    id: "GEN_1",
    kind: "image",
    job_id: "JOB_1",
    project_id: null,
    character_id: null,
    provider: "flux2_diffusers",
    model_key: "flux2_klein_4b",
    model_source: null,
    params: {},
    seeds: [1],
    input_asset_ids: [],
    output_asset_ids: ["AST_SRC"],
    duration_ms: 1,
    assets: [SOURCE],
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:00:00Z",
  },
];

function setup(mode: "edit" | "inpaint" | "outpaint") {
  const onSubmit = vi.fn();
  render(
    <ImageEditForm
      mode={mode}
      models={[KLEIN]}
      defaultModelKey="flux2_klein_4b"
      recent={RECENT}
      onSubmit={onSubmit}
      pending={false}
    />,
  );
  return onSubmit;
}

describe("ImageEditForm", () => {
  beforeEach(() => {
    // jsdom has no 2D canvas; the mask editor must tolerate that.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  });

  it("builds an outpaint request from padding and shows the result size", async () => {
    const onSubmit = setup("outpaint");
    await userEvent.click(screen.getByRole("radio", { name: "Source AST_SRC" }));
    expect(screen.getByText("Result 1024×1280px (source 1024×1024)")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Extend left"), "128");
    await userEvent.type(screen.getByLabelText("Prompt for the new area"), "more beach");
    await userEvent.click(screen.getByRole("button", { name: "Run outpaint" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: "outpaint",
        source_asset_id: "AST_SRC",
        padding: { left: 128, top: 0, right: 0, bottom: 256 },
        strength: 1,
        feather: 8,
        mask_asset_id: null,
        guidance_scale: null,
      }),
    );
  });

  it("blocks outpaint results larger than the model allows", async () => {
    setup("outpaint");
    await userEvent.click(screen.getByRole("radio", { name: "Source AST_SRC" }));
    await userEvent.selectOptions(screen.getByLabelText("Extend right"), "1024");
    await userEvent.type(screen.getByLabelText("Prompt for the new area"), "x");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // 1024 + 1024 = 2048 is still allowed
    await userEvent.selectOptions(screen.getByLabelText("Extend left"), "64");
    expect(screen.getByRole("alert")).toHaveTextContent("Result width 2112px is outside 256-2048px");
    expect(screen.getByRole("button", { name: "Run outpaint" })).toBeDisabled();
  });

  it("sends instruction edits without strength and with one reference slot fewer", async () => {
    const onSubmit = setup("edit");
    expect(screen.getByText("Reference images (0/3)")).toBeInTheDocument();
    expect(screen.queryByLabelText("Strength (0.05-1)")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Source AST_SRC" }));
    await userEvent.type(screen.getByLabelText("Instruction"), "make it night");
    await userEvent.click(screen.getByRole("button", { name: "Apply edit" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ mode: "edit", strength: null, padding: null, mask_asset_id: null }),
    );
  });

  it("requires a painted mask for inpaint", async () => {
    const onSubmit = setup("inpaint");
    await userEvent.click(screen.getByRole("radio", { name: "Source AST_SRC" }));
    await userEvent.type(screen.getByLabelText("Prompt for the new area"), "a cup");
    expect(screen.getByLabelText("Mask canvas")).toHaveAttribute("width", "1024");
    expect(screen.getByText("Paint a mask to continue.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run inpaint" })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
