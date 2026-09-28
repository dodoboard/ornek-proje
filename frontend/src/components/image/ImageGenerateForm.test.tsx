import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProviderInfo } from "@/lib/api/client";

import { ImageGenerateForm } from "./ImageGenerateForm";

function model(key: string, capabilities: Record<string, unknown>, maturity: ProviderInfo["maturity"] = "stable") {
  return {
    kind: "image",
    key,
    provider: key,
    status: "available",
    detail: null,
    maturity,
    verification: "verified",
    license_claim: null,
    note: null,
    source: null,
    is_default: false,
    is_local: true,
    capabilities,
  } satisfies ProviderInfo;
}

const KLEIN = model("flux2_klein_4b", {
  guidance: false,
  max_reference_images: 4,
  default_steps: 4,
  max_images_per_request: 4,
});
const BASE = model("flux2_klein_base_9b", { guidance: true, max_reference_images: 0, default_steps: 50 });

describe("ImageGenerateForm", () => {
  it("builds a request from the chosen preset, seed and count", async () => {
    const onSubmit = vi.fn();
    render(<ImageGenerateForm models={[KLEIN]} defaultModelKey="flux2_klein_4b" onSubmit={onSubmit} pending={false} />);

    expect(screen.queryByLabelText("Guidance scale")).not.toBeInTheDocument();
    expect(screen.getByText("Reference images (0/4)")).toBeInTheDocument();
    expect(screen.getByLabelText("Steps (default 4)")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Prompt"), "adult chef in a sunny kitchen");
    await userEvent.click(screen.getByRole("radio", { name: /16:9/ }));
    await userEvent.type(screen.getByLabelText("Seed (empty = random)"), "123");
    await userEvent.selectOptions(screen.getByLabelText("Images"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(onSubmit).toHaveBeenCalledWith({
      prompt: "adult chef in a sunny kitchen",
      model_key: "flux2_klein_4b",
      width: 1360,
      height: 768,
      num_images: 2,
      steps: null,
      seed: 123,
      guidance_scale: null,
      reference_asset_ids: [],
    });
  });

  it("shows guidance only for models that use it and hides references when unsupported", async () => {
    render(
      <ImageGenerateForm models={[KLEIN, BASE]} defaultModelKey="flux2_klein_4b" onSubmit={vi.fn()} pending={false} />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Model"), "flux2_klein_base_9b");
    expect(screen.getByLabelText("Guidance scale")).toBeInTheDocument();
    expect(screen.queryByText(/Reference images/)).not.toBeInTheDocument();
  });

  it("blocks invalid seeds", async () => {
    render(<ImageGenerateForm models={[KLEIN]} defaultModelKey={null} onSubmit={vi.fn()} pending={false} />);
    await userEvent.type(screen.getByLabelText("Prompt"), "x");
    await userEvent.type(screen.getByLabelText("Seed (empty = random)"), "abc");
    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Seed must be a whole number.");
  });

  it("explains what to do when no model is ready", () => {
    render(<ImageGenerateForm models={[]} defaultModelKey={null} onSubmit={vi.fn()} pending={false} />);
    expect(screen.getByText(/No image model is ready/)).toBeInTheDocument();
  });
});
