"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useMemo, useState } from "react";

import { useAuth } from "@/auth/clerk";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/mutator";
import type { SkillPackRead } from "@/api/generated/model";
import {
  getListSkillPacksApiV1SkillsPacksGetQueryKey,
  type listSkillPacksApiV1SkillsPacksGetResponse,
  useDeleteSkillPackApiV1SkillsPacksPackIdDelete,
  useListSkillPacksApiV1SkillsPacksGet,
  useSyncSkillPackApiV1SkillsPacksPackIdSyncPost,
} from "@/api/generated/skills/skills";
import { SkillPacksTable } from "@/components/skills/SkillPacksTable";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { buttonVariants } from "@/components/ui/button";
import { ConfirmActionDialog } from "@/components/ui/confirm-action-dialog";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { useUrlSorting } from "@/lib/use-url-sorting";

const PACKS_SORTABLE_COLUMNS = ["name", "source_url", "skill_count", "updated_at"];

export default function SkillsPacksPage() {
  const queryClient = useQueryClient();
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const [deleteTarget, setDeleteTarget] = useState<SkillPackRead | null>(null);
  const [syncingPackIds, setSyncingPackIds] = useState<Set<string>>(new Set());

  const { sorting, onSortingChange } = useUrlSorting({
    allowedColumnIds: PACKS_SORTABLE_COLUMNS,
    defaultSorting: [{ id: "name", desc: false }],
    paramPrefix: "skill_packs",
  });

  const packsQuery = useListSkillPacksApiV1SkillsPacksGet<
    listSkillPacksApiV1SkillsPacksGetResponse,
    ApiError
  >({
    query: {
      enabled: Boolean(isSignedIn && isAdmin),
      refetchOnMount: "always",
      refetchInterval: 15_000,
    },
  });

  const packsQueryKey = getListSkillPacksApiV1SkillsPacksGetQueryKey();

  const packs = useMemo<SkillPackRead[]>(
    () => (packsQuery.data?.status === 200 ? packsQuery.data.data : []),
    [packsQuery.data],
  );

  const deleteMutation =
    useDeleteSkillPackApiV1SkillsPacksPackIdDelete<ApiError>(
      {
        mutation: {
          onSuccess: async () => {
            setDeleteTarget(null);
            await queryClient.invalidateQueries({
              queryKey: packsQueryKey,
            });
          },
        },
      },
      queryClient,
    );
  const syncMutation =
    useSyncSkillPackApiV1SkillsPacksPackIdSyncPost<ApiError>(
      {
        mutation: {
          onSuccess: async () => {
            await queryClient.invalidateQueries({
              queryKey: packsQueryKey,
            });
          },
        },
      },
      queryClient,
    );

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate({ packId: deleteTarget.id });
  };

  return (
    <>
      <DashboardPageLayout
        signedOut={{
          message: "Sign in to manage skill packs.",
          forceRedirectUrl: "/skills/packs",
        }}
        title="Skill Packs"
        description={`${packs.length} pack${packs.length === 1 ? "" : "s"} configured.`}
        headerActions={
          isAdmin ? (
            <Link
              href="/skills/packs/new"
              className={buttonVariants({ variant: "primary", size: "md" })}
            >
              Add pack
            </Link>
          ) : null
        }
        isAdmin={isAdmin}
        adminOnlyMessage="Only organization owners and admins can manage skill packs."
        stickyHeader
      >
        <div className="space-y-6">
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <SkillPacksTable
              packs={packs}
              isLoading={packsQuery.isLoading}
              sorting={sorting}
              onSortingChange={onSortingChange}
              stickyHeader
              getEditHref={(pack) => `/skills/packs/${pack.id}/edit`}
              canSync
              syncingPackIds={syncingPackIds}
              onSync={(pack) => {
                void (async () => {
                  setSyncingPackIds((previous) => {
                    const next = new Set(previous);
                    next.add(pack.id);
                    return next;
                  });
                  try {
                    await syncMutation.mutateAsync({
                      packId: pack.id,
                    });
                  } finally {
                    setSyncingPackIds((previous) => {
                      const next = new Set(previous);
                      next.delete(pack.id);
                      return next;
                    });
                  }
                })();
              }}
              onDelete={setDeleteTarget}
              emptyState={{
                title: "No packs yet",
                description: "Add your first skill URL pack to get started.",
                actionHref: "/skills/packs/new",
                actionLabel: "Add your first pack",
              }}
            />
          </div>

          {packsQuery.error ? (
            <p className="text-sm text-rose-600">{packsQuery.error.message}</p>
          ) : null}
          {deleteMutation.error ? (
            <p className="text-sm text-rose-600">{deleteMutation.error.message}</p>
          ) : null}
          {syncMutation.error ? (
            <p className="text-sm text-rose-600">{syncMutation.error.message}</p>
          ) : null}
        </div>
      </DashboardPageLayout>

      <ConfirmActionDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        ariaLabel="Delete skill pack"
        title="Delete skill pack"
        description={
          <>
            This will remove <strong>{deleteTarget?.name}</strong> from your
            pack list. This action cannot be undone.
          </>
        }
        errorMessage={deleteMutation.error?.message}
        onConfirm={handleDelete}
        isConfirming={deleteMutation.isPending}
      />
    </>
  );
}
