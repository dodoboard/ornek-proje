"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ProductForm } from "@/components/product/ProductForm";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { productKeys, useProductList } from "@/hooks/useProducts";
import { api, type ApiError, type ProductCreate, type ProductRead } from "@/lib/api/client";
import { findNavItem } from "@/lib/navigation";

export default function ProductAdsPage() {
  const item = findNavItem("/product-ads");
  const router = useRouter();
  const queryClient = useQueryClient();
  const list = useProductList();
  const create = useMutation<ProductRead, ApiError, ProductCreate>({
    mutationFn: api.products.create,
    onSuccess: (product) => {
      void queryClient.invalidateQueries({ queryKey: productKeys.all });
      router.push(`/product-ads/${product.id}`);
    },
  });

  return (
    <>
      <PageHeader
        title="Product Studio"
        description="Cut out a product photo and place its original pixels into new scenes. Logos and labels are never re-drawn by AI."
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card title="New product">
          <ProductForm pending={create.isPending} error={create.error?.message} onSubmit={(b) => create.mutate(b)} />
        </Card>
        <Card title="Products" action={list.data ? <Badge>{list.data.total}</Badge> : null}>
          {list.isPending && <p className="text-sm text-muted">Loading…</p>}
          {list.error && <p className="text-sm text-danger">{list.error.message}</p>}
          {list.data && list.data.items.length === 0 && (
            <EmptyState title="No products yet">Create one, then upload a product photo.</EmptyState>
          )}
          {list.data && list.data.items.length > 0 && (
            <ul className="divide-y divide-border">
              {list.data.items.map((p) => (
                <li key={p.id}>
                  <Link href={`/product-ads/${p.id}`} className="flex items-center justify-between gap-3 py-3 hover:text-accent">
                    <span className="text-sm font-medium">{p.name}</span>
                    {p.brand && <Badge>{p.brand}</Badge>}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <p className="mt-4 text-xs text-muted">{item.description}</p>
    </>
  );
}
