import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Meter } from "./Meter";

describe("Meter", () => {
  it("uses warning colors for usage near capacity but not for progress", () => {
    render(
      <>
        <Meter label="Disk" value={95} max={100} caption="95%" />
        <Meter label="Job" value={100} max={100} caption="100%" variant="progress" />
      </>,
    );
    expect(screen.getByRole("meter", { name: "Disk" }).firstElementChild).toHaveClass("bg-danger");
    expect(screen.getByRole("meter", { name: "Job" }).firstElementChild).toHaveClass("bg-accent");
  });
});
