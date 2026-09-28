"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiError, type SystemResponse } from "@/lib/api/client";

export const SYSTEM_QUERY_KEY = ["system"] as const;

export function useSystem() {
  return useQuery<SystemResponse, ApiError>({
    queryKey: SYSTEM_QUERY_KEY,
    queryFn: api.system,
    refetchInterval: 10_000,
  });
}
