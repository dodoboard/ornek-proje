"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";

/** Text input with an explicit Save button; empty value clears the override. */
export function PathField({
  label,
  current,
  placeholder,
  disabled,
  onSave,
}: {
  label: string;
  current: string | null | undefined;
  placeholder?: string;
  disabled?: boolean;
  onSave: (value: string) => void;
}) {
  const [value, setValue] = useState(current ?? "");
  const dirty = value.trim() !== (current ?? "");
  return (
    <div className="flex items-end gap-2">
      <div className="min-w-0 flex-1">
        <TextField label={label} value={value} placeholder={placeholder} onChange={(e) => setValue(e.target.value)} />
      </div>
      <Button variant="ghost" disabled={!dirty || disabled} onClick={() => onSave(value.trim())}>
        Save
      </Button>
    </div>
  );
}
