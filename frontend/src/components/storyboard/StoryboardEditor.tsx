"use client";

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useState } from "react";

import type { ShotRead, ShotUpdate } from "@/lib/api/client";
import { move } from "@/lib/storyboard";

import { ShotCard } from "./ShotCard";

/** Sortable shot list. `order` is kept locally so a drag shows immediately; `onReorder` persists it. */
export function StoryboardEditor({
  shots,
  pending,
  onReorder,
  onSave,
  onDelete,
}: {
  shots: ShotRead[];
  pending: boolean;
  onReorder: (shotIds: string[]) => void;
  onSave: (shotId: string, patch: ShotUpdate) => void;
  onDelete: (shotId: string) => void;
}) {
  const [local, setLocal] = useState<{ source: ShotRead[]; ids: string[] } | null>(null);
  // Server data wins as soon as it changes (e.g. after a save or reload).
  const ids = local && local.source === shots ? local.ids : shots.map((s) => s.id);
  const byId = new Map(shots.map((s) => [s.id, s]));
  const ordered = ids.map((id) => byId.get(id)).filter((s): s is ShotRead => s !== undefined);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function commit(next: string[]) {
    setLocal({ source: shots, ids: next });
    onReorder(next);
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) return;
    commit(move(ids, ids.indexOf(String(active.id)), ids.indexOf(String(over.id))));
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={ids} strategy={verticalListSortingStrategy}>
        <ol className="space-y-2" aria-label="Shots">
          {ordered.map((shot, index) => (
            <ShotCard
              key={shot.id}
              shot={shot}
              index={index}
              count={ordered.length}
              pending={pending}
              onMove={(from, to) => commit(move(ids, from, to))}
              onSave={(patch) => onSave(shot.id, patch)}
              onDelete={() => onDelete(shot.id)}
            />
          ))}
        </ol>
      </SortableContext>
    </DndContext>
  );
}
