import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { KindModels, ProviderInfo } from "@/lib/api/client";
import { capabilityFlags } from "@/lib/models";

import { ModelKindCard } from "./ModelKindCard";

function provider(overrides: Partial<ProviderInfo>): ProviderInfo {
  return {
    kind: "image",
    key: "flux2_klein_4b",
    provider: "flux2_diffusers",
    status: "not_implemented",
    detail: "Integration not implemented yet.",
    maturity: "stable",
    verification: "needs-user-machine",
    license_claim: "Apache-2.0 (unverified)",
    note: null,
    source: "black-forest-labs/FLUX.2-klein-4B",
    is_default: true,
    is_local: true,
    capabilities: null,
    ...overrides,
  };
}

const GROUP: KindModels = {
  kind: "image",
  default_key: "flux2_klein_4b",
  providers: [
    provider({}),
    provider({
      key: "dev_fake_image",
      provider: "dev_fake_image",
      status: "available",
      maturity: "dev_only",
      verification: "dev-only",
      is_default: false,
      source: null,
      capabilities: { text_to_image: true, inpainting: false, max_size: 2048 },
    }),
  ],
};

describe("ModelKindCard", () => {
  it("renders status honestly and only allows selecting implemented models", async () => {
    const onUpdate = vi.fn();
    render(<ModelKindCard group={GROUP} localPaths={{}} onUpdate={onUpdate} pending={false} />);

    expect(screen.getByText("Not implemented")).toBeInTheDocument();
    expect(screen.getByText("dev only")).toBeInTheDocument();
    expect(screen.queryByText("dev-only")).not.toBeInTheDocument();
    expect(screen.getByText("needs-user-machine")).toBeInTheDocument();
    expect(screen.getByLabelText("Use flux2_klein_4b as default")).toBeDisabled();

    await userEvent.click(screen.getByLabelText("Use dev_fake_image as default"));
    expect(onUpdate).toHaveBeenCalledWith({ default_models: { image: "dev_fake_image" } });
  });

  it("saves a local path override and hides it for dev placeholders", async () => {
    const onUpdate = vi.fn();
    render(<ModelKindCard group={GROUP} localPaths={{}} onUpdate={onUpdate} pending={false} />);
    expect(screen.queryByLabelText("Local path for dev_fake_image")).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Local path for flux2_klein_4b"), "D:/models/klein");
    await userEvent.click(screen.getByRole("button", { name: "Save path" }));
    expect(onUpdate).toHaveBeenCalledWith({ model_paths: { flux2_klein_4b: "D:/models/klein" } });
  });

  it("lists only enabled capability flags", () => {
    expect(capabilityFlags({ text_to_image: true, inpainting: false, max_size: 2048 })).toEqual(["text to image"]);
    expect(capabilityFlags(null)).toEqual([]);
  });
});
