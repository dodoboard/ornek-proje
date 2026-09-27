import { describe, expect, it } from "vitest";

import { NAV_ITEMS, findNavItem, isActivePath } from "./navigation";

describe("isActivePath", () => {
  it("matches the dashboard only on the root path", () => {
    expect(isActivePath("/", "/")).toBe(true);
    expect(isActivePath("/projects", "/")).toBe(false);
  });

  it("matches nested routes but not prefixes of other words", () => {
    expect(isActivePath("/projects/PRJ_1", "/projects")).toBe(true);
    expect(isActivePath("/projects-archive", "/projects")).toBe(false);
  });
});

describe("NAV_ITEMS", () => {
  it("has unique hrefs and contains every required module", () => {
    const hrefs = NAV_ITEMS.map((item) => item.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
    expect(NAV_ITEMS.map((item) => item.label)).toEqual([
      "Dashboard",
      "Influencers",
      "Image Studio",
      "Video Studio",
      "Product Ads",
      "Real Estate",
      "Storyboard",
      "Projects",
      "Models",
      "Settings",
    ]);
  });

  it("throws for unknown routes", () => {
    expect(() => findNavItem("/nope")).toThrow();
  });
});
