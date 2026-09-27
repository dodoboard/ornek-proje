import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, api, type SystemResponse } from "@/lib/api/client";

import { SystemStatus } from "./SystemStatus";

const SYSTEM: SystemResponse = {
  app_name: "AI Influencer Studio",
  version: "0.1.0",
  app_env: "development",
  python_version: "3.12.14",
  platform: "Linux",
  device_preference: "auto",
  performance_profile: "balanced",
  fake_providers_enabled: false,
  privacy: { telemetry_enabled: false, offline_mode: true },
  gpu: {
    status: "ok",
    source: "nvidia-smi",
    detail: null,
    devices: [
      {
        index: 0,
        name: "NVIDIA GeForce RTX 5080 Laptop GPU",
        driver_version: "580.10",
        memory_total_mb: 16303,
        memory_used_mb: 1024,
        memory_free_mb: 15279,
      },
    ],
  },
  ffmpeg: { status: "missing", path: null, version: null },
  ffprobe: { status: "missing", path: null, version: null },
  storage: { data_dir: "/data", total_gb: 1000, used_gb: 400, free_gb: 600 },
};

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SystemStatus />
    </QueryClientProvider>,
  );
}

describe("SystemStatus", () => {
  it("shows GPU, VRAM and storage from the API", async () => {
    vi.spyOn(api, "system").mockResolvedValue(SYSTEM);
    renderWithClient();
    expect(await screen.findByText("NVIDIA GeForce RTX 5080 Laptop GPU")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "VRAM used" })).toHaveAttribute("aria-valuenow", "6");
    expect(screen.getByText("600.0 GB free")).toBeInTheDocument();
  });

  it("shows a friendly error when the backend is down", async () => {
    vi.spyOn(api, "system").mockRejectedValue(new ApiError("BACKEND_UNREACHABLE", "Cannot reach the local backend.", 0));
    renderWithClient();
    expect(await screen.findByText("BACKEND_UNREACHABLE")).toBeInTheDocument();
    expect(screen.getByText("Cannot reach the local backend.")).toBeInTheDocument();
  });
});
