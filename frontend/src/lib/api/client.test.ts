import { describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("apiFetch", () => {
  it("returns parsed JSON on success", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ status: "ok" }));
    await expect(apiFetch("/api/health", undefined, fetchImpl)).resolves.toEqual({ status: "ok" });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/health",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("maps the backend error envelope to ApiError", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ error: { code: "VRAM_OOM", message: "Out of memory" } }, 507));
    const error = await apiFetch("/x", undefined, fetchImpl).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "VRAM_OOM", message: "Out of memory", status: 507 });
  });

  it("never leaks non-envelope bodies", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("Traceback (most recent call last)", { status: 500 }));
    await expect(apiFetch("/x", undefined, fetchImpl)).rejects.toMatchObject({
      code: "HTTP_500",
      message: "The backend returned an unexpected error.",
    });
  });

  it("reports an unreachable backend", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(apiFetch("/x", undefined, fetchImpl)).rejects.toMatchObject({ code: "BACKEND_UNREACHABLE", status: 0 });
  });
});

describe("apiFetch 204", () => {
  it("returns undefined for No Content", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiFetch("/api/projects/PRJ_1", { method: "DELETE" }, fetchImpl)).resolves.toBeUndefined();
  });
});
