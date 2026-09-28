"use client";

import { ProjectForm } from "@/components/projects/ProjectForm";
import { ProjectList } from "@/components/projects/ProjectList";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useCreateProject, useDeleteProject, useProjects } from "@/hooks/useProjects";
import { findNavItem } from "@/lib/navigation";

export default function ProjectsPage() {
  const item = findNavItem("/projects");
  const projects = useProjects();
  const create = useCreateProject();
  const remove = useDeleteProject();

  return (
    <>
      <PageHeader title={item.label} description={item.description} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card title="New project">
          <ProjectForm
            key={create.data?.id ?? "new"}
            pending={create.isPending}
            error={create.error?.message}
            onSubmit={(payload) => create.mutate(payload)}
          />
        </Card>
        <Card
          title="All projects"
          action={projects.data && <Badge>{projects.data.total}</Badge>}
        >
          {projects.isPending && <p className="text-sm text-muted">Loading…</p>}
          {projects.error && (
            <p role="alert" className="text-sm text-danger">
              {projects.error.message}
            </p>
          )}
          {remove.error && (
            <p role="alert" className="mb-2 text-sm text-danger">
              {remove.error.message}
            </p>
          )}
          {projects.data && (
            <ProjectList
              projects={projects.data.items}
              deletingId={remove.isPending ? remove.variables : null}
              onDelete={(project) => {
                if (window.confirm(`Delete project "${project.name}"?`)) remove.mutate(project.id);
              }}
            />
          )}
        </Card>
      </div>
    </>
  );
}
