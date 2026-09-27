import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Toggle } from "@/components/ui/Toggle";

import { PerformanceSection } from "./PerformanceSection";

describe("settings controls", () => {
  it("selects a performance profile", async () => {
    const onChange = vi.fn();
    render(<PerformanceSection value="balanced" onChange={onChange} disabled={false} />);
    expect(screen.getByRole("radio", { name: /Balanced/ })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("radio", { name: /Low VRAM/ }));
    expect(onChange).toHaveBeenCalledWith("low_vram");
  });

  it("toggles a switch", async () => {
    const onChange = vi.fn();
    render(<Toggle label="Offline mode" checked={false} onChange={onChange} />);
    await userEvent.click(screen.getByRole("switch", { name: "Offline mode" }));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});
