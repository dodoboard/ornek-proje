import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProjectForm } from "./ProjectForm";

describe("ProjectForm", () => {
  it("submits a typed payload with trimmed name and chosen settings", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ProjectForm onSubmit={onSubmit} />);

    const submit = screen.getByRole("button", { name: "Create project" });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText("Name"), "  Villa tour  ");
    await user.selectOptions(screen.getByLabelText("Type"), "real_estate");
    await user.selectOptions(screen.getByLabelText("Duration"), "60");
    await user.selectOptions(screen.getByLabelText("Format"), "16:9");
    await user.click(submit);

    expect(onSubmit).toHaveBeenCalledWith({
      name: "Villa tour",
      type: "real_estate",
      settings: { platform: "instagram", aspect_ratio: "16:9", duration_s: 60, tone: "professional", language: "tr" },
    });
  });

  it("shows server errors", () => {
    render(<ProjectForm onSubmit={vi.fn()} error="Request validation failed." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Request validation failed.");
  });
});
