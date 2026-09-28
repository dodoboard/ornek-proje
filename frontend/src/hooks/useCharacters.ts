"use client";

import { useQuery } from "@tanstack/react-query";

import {
  api,
  type ApiError,
  type CharacterBible,
  type CharacterRead,
  type CharacterSummary,
  type GenerationRead,
  type Page,
} from "@/lib/api/client";

export const characterKeys = {
  all: ["characters"] as const,
  detail: (id: string) => ["characters", id] as const,
  bible: (id: string) => ["characters", id, "bible"] as const,
  generations: (id: string) => ["generations", { character_id: id }] as const,
};

export function useCharacterList() {
  return useQuery<Page<CharacterSummary>, ApiError>({
    queryKey: characterKeys.all,
    queryFn: () => api.characters.list({ limit: 100 }),
  });
}

export function useCharacter(id: string) {
  return useQuery<CharacterRead, ApiError>({ queryKey: characterKeys.detail(id), queryFn: () => api.characters.get(id) });
}

export function useCharacterBible(id: string) {
  return useQuery<CharacterBible, ApiError>({ queryKey: characterKeys.bible(id), queryFn: () => api.characters.bible(id) });
}

export function useCharacterGenerations(id: string) {
  return useQuery<Page<GenerationRead>, ApiError>({
    queryKey: characterKeys.generations(id),
    queryFn: () => api.generations.list({ character_id: id, limit: 100 }),
  });
}
