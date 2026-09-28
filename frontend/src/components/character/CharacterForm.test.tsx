import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CharacterForm } from "./CharacterForm";

describe("CharacterForm", () => {
  it("submits a character with only filled fields", async () => {
    const onSubmit = vi.fn();
    render(<CharacterForm onSubmit={onSubmit} pending={false} />);
    await userEvent.type(screen.getByLabelText("Name"), "Deniz");
    await userEvent.clear(screen.getByLabelText("Age (18+)"));
    await userEvent.type(screen.getByLabelText("Age (18+)"), "28");
    await userEvent.type(screen.getByLabelText("Hair"), "wavy dark brown");
    await userEvent.click(screen.getByRole("button", { name: "Create influencer" }));
    expect(onSubmit).toHaveBeenCalledWith({
      character: { name: "Deniz", adult_age: 28, default_language: "tr", is_real_person: false, hair: "wavy dark brown" },
      consent: null,
    });
  });

  it("blocks minors", async () => {
    render(<CharacterForm onSubmit={vi.fn()} pending={false} />);
    await userEvent.type(screen.getByLabelText("Name"), "X");
    await userEvent.clear(screen.getByLabelText("Age (18+)"));
    await userEvent.type(screen.getByLabelText("Age (18+)"), "17");
    expect(screen.getByRole("alert")).toHaveTextContent("Characters must be adults");
    expect(screen.getByRole("button", { name: "Create influencer" })).toBeDisabled();
  });

  it("requires explicit consent for a real person", async () => {
    const onSubmit = vi.fn();
    render(<CharacterForm onSubmit={onSubmit} pending={false} />);
    await userEvent.type(screen.getByLabelText("Name"), "Jane");
    await userEvent.click(screen.getByLabelText(/based on a real person/));
    await userEvent.type(screen.getByLabelText("Person's name"), "Jane Doe");
    await userEvent.type(screen.getByLabelText("Consent recorded by"), "Me");
    const submit = screen.getByRole("button", { name: "Create influencer" });
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByLabelText("I have permission to use this person's likeness."));
    await userEvent.click(submit);
    expect(onSubmit.mock.calls[0]?.[0]).toMatchObject({
      character: { is_real_person: true },
      consent: { subjectName: "Jane Doe", grantedBy: "Me" },
    });
  });
});
