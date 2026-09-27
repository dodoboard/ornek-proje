import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AssetRead, GenerationRead } from "@/lib/api/client";

import { GenerationGallery } from "./GenerationGallery";

function asset(id: string, metadata: Record<string, unknown>): AssetRead {
  return {
    id,
    kind: "image",
    source: "generated",
    mime: "image/png",
    size_bytes: 1,
    checksum_sha256: "x",
    width: 64,
    height: 64,
    duration_s: null,
    original_filename: null,
    ai_generated: true,
    metadata,
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:00:00Z",
  };
}

const GENERATION: GenerationRead = {
  id: "GEN_1",
  kind: "image",
  job_id: "JOB_1",
  project_id: null,
  character_id: null,
  provider: "flux2_diffusers",
  model_key: "flux2_klein_4b",
  model_source: null,
  params: { prompt: "adult portrait" },
  seeds: [1, 2],
  input_asset_ids: [],
  output_asset_ids: ["AST_1", "AST_2"],
  duration_ms: 1000,
  assets: [asset("AST_1", { seed: 1 }), asset("AST_2", { seed: 2, dev_placeholder: true })],
  created_at: "2026-09-27T10:00:00Z",
  updated_at: "2026-09-27T10:00:00Z",
};

describe("GenerationGallery", () => {
  it("labels real output and dev placeholders differently", () => {
    render(<GenerationGallery generations={[GENERATION]} />);
    expect(screen.getByText("AI generated")).toBeInTheDocument();
    expect(screen.getByText("DEV PLACEHOLDER")).toBeInTheDocument();
    expect(screen.getByText("flux2_klein_4b · seed 1")).toBeInTheDocument();
    expect(screen.getAllByRole("img")[0]).toHaveAttribute(
      "src",
      "http://127.0.0.1:8000/api/assets/AST_1/thumbnail",
    );
  });

  it("marks edits as AI edited with their mode", () => {
    const edit: GenerationRead = {
      ...GENERATION,
      id: "GEN_2",
      kind: "image_edit",
      params: { prompt: "red jacket", mode: "inpaint" },
      assets: [asset("AST_3", { seed: 7 })],
    };
    render(<GenerationGallery generations={[edit]} />);
    expect(screen.getByText("AI edited")).toBeInTheDocument();
    expect(screen.getByText("inpaint · flux2_klein_4b · seed 7")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<GenerationGallery generations={[]} />);
    expect(screen.getByText("No images yet")).toBeInTheDocument();
  });
});
