"use client";

import clsx from "clsx";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS, isActivePath } from "@/lib/navigation";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 px-5 py-5">
        <Sparkles className="size-5 text-accent" aria-hidden />
        <span className="text-sm font-semibold tracking-tight">AI Influencer Studio</span>
      </div>
      <nav aria-label="Main" className="flex-1 space-y-0.5 px-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = isActivePath(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active ? "bg-accent-soft text-fg" : "text-muted hover:bg-surface-raised hover:text-fg",
              )}
            >
              <Icon className={clsx("size-4", active && "text-accent")} aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
