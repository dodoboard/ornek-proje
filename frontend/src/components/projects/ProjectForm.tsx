"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import type { ProjectCreate, ProjectSettings, ProjectType } from "@/lib/api/client";
import { ASPECT_RATIOS, DURATIONS, LANGUAGES, PLATFORMS, PROJECT_TYPES, TONES } from "@/lib/projects";

type Settings = Required<Pick<ProjectSettings, "platform" | "aspect_ratio" | "duration_s" | "tone" | "language">>;

const DEFAULT_SETTINGS: Settings = {
  platform: "instagram",
  aspect_ratio: "9:16",
  duration_s: 30,
  tone: "professional",
  language: "tr",
};

interface ProjectFormProps {
  onSubmit: (payload: ProjectCreate) => void;
  pending?: boolean;
  error?: string | null;
}

export function ProjectForm({ onSubmit, pending = false, error }: ProjectFormProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<ProjectType>("product_ad");
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    onSubmit({ name: trimmed, type, settings });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" aria-label="New project">
      <div className="grid gap-4 md:grid-cols-2">
        <TextField
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
          required
          placeholder="Summer perfume launch"
        />
        <SelectField
          label="Type"
          options={PROJECT_TYPES}
          value={type}
          onChange={(e) => setType(e.target.value as ProjectType)}
        />
        <SelectField
          label="Platform"
          options={PLATFORMS}
          value={settings.platform}
          onChange={(e) => update("platform", e.target.value as Settings["platform"])}
        />
        <SelectField
          label="Format"
          options={ASPECT_RATIOS}
          value={settings.aspect_ratio}
          onChange={(e) => update("aspect_ratio", e.target.value as Settings["aspect_ratio"])}
        />
        <SelectField
          label="Duration"
          options={DURATIONS}
          value={settings.duration_s}
          onChange={(e) => update("duration_s", Number(e.target.value) as Settings["duration_s"])}
        />
        <SelectField
          label="Tone"
          options={TONES}
          value={settings.tone}
          onChange={(e) => update("tone", e.target.value as Settings["tone"])}
        />
        <SelectField
          label="Language"
          options={LANGUAGES}
          value={settings.language}
          onChange={(e) => update("language", e.target.value)}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" disabled={pending || !name.trim()}>
        {pending ? "Creating…" : "Create project"}
      </Button>
    </form>
  );
}
