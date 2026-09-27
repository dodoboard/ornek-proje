import clsx from "clsx";

import { percent } from "@/lib/utils/format";

interface MeterProps {
  label: string;
  value: number;
  max: number;
  caption: string;
}

export function Meter({ label, value, max, caption }: MeterProps) {
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
          className={clsx("h-full rounded-full", pct > 90 ? "bg-danger" : pct > 75 ? "bg-warning" : "bg-accent")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
