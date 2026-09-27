import type { LucideIcon } from "lucide-react";
import {
  Building2,
  Clapperboard,
  Cpu,
  FolderKanban,
  Image,
  LayoutDashboard,
  LayoutList,
  Settings,
  ShoppingBag,
  Users,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Roadmap phase in which the module becomes functional. */
  phase: number;
  description: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    phase: 1,
    description: "System status, recent work and active jobs.",
  },
  {
    href: "/influencers",
    label: "Influencers",
    icon: Users,
    phase: 6,
    description: "Create AI influencers and maintain their Character Bible.",
  },
  {
    href: "/image-studio",
    label: "Image Studio",
    icon: Image,
    phase: 7,
    description: "FLUX.2 text-to-image, reference-based generation and inpainting.",
  },
  {
    href: "/video-studio",
    label: "Video Studio",
    icon: Clapperboard,
    phase: 11,
    description: "Image-to-video clips with a local video model.",
  },
  {
    href: "/product-ads",
    label: "Product Ads",
    icon: ShoppingBag,
    phase: 8,
    description: "Product scenes that preserve original logos and labels, and ad campaigns.",
  },
  {
    href: "/real-estate",
    label: "Real Estate",
    icon: Building2,
    phase: 17,
    description: "Property and land videos built only from verified listing data.",
  },
  {
    href: "/storyboard",
    label: "Storyboard",
    icon: LayoutList,
    phase: 9,
    description: "Script-driven shot lists you can edit and reorder before rendering.",
  },
  {
    href: "/projects",
    label: "Projects",
    icon: FolderKanban,
    phase: 2,
    description: "Every piece of work, its assets and final outputs.",
  },
  {
    href: "/models",
    label: "Models",
    icon: Cpu,
    phase: 4,
    description: "Installed providers, model paths and capabilities.",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    phase: 4,
    description: "Storage, performance profile, privacy and FFmpeg.",
  },
];

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function findNavItem(href: string): NavItem {
  const item = NAV_ITEMS.find((candidate) => candidate.href === href);
  if (!item) throw new Error(`Unknown navigation item: ${href}`);
  return item;
}
