import Link from "next/link";

import { EmptyState } from "@/components/ui/EmptyState";

export default function NotFound() {
  return (
    <EmptyState title="Page not found">
      <Link href="/" className="text-accent hover:underline">
        Back to dashboard
      </Link>
    </EmptyState>
  );
}
