import { describe, expect, it } from "vitest";

import type { GenerationRead } from "@/lib/api/client";

import { imagesForPurpose, parseTraits } from "./characters";

function gen(id: string, purpose: string, seeds: number[]): GenerationRead {
  return {
    id,
    kind: "image",
    job_id: null,
    project_id: null,
    character_id: "CHR_1",
    provider: "p",
    model_key: "m",
    model_source: null,
    params: { purpose },
    seeds,
    input_asset_ids: [],
    output_asset_ids: seeds.map((s) => `AST_${s}`),
    duration_ms: 0,
    assets: seeds.map((s) => ({
      id: `AST_${s}`,
      kind: "image",
      source: "generated",
      mime: "image/png",
      size_bytes: 1,
      checksum_sha256: "",
      width: 1,
      height: 1,
      duration_s: null,
      original_filename: null,
      ai_generated: true,
      metadata: { seed: s },
      created_at: "",
      updated_at: "",
    })),
    created_at: "",
    updated_at: "",
  };
}

describe("character helpers", () => {
  it("groups generated images by workflow step", () => {
    const all = [gen("G1", "candidates", [1, 2]), gen("G2", "front", [3]), gen("G3", "candidates", [4])];
    expect(imagesForPurpose(all, "candidates").map((i) => i.seed)).toEqual([1, 2, 4]);
    expect(imagesForPurpose(all, "front").map((i) => i.asset.id)).toEqual(["AST_3"]);
    expect(imagesForPurpose(all, "scene")).toEqual([]);
  });

  it("parses traits from lines or commas", () => {
    expect(parseTraits("mole above lip\n  green eyes, \n\n tattoo on wrist")).toEqual([
      "mole above lip",
      "green eyes",
      "tattoo on wrist",
    ]);
  });
});
