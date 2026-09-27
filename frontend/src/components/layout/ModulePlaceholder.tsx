import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { findNavItem } from "@/lib/navigation";

/** Shown for modules not yet implemented — never pretends a feature works. */
export function ModulePlaceholder({ href }: { href: string }) {
  const item = findNavItem(href);
  return (
    <>
      <PageHeader title={item.label} description={item.description} />
      <Card>
        <div className="flex items-center gap-3">
          <Badge tone="accent">Phase {item.phase}</Badge>
          <p className="text-sm text-muted">This module is not implemented yet.</p>
        </div>
      </Card>
    </>
  );
}
