"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiError, type GenerationRead, type Page, type ProductRead, type ProductSummary } from "@/lib/api/client";

export const productKeys = {
  all: ["products"] as const,
  detail: (id: string) => ["products", id] as const,
  scenes: (id: string) => ["generations", { product_id: id }] as const,
};

export function useProductList() {
  return useQuery<Page<ProductSummary>, ApiError>({
    queryKey: productKeys.all,
    queryFn: () => api.products.list({ limit: 100 }),
  });
}

export function useProduct(id: string) {
  return useQuery<ProductRead, ApiError>({ queryKey: productKeys.detail(id), queryFn: () => api.products.get(id) });
}

export function useProductScenes(id: string) {
  return useQuery<Page<GenerationRead>, ApiError>({
    queryKey: productKeys.scenes(id),
    queryFn: () => api.generations.list({ product_id: id, kind: "product_scene", limit: 48 }),
  });
}
