import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Sidebar } from "./Sidebar";

vi.mock("next/navigation", () => ({ usePathname: () => "/product-ads" }));

describe("Sidebar", () => {
  it("renders every module link and marks the active one", () => {
    render(<Sidebar />);
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(nav.querySelectorAll("a")).toHaveLength(10);
    expect(screen.getByRole("link", { name: "Product Ads" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });
});
