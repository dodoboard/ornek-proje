"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiError, type Page, type ProjectCreate, type ProjectRead } from "@/lib/api/client";

export const PROJECTS_QUERY_KEY = ["projects"] as const;

export function useProjects(limit = 50) {
  return useQuery<Page<ProjectRead>, ApiError>({
    queryKey: [...PROJECTS_QUERY_KEY, { limit }],
    queryFn: () => api.projects.list({ limit }),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation<ProjectRead, ApiError, ProjectCreate>({
    mutationFn: api.projects.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY }),
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: api.projects.remove,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY }),
  });
}
