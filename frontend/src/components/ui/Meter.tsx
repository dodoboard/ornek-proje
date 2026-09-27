import clsx from "clsx";

import { percent } from "@/lib/utils/format";

interface MeterProps {
  label: string;
  value: number;
  max: number;
  caption: string;
  /** "usage" turns amber/red near capacity; "progress" stays on the accent color. */
  variant?: "usage" | "progress";
}

function barColor(pct: number, variant: MeterProps["variant"]): string {
  if (variant === "progress") return "bg-accent";
  return pct > 90 ? "bg-danger" : pct > 75 ? "bg-warning" : "bg-accent";
}

export function Meter({ label, value, max, caption, variant = "usage" }: MeterProps) {
  const pct = percent(value, max);
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="tabular-nums">{caption}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        className="h-1.5 overflow-hidden rounded-full bg-surface-raised"
      >
        <div
          className={clsx("h-full rounded-full transition-[width] duration-300", barColor(pct, variant))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
