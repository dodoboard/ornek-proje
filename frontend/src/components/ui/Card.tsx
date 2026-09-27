import clsx from "clsx";
import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Card({ title, action, className, children }: CardProps) {
  return (
    <section className={clsx("rounded-lg border border-border bg-surface p-5", className)}>
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-medium text-muted">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
