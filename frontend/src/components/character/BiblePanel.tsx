"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { CharacterBible, CharacterBibleUpdate } from "@/lib/api/client";
import { parseTraits } from "@/lib/characters";
import { formatDateTime } from "@/lib/utils/format";

function TraitArea({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const id = label.replace(/\W+/g, "-").toLowerCase();
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted">
        {label}
      </label>
      <textarea
        id={id}
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm outline-none focus:border-accent"
      />
    </div>
  );
}

export function BiblePanel({
  bible,
  onSave,
  pending,
  error,
}: {
  bible: CharacterBible;
  onSave: (patch: CharacterBibleUpdate) => void;
  pending: boolean;
  error?: string | null;
}) {
  const [immutable, setImmutable] = useState(bible.immutable_traits.join("\n"));
  const [mutable, setMutable] = useState(bible.mutable_traits.join("\n"));
  const [houseStyle, setHouseStyle] = useState(bible.prompt_template);
  const history = [...bible.seed_history].reverse().slice(0, 12);

  return (
    <Card title="Character Bible">
      <p className="mb-1 text-xs font-medium text-muted">Identity used in every prompt</p>
      <p className="mb-4 rounded-md bg-surface-raised p-3 text-sm">{bible.identity}</p>
      <div className="space-y-3">
        <TraitArea label="Immutable traits (never change)" value={immutable} onChange={setImmutable} />
        <TraitArea label="Mutable traits (may vary by scene)" value={mutable} onChange={setMutable} />
        <TraitArea label="House style (appended to every prompt)" value={houseStyle} onChange={setHouseStyle} />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
      <Button
        className="mt-3"
        disabled={pending}
        onClick={() =>
          onSave({
            immutable_traits: parseTraits(immutable),
            mutable_traits: parseTraits(mutable),
            prompt_template: houseStyle.trim(),
          })
        }
      >
        Save bible
      </Button>
      <p className="mt-4 text-xs text-muted">
        Consistency comes from the reference images (canonical + views) sent with every prompt. Seeds below are kept for
        reproducibility only.
      </p>
      {history.length > 0 && (
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-muted">
            <tr>
              <th className="py-1 font-medium">Step</th>
              <th className="py-1 font-medium">Seed</th>
              <th className="py-1 font-medium">When</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={`${h.asset_id}-${h.seed}`} className="border-t border-border">
                <td className="py-1">{h.purpose.replace("_", " ")}</td>
                <td className="py-1 tabular-nums">{h.seed}</td>
                <td className="py-1">{formatDateTime(h.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
