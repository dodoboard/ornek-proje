"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField } from "@/components/ui/Field";
import type { ProviderInfo, ScriptGenerateRequest } from "@/lib/api/client";

export function ScriptGenerateForm({
  models,
  defaultModelKey,
  busy,
  onGenerate,
}: {
  models: ProviderInfo[];
  defaultModelKey: string | null;
  busy: boolean;
  onGenerate: (body: ScriptGenerateRequest) => void;
}) {
  const [modelKey, setModelKey] = useState(defaultModelKey ?? models[0]?.key ?? "");
  const [brief, setBrief] = useState("");
  const model = models.find((m) => m.key === modelKey) ?? models[0];

  return (
    <div className="space-y-3">
      <label className="block text-xs font-medium text-muted">
        Notes for the script (optional, treated as verified input)
        <textarea
          className="mt-1 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm outline-none focus:border-accent"
          rows={3}
          maxLength={2000}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="Focus on the morning routine; friendly, not salesy."
        />
      </label>
      {models.length > 0 ? (
        <SelectField
          label="Local LLM"
          options={models.map((m) => ({ value: m.key, label: m.maturity === "dev_only" ? `${m.key} (dev placeholder)` : m.key }))}
          value={model?.key ?? ""}
          onChange={(e) => setModelKey(e.target.value)}
        />
      ) : (
        <p className="text-sm text-muted">
          No local LLM is running. Start Ollama (<code>ollama pull qwen3:8b</code>) or llama-server — or use the
          template, which only uses your verified facts.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={busy || !model}
          onClick={() => model && onGenerate({ brief: brief.trim(), llm_model_key: model.key, template_only: false })}
        >
          Write script with LLM
        </Button>
        <Button variant="ghost" disabled={busy} onClick={() => onGenerate({ brief: brief.trim(), template_only: true })}>
          Use template
        </Button>
      </div>
    </div>
  );
}
