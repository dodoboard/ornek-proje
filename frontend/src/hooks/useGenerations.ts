"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiError, type GenerationRead, type Page } from "@/lib/api/client";

export const GENERATIONS_KEY = ["generations"] as const;

export function useGenerations(params: { kind?: string; limit?: number } = {}) {
  return useQuery<Page<GenerationRead>, ApiError>({
    queryKey: [...GENERATIONS_KEY, params],
    queryFn: () => api.generations.list(params),
  });
}
