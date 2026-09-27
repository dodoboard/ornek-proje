import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProjectRead } from "@/lib/api/client";

import { ProjectList } from "./ProjectList";

const PROJECT: ProjectRead = {
  id: "PRJ_1",
  type: "land",
  name: "Seaside plot",
  description: "",
  character_id: null,
  product_id: null,
  property_id: null,
  settings: { platform: "tiktok", duration_s: 15, aspect_ratio: "9:16", tone: "minimal", preset: null, language: "tr" },
  created_at: "2026-09-27T10:00:00Z",
  updated_at: "2026-09-27T10:00:00Z",
};

describe("ProjectList", () => {
  it("renders an empty state", () => {
    render(<ProjectList projects={[]} />);
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
  });

  it("renders projects and triggers delete", async () => {
    const onDelete = vi.fn();
    render(<ProjectList projects={[PROJECT]} onDelete={onDelete} />);
    expect(screen.getByText("Seaside plot")).toBeInTheDocument();
    expect(screen.getByText("Land")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete Seaside plot" }));
    expect(onDelete).toHaveBeenCalledWith(PROJECT);
  });
});
