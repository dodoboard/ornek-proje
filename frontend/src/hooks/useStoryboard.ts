"use client";

import { useQuery } from "@tanstack/react-query";

import { api, ApiError, type ScriptRead, type StoryboardRead } from "@/lib/api/client";

export const storyboardKeys = {
  latest: (projectId: string) => ["storyboard", projectId] as const,
  scripts: (projectId: string) => ["scripts", projectId] as const,
};

/** Latest storyboard of a project, or null when none has been generated yet. */
export function useLatestStoryboard(projectId: string | null) {
  return useQuery<StoryboardRead | null, ApiError>({
    queryKey: storyboardKeys.latest(projectId ?? ""),
    enabled: projectId !== null,
    queryFn: async () => {
      try {
        return await api.storyboards.latest(projectId!);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
  });
}

export function useScripts(projectId: string | null) {
  return useQuery<ScriptRead[], ApiError>({
    queryKey: storyboardKeys.scripts(projectId ?? ""),
    enabled: projectId !== null,
    queryFn: () => api.storyboards.scripts(projectId!),
  });
}
