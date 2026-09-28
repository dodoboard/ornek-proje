"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import type { CharacterCreate } from "@/lib/api/client";
import { LANGUAGES } from "@/lib/projects";

export interface CharacterFormValue {
  character: CharacterCreate;
  consent: { subjectName: string; grantedBy: string } | null;
}

const TEXT_FIELDS: { key: keyof CharacterCreate; label: string; placeholder: string }[] = [
  { key: "presentation", label: "Presentation", placeholder: "woman / man / non-binary person" },
  { key: "face_description", label: "Face", placeholder: "oval face, light freckles" },
  { key: "hair", label: "Hair", placeholder: "shoulder-length wavy dark brown" },
  { key: "eye_color", label: "Eyes", placeholder: "hazel" },
  { key: "skin_appearance", label: "Skin", placeholder: "warm olive skin" },
  { key: "body_description", label: "Body", placeholder: "athletic build, tall" },
  { key: "style", label: "Style", placeholder: "minimal chic, earthy tones" },
  { key: "clothing_preferences", label: "Clothing", placeholder: "linen shirts, tailored trousers" },
  { key: "personality", label: "Personality", placeholder: "warm, witty, calm" },
  { key: "speaking_style", label: "Speaking style", placeholder: "friendly, short sentences" },
  { key: "brand_tone", label: "Brand tone", placeholder: "premium but approachable" },
];

export function CharacterForm({
  onSubmit,
  pending,
  error,
}: {
  onSubmit: (value: CharacterFormValue) => void;
  pending: boolean;
  error?: string | null;
}) {
  const [name, setName] = useState("");
  const [age, setAge] = useState("25");
  const [language, setLanguage] = useState("tr");
  const [text, setText] = useState<Record<string, string>>({});
  const [realPerson, setRealPerson] = useState(false);
  const [subjectName, setSubjectName] = useState("");
  const [grantedBy, setGrantedBy] = useState("");
  const [consentChecked, setConsentChecked] = useState(false);

  const ageValue = Number(age);
  const ageValid = Number.isInteger(ageValue) && ageValue >= 18 && ageValue <= 120;
  const consentValid = !realPerson || (consentChecked && subjectName.trim() !== "" && grantedBy.trim() !== "");
  const valid = name.trim() !== "" && ageValid && consentValid;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid) return;
    const fields = Object.fromEntries(Object.entries(text).filter(([, v]) => v.trim() !== ""));
    onSubmit({
      character: {
        name: name.trim(),
        adult_age: ageValue,
        default_language: language,
        is_real_person: realPerson,
        ...fields,
      },
      consent: realPerson ? { subjectName: subjectName.trim(), grantedBy: grantedBy.trim() } : null,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4" aria-label="New influencer">
      <div className="grid gap-4 md:grid-cols-3">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required />
        <TextField
          label="Age (18+)"
          type="number"
          min={18}
          max={120}
          value={age}
          onChange={(e) => setAge(e.target.value)}
          aria-invalid={!ageValid}
        />
        <SelectField label="Language" options={LANGUAGES} value={language} onChange={(e) => setLanguage(e.target.value)} />
      </div>
      {!ageValid && (
        <p role="alert" className="text-xs text-danger">
          Characters must be adults (18–120).
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {TEXT_FIELDS.map(({ key, label, placeholder }) => (
          <TextField
            key={key}
            label={label}
            placeholder={placeholder}
            value={text[key] ?? ""}
            onChange={(e) => setText((t) => ({ ...t, [key]: e.target.value }))}
          />
        ))}
      </div>

      <fieldset className="space-y-3 rounded-md border border-border p-3">
        <legend className="px-1 text-xs font-medium text-muted">Real person</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={realPerson} onChange={(e) => setRealPerson(e.target.checked)} />
          This character is based on a real person&apos;s likeness
        </label>
        {realPerson && (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <TextField label="Person's name" value={subjectName} onChange={(e) => setSubjectName(e.target.value)} />
              <TextField label="Consent recorded by" value={grantedBy} onChange={(e) => setGrantedBy(e.target.value)} />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={(e) => setConsentChecked(e.target.checked)}
                className="mt-1"
              />
              I have permission to use this person&apos;s likeness.
            </label>
          </>
        )}
      </fieldset>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" disabled={!valid || pending}>
        {pending ? "Creating…" : "Create influencer"}
      </Button>
    </form>
  );
}
