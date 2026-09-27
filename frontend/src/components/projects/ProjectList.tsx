"use client";

import { Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { ProjectRead } from "@/lib/api/client";
import { projectTypeLabel } from "@/lib/projects";
import { formatDateTime } from "@/lib/utils/format";

interface ProjectListProps {
  projects: ProjectRead[];
  onDelete?: (project: ProjectRead) => void;
  deletingId?: string | null;
}

export function ProjectList({ projects, onDelete, deletingId }: ProjectListProps) {
  if (projects.length === 0) {
    return <EmptyState title="No projects yet">Create one to get started.</EmptyState>;
  }
  return (
    <ul className="divide-y divide-border">
      {projects.map((project) => (
        <li key={project.id} className="flex items-center justify-between gap-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{project.name}</p>
            <p className="text-xs text-muted">
              {project.settings.platform} · {project.settings.aspect_ratio} · {project.settings.duration_s}s · updated{" "}
              {formatDateTime(project.updated_at)}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge tone="accent">{projectTypeLabel(project.type)}</Badge>
            {onDelete && (
              <Button
                variant="danger"
                aria-label={`Delete ${project.name}`}
                disabled={deletingId === project.id}
                onClick={() => onDelete(project)}
              >
                <Trash2 className="size-4" aria-hidden />
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
