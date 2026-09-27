"use client";

import { Card } from "@/components/ui/Card";

export default function ErrorBoundary({ reset }: { error: Error; reset: () => void }) {
  return (
    <Card title="Something went wrong">
      <p className="text-sm text-muted">This page failed to render. Details are in the browser console.</p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
      >
        Try again
      </button>
    </Card>
  );
}
