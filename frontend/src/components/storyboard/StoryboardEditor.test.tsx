import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ScriptRead, ShotRead } from "@/lib/api/client";
import { durationSummary, move, scriptOrigin } from "@/lib/storyboard";

import { StoryboardEditor } from "./StoryboardEditor";

function shot(id: string, position: number, extra: Partial<ShotRead> = {}): ShotRead {
  return {
    id,
    storyboard_id: "SB_1",
    position,
    type: "talking_head",
    duration_s: 5,
    description: "",
    dialogue: `line ${id}`,
    on_screen_text: "",
    visual_prompt: "",
    camera: "medium",
    camera_motion: "static",
    generation_method: "lipsync",
    disclosure_label: "ai_generated",
    edited: false,
    status: "draft",
    keyframe_asset_id: null,
    clip_asset_id: null,
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:00:00Z",
    ...extra,
  };
}

const SHOTS = [shot("A", 0), shot("B", 1, { type: "cta", on_screen_text: "1.299 TRY" }), shot("C", 2)];

function setup() {
  const handlers = { onReorder: vi.fn(), onSave: vi.fn(), onDelete: vi.fn() };
  render(<StoryboardEditor shots={SHOTS} pending={false} {...handlers} />);
  return handlers;
}

describe("StoryboardEditor", () => {
  it("reorders with the move buttons and shows the new order immediately", async () => {
    const { onReorder } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Move shot 1 down" }));
    expect(onReorder).toHaveBeenCalledWith(["B", "A", "C"]);
    const items = within(screen.getByRole("list", { name: "Shots" })).getAllByRole("listitem");
    expect(items[0]).toHaveAccessibleName("Shot 1: Call to action");
    expect(screen.getByRole("button", { name: "Move shot 1 up" })).toBeDisabled();
  });

  it("edits a shot and sends only valid values", async () => {
    const { onSave } = setup();
    const card = screen.getByRole("listitem", { name: "Shot 2: Call to action" });
    await userEvent.click(within(card).getByRole("button", { name: "Edit" }));
    const form = screen.getByRole("form", { name: "Edit shot 2" });
    await userEvent.clear(within(form).getByLabelText("Duration (s)"));
    await userEvent.type(within(form).getByLabelText("Duration (s)"), "7.5");
    await userEvent.selectOptions(within(form).getByLabelText("Made with"), "real_footage");
    await userEvent.click(within(form).getByRole("button", { name: "Save shot" }));
    expect(onSave).toHaveBeenCalledWith("B", expect.objectContaining({ duration_s: 7.5, generation_method: "real_footage" }));
  });

  it("deletes a shot", async () => {
    const { onDelete } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Delete shot 3" }));
    expect(onDelete).toHaveBeenCalledWith("C");
  });
});

describe("storyboard helpers", () => {
  it("moves items and summarises duration", () => {
    expect(move(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
    expect(durationSummary(SHOTS, 15)).toEqual({ total: 15, diff: 0, ok: true });
    expect(durationSummary(SHOTS, 30).ok).toBe(false);
  });

  it("explains a template fallback", () => {
    const script = {
      source: "template",
      llm_model: "ollama_default",
      attempts: [{ attempt: 1, ok: false, errors: ["shots[0].dialogue: Numbers must come from a {{placeholder}}. (found '999')"] }],
    } as unknown as ScriptRead;
    const origin = scriptOrigin(script);
    expect(origin.label).toBe("Template fallback");
    expect(origin.reasons[0]).toContain("999");
  });
});
