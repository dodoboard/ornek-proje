"use client";

import { RecentList } from "@/components/dashboard/RecentList";
import { ActiveJobs } from "@/components/jobs/ActiveJobs";
import { api } from "@/lib/api/client";
import { projectTypeLabel } from "@/lib/projects";

const RECENT = { limit: 5 };

export function DashboardLists() {
  return (
    <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <RecentList
        title="Recent Projects"
        href="/projects"
        queryKey={["projects", RECENT]}
        fetchPage={() => api.projects.list(RECENT)}
        toItem={(p) => ({ id: p.id, title: p.name, subtitle: projectTypeLabel(p.type) })}
        emptyText="Create a project to get started."
      />
      <ActiveJobs />
      <RecentList
        title="Recent Generations"
        href="/image-studio"
        queryKey={["generations", RECENT]}
        fetchPage={() => api.generations.list(RECENT)}
        toItem={(g) => ({
          id: g.id,
          title: String(g.params?.prompt ?? g.kind),
          subtitle: `${g.model_key} · ${g.output_asset_ids?.length ?? 0} img`,
        })}
        emptyText="Generate an image in Image Studio."
      />
      <RecentList
        title="Influencers"
        href="/influencers"
        queryKey={["characters", RECENT]}
        fetchPage={() => api.characters.list(RECENT)}
        toItem={(c) => ({ id: c.id, title: c.name, subtitle: `${c.adult_age} · ${c.default_language}` })}
        emptyText="Character Studio arrives in Phase 6."
      />
      <RecentList
        title="Products"
        href="/product-ads"
        queryKey={["products", RECENT]}
        fetchPage={() => api.products.list(RECENT)}
        toItem={(p) => ({ id: p.id, title: p.name, subtitle: p.brand || undefined })}
        emptyText="Product Studio arrives in Phase 8."
      />
      <RecentList
        title="Properties"
        href="/real-estate"
        queryKey={["properties", RECENT]}
        fetchPage={() => api.properties.list(RECENT)}
        toItem={(p) => ({
          id: p.id,
          title: p.title,
          subtitle: p.facts_verified_at ? "verified" : "unverified",
        })}
        emptyText="Real Estate Studio arrives in Phase 17."
      />
    </div>
  );
}
