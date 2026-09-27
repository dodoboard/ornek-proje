"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { CharacterForm, type CharacterFormValue } from "@/components/character/CharacterForm";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { characterKeys, useCharacterList } from "@/hooks/useCharacters";
import { api, type ApiError, type CharacterRead } from "@/lib/api/client";
import { findNavItem } from "@/lib/navigation";

async function createCharacter({ character, consent }: CharacterFormValue): Promise<CharacterRead> {
  let consentId: string | null = null;
  if (consent) {
    const record = await api.consents.create({
      subject_type: "face",
      subject_name: consent.subjectName,
      granted_by: consent.grantedBy,
      confirm: true,
    });
    consentId = record.id;
  }
  return api.characters.create({ ...character, consent_id: consentId });
}

export default function InfluencersPage() {
  const item = findNavItem("/influencers");
  const router = useRouter();
  const queryClient = useQueryClient();
  const list = useCharacterList();
  const create = useMutation<CharacterRead, ApiError, CharacterFormValue>({
    mutationFn: createCharacter,
    onSuccess: (character) => {
      void queryClient.invalidateQueries({ queryKey: characterKeys.all });
      router.push(`/influencers/${character.id}`);
    },
  });

  return (
    <>
      <PageHeader title={item.label} description={item.description} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card title="New influencer">
          <CharacterForm pending={create.isPending} error={create.error?.message} onSubmit={(v) => create.mutate(v)} />
        </Card>
        <Card title="Influencers" action={list.data ? <Badge>{list.data.total}</Badge> : null}>
          {list.isPending && <p className="text-sm text-muted">Loading…</p>}
          {list.error && <p className="text-sm text-danger">{list.error.message}</p>}
          {list.data && list.data.items.length === 0 && (
            <EmptyState title="No influencers yet">Create one to start its Character Bible.</EmptyState>
          )}
          {list.data && list.data.items.length > 0 && (
            <ul className="divide-y divide-border">
              {list.data.items.map((c) => (
                <li key={c.id}>
                  <Link href={`/influencers/${c.id}`} className="flex items-center justify-between gap-3 py-3 hover:text-accent">
                    <span className="text-sm font-medium">{c.name}</span>
                    <span className="flex gap-1">
                      {c.is_real_person && <Badge tone="warning">real person</Badge>}
                      <Badge>
                        {c.adult_age} · {c.default_language}
                      </Badge>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
