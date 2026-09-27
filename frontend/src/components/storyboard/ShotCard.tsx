"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDown, ArrowUp, GripVertical, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import type { ShotRead, ShotUpdate } from "@/lib/api/client";
import { CAMERAS, DISCLOSURES, METHODS, MOTIONS, SHOT_TYPES, labelOf, options } from "@/lib/storyboard";

const TEXTAREA =
  "w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm outline-none focus:border-accent";

function ShotEditor({ shot, onSave, onCancel, pending }: {
  shot: ShotRead;
  onSave: (patch: ShotUpdate) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [draft, setDraft] = useState({
    type: shot.type,
    duration_s: String(shot.duration_s),
    dialogue: shot.dialogue,
    on_screen_text: shot.on_screen_text,
    description: shot.description,
    visual_prompt: shot.visual_prompt,
    camera: shot.camera,
    camera_motion: shot.camera_motion,
    generation_method: shot.generation_method,
  });
  const duration = Number(draft.duration_s);
  const invalid = !(duration >= 0.5 && duration <= 60);
  const set = (key: keyof typeof draft) => (e: { target: { value: string } }) =>
    setDraft((d) => ({ ...d, [key]: e.target.value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid) return;
    onSave({ ...draft, duration_s: duration } as ShotUpdate);
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 border-t border-border pt-3" aria-label={`Edit shot ${shot.position + 1}`}>
      <div className="grid gap-3 md:grid-cols-3">
        <SelectField label="Shot type" options={options(SHOT_TYPES)} value={draft.type} onChange={set("type")} />
        <TextField label="Duration (s)" inputMode="decimal" value={draft.duration_s} onChange={set("duration_s")} aria-invalid={invalid} />
        <SelectField label="Made with" options={options(METHODS)} value={draft.generation_method} onChange={set("generation_method")} />
      </div>
      <label className="block text-xs font-medium text-muted">
        Dialogue
        <textarea className={TEXTAREA} rows={2} maxLength={500} value={draft.dialogue} onChange={set("dialogue")} />
      </label>
      <TextField label="On-screen text" maxLength={200} value={draft.on_screen_text} onChange={set("on_screen_text")} />
      <label className="block text-xs font-medium text-muted">
        Visual prompt (for the image/video model)
        <textarea className={TEXTAREA} rows={2} maxLength={500} value={draft.visual_prompt} onChange={set("visual_prompt")} />
      </label>
      <div className="grid gap-3 md:grid-cols-2">
        <SelectField label="Camera" options={options(CAMERAS)} value={draft.camera} onChange={set("camera")} />
        <SelectField label="Camera motion" options={options(MOTIONS)} value={draft.camera_motion} onChange={set("camera_motion")} />
      </div>
      <p className="text-xs text-muted">Your edits are used as written; check any facts you type yourself.</p>
      <div className="flex gap-2">
        <Button type="submit" disabled={pending || invalid}>
          Save shot
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function ShotCard({
  shot,
  index,
  count,
  onMove,
  onSave,
  onDelete,
  pending,
}: {
  shot: ShotRead;
  index: number;
  count: number;
  onMove: (from: number, to: number) => void;
  onSave: (patch: ShotUpdate) => void;
  onDelete: () => void;
  pending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: shot.id });
  const style = { transform: CSS.Transform.toString(transform), transition };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="rounded-md border border-border bg-surface-raised p-3 data-[dragging=true]:opacity-60"
      data-dragging={isDragging}
      aria-label={`Shot ${index + 1}: ${labelOf(SHOT_TYPES, shot.type)}`}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          className="mt-0.5 cursor-grab text-muted hover:text-fg"
          aria-label={`Drag shot ${index + 1}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical className="size-4" aria-hidden />
        </button>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-medium">
              {index + 1}. {labelOf(SHOT_TYPES, shot.type)}
            </span>
            <Badge>{shot.duration_s}s</Badge>
            <Badge tone={shot.generation_method === "real_footage" ? "success" : "accent"}>
              {labelOf(METHODS, shot.generation_method)}
            </Badge>
            <Badge tone="neutral">{labelOf(DISCLOSURES, shot.disclosure_label)}</Badge>
            {shot.edited && <Badge tone="warning">edited</Badge>}
          </div>
          {shot.dialogue && <p className="text-sm">“{shot.dialogue}”</p>}
          {shot.on_screen_text && <p className="text-xs text-accent">On screen: {shot.on_screen_text}</p>}
          {shot.description && <p className="text-xs text-muted">{shot.description}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" aria-label={`Move shot ${index + 1} up`} disabled={index === 0 || pending}
            onClick={() => onMove(index, index - 1)} className="p-1 text-muted hover:text-fg disabled:opacity-30">
            <ArrowUp className="size-4" aria-hidden />
          </button>
          <button type="button" aria-label={`Move shot ${index + 1} down`} disabled={index === count - 1 || pending}
            onClick={() => onMove(index, index + 1)} className="p-1 text-muted hover:text-fg disabled:opacity-30">
            <ArrowDown className="size-4" aria-hidden />
          </button>
          <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => setEditing((v) => !v)}>
            {editing ? "Close" : "Edit"}
          </Button>
          <button type="button" aria-label={`Delete shot ${index + 1}`} disabled={count <= 1 || pending}
            onClick={onDelete} className="p-1 text-muted hover:text-danger disabled:opacity-30">
            <Trash2 className="size-4" aria-hidden />
          </button>
        </div>
      </div>
      {editing && (
        <ShotEditor
          shot={shot}
          pending={pending}
          onCancel={() => setEditing(false)}
          onSave={(patch) => {
            onSave(patch);
            setEditing(false);
          }}
        />
      )}
    </li>
  );
}
