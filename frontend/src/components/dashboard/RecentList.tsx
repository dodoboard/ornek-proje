"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import type { ApiError, Page } from "@/lib/api/client";

export interface RecentItem {
  id: string;
  title: string;
  subtitle?: string;
}

interface RecentListProps<T> {
  title: string;
  queryKey: readonly unknown[];
  fetchPage: () => Promise<Page<T>>;
  toItem: (item: T) => RecentItem;
  href: string;
  emptyText: string;
}

export function RecentList<T>({ title, queryKey, fetchPage, toItem, href, emptyText }: RecentListProps<T>) {
  const { data, error, isPending } = useQuery<Page<T>, ApiError>({ queryKey, queryFn: fetchPage });

  return (
    <Card
      title={title}
      action={
        <Link href={href} className="text-xs text-accent hover:underline">
          View all
        </Link>
      }
    >
      {isPending && <p className="text-sm text-muted">Loading…</p>}
      {error && <Badge tone="danger">{error.code}</Badge>}
      {data && data.items.length === 0 && <EmptyState title="Nothing here yet">{emptyText}</EmptyState>}
      {data && data.items.length > 0 && (
        <ul className="space-y-2">
          {data.items.map((raw) => {
            const item = toItem(raw);
            return (
              <li key={item.id} className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate">{item.title}</span>
                {item.subtitle && <span className="shrink-0 text-xs text-muted">{item.subtitle}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
