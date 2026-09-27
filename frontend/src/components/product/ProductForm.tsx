"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import type { ProductCreate } from "@/lib/api/client";

/** Product facts are entered by the user and stored as verified data; nothing here is generated. */
export function ProductForm({
  onSubmit,
  pending,
  error,
}: {
  onSubmit: (body: ProductCreate) => void;
  pending: boolean;
  error?: string | null;
}) {
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [description, setDescription] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    onSubmit({ name: name.trim(), brand: brand.trim(), description: description.trim() });
  }

  return (
    <form onSubmit={submit} className="space-y-3" aria-label="New product">
      <TextField label="Product name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
      <TextField label="Brand" value={brand} onChange={(e) => setBrand(e.target.value)} maxLength={200} />
      <TextField
        label="Description (verified facts only)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        maxLength={2000}
      />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" disabled={pending || !name.trim()}>
        {pending ? "Creating…" : "Create product"}
      </Button>
    </form>
  );
}
