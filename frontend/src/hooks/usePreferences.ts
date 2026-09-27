"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiError, type ModelsResponse, type Preferences, type PreferencesUpdate } from "@/lib/api/client";

export const PREFERENCES_KEY = ["settings"] as const;
export const MODELS_KEY = ["models"] as const;

export function usePreferences() {
  return useQuery<Preferences, ApiError>({ queryKey: PREFERENCES_KEY, queryFn: api.settings.get });
}

export function useModels() {
  return useQuery<ModelsResponse, ApiError>({ queryKey: MODELS_KEY, queryFn: api.models.list });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation<Preferences, ApiError, PreferencesUpdate>({
    mutationFn: api.settings.update,
    onSuccess: (data) => {
      queryClient.setQueryData(PREFERENCES_KEY, data);
      void queryClient.invalidateQueries({ queryKey: MODELS_KEY });
      void queryClient.invalidateQueries({ queryKey: ["system"] });
    },
  });
}
