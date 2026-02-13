"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useAuth } from "@/auth/clerk";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/mutator";
import {
  type listGatewaysApiV1GatewaysGetResponse,
  useListGatewaysApiV1GatewaysGet,
} from "@/api/generated/gateways/gateways";
import type { MarketplaceSkillCardRead } from "@/api/generated/model";
import {
  listMarketplaceSkillsApiV1SkillsMarketplaceGet,
  type listMarketplaceSkillsApiV1SkillsMarketplaceGetResponse,
  useInstallMarketplaceSkillApiV1SkillsMarketplaceSkillIdInstallPost,
  useListMarketplaceSkillsApiV1SkillsMarketplaceGet,
  useUninstallMarketplaceSkillApiV1SkillsMarketplaceSkillIdUninstallPost,
} from "@/api/generated/skills-marketplace/skills-marketplace";
import {
  type listSkillPacksApiV1SkillsPacksGetResponse,
  useListSkillPacksApiV1SkillsPacksGet,
} from "@/api/generated/skills/skills";
import { MarketplaceSkillsTable } from "@/components/skills/MarketplaceSkillsTable";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { useUrlSorting } from "@/lib/use-url-sorting";

const MARKETPLACE_SKILLS_SORTABLE_COLUMNS = [
  "name",
  "category",
  "risk",
  "source",
  "updated_at",
];

const normalizeRepoSourceUrl = (sourceUrl: string): string => {
  const trimmed = sourceUrl.trim().replace(/\/+$/, "");
  return trimmed.endsWith(".git") ? trimmed.slice(0, -4) : trimmed;
};

const repoBaseFromSkillSourceUrl = (skillSourceUrl: string): string | null => {
  try {
    const parsed = new URL(skillSourceUrl);
    const marker = "/tree/";
    const markerIndex = parsed.pathname.indexOf(marker);
    if (markerIndex <= 0) return null;
    return normalizeRepoSourceUrl(
      `${parsed.origin}${parsed.pathname.slice(0, markerIndex)}`,
    );
  } catch {
    return null;
  }
};

export default function SkillsMarketplacePage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const [selectedSkill, setSelectedSkill] = useState<MarketplaceSkillCardRead | null>(null);
  const [gatewayInstalledById, setGatewayInstalledById] = useState<
    Record<string, boolean>
  >({});
  const [isGatewayStatusLoading, setIsGatewayStatusLoading] = useState(false);
  const [gatewayStatusError, setGatewayStatusError] = useState<string | null>(null);
  const [installingGatewayId, setInstallingGatewayId] = useState<string | null>(null);

  const { sorting, onSortingChange } = useUrlSorting({
    allowedColumnIds: MARKETPLACE_SKILLS_SORTABLE_COLUMNS,
    defaultSorting: [{ id: "name", desc: false }],
    paramPrefix: "skills_marketplace",
  });

  const gatewaysQuery = useListGatewaysApiV1GatewaysGet<
    listGatewaysApiV1GatewaysGetResponse,
    ApiError
  >(undefined, {
    query: {
      enabled: Boolean(isSignedIn && isAdmin),
      refetchOnMount: "always",
      refetchInterval: 30_000,
    },
  });

  const gateways = useMemo(
    () =>
      gatewaysQuery.data?.status === 200
        ? (gatewaysQuery.data.data.items ?? [])
        : [],
    [gatewaysQuery.data],
  );

  const resolvedGatewayId = gateways[0]?.id ?? "";

  const skillsQuery = useListMarketplaceSkillsApiV1SkillsMarketplaceGet<
    listMarketplaceSkillsApiV1SkillsMarketplaceGetResponse,
    ApiError
  >(
    { gateway_id: resolvedGatewayId },
    {
      query: {
        enabled: Boolean(isSignedIn && isAdmin && resolvedGatewayId),
        refetchOnMount: "always",
        refetchInterval: 15_000,
      },
    },
  );

  const skills = useMemo<MarketplaceSkillCardRead[]>(
    () => (skillsQuery.data?.status === 200 ? skillsQuery.data.data : []),
    [skillsQuery.data],
  );

  const packsQuery = useListSkillPacksApiV1SkillsPacksGet<
    listSkillPacksApiV1SkillsPacksGetResponse,
    ApiError
  >({
    query: {
      enabled: Boolean(isSignedIn && isAdmin),
      refetchOnMount: "always",
    },
  });

  const packs = useMemo(
    () => (packsQuery.data?.status === 200 ? packsQuery.data.data : []),
    [packsQuery.data],
  );

  const selectedPackId = searchParams.get("packId");
  const selectedPack = useMemo(
    () => packs.find((pack) => pack.id === selectedPackId) ?? null,
    [packs, selectedPackId],
  );

  const visibleSkills = useMemo(() => {
    if (!selectedPack) return skills;
    const selectedRepo = normalizeRepoSourceUrl(selectedPack.source_url);
    return skills.filter((skill) => {
      const skillRepo = repoBaseFromSkillSourceUrl(skill.source_url);
      return skillRepo === selectedRepo;
    });
  }, [selectedPack, skills]);

  const installMutation =
    useInstallMarketplaceSkillApiV1SkillsMarketplaceSkillIdInstallPost<ApiError>(
      {
        mutation: {
          onSuccess: async (_, variables) => {
            await queryClient.invalidateQueries({
              queryKey: ["/api/v1/skills/marketplace"],
            });
            setGatewayInstalledById((previous) => ({
              ...previous,
              [variables.params.gateway_id]: true,
            }));
          },
        },
      },
      queryClient,
    );

  const uninstallMutation =
    useUninstallMarketplaceSkillApiV1SkillsMarketplaceSkillIdUninstallPost<ApiError>(
      {
        mutation: {
          onSuccess: async () => {
            await queryClient.invalidateQueries({
              queryKey: ["/api/v1/skills/marketplace"],
            });
          },
        },
      },
      queryClient,
    );

  useEffect(() => {
    let cancelled = false;

    const loadGatewayStatus = async () => {
      if (!selectedSkill) {
        setGatewayInstalledById({});
        setGatewayStatusError(null);
        setIsGatewayStatusLoading(false);
        return;
      }

      if (gateways.length === 0) {
        setGatewayInstalledById({});
        setGatewayStatusError(null);
        setIsGatewayStatusLoading(false);
        return;
      }

      setIsGatewayStatusLoading(true);
      setGatewayStatusError(null);
      try {
        const entries = await Promise.all(
          gateways.map(async (gateway) => {
            const response = await listMarketplaceSkillsApiV1SkillsMarketplaceGet({
              gateway_id: gateway.id,
            });
            const row =
              response.status === 200
                ? response.data.find((skill) => skill.id === selectedSkill.id)
                : null;
            return [gateway.id, Boolean(row?.installed)] as const;
          }),
        );
        if (cancelled) return;
        setGatewayInstalledById(Object.fromEntries(entries));
      } catch (error) {
        if (cancelled) return;
        setGatewayStatusError(
          error instanceof Error ? error.message : "Unable to load gateway status.",
        );
      } finally {
        if (!cancelled) {
          setIsGatewayStatusLoading(false);
        }
      }
    };

    void loadGatewayStatus();

    return () => {
      cancelled = true;
    };
  }, [gateways, selectedSkill]);

  const mutationError =
    installMutation.error?.message ?? uninstallMutation.error?.message;

  const isMutating = installMutation.isPending || uninstallMutation.isPending;

  const handleInstallToGateway = async (gatewayId: string) => {
    if (!selectedSkill) return;
    setInstallingGatewayId(gatewayId);
    try {
      await installMutation.mutateAsync({
        skillId: selectedSkill.id,
        params: { gateway_id: gatewayId },
      });
    } finally {
      setInstallingGatewayId(null);
    }
  };

  return (
    <>
      <DashboardPageLayout
        signedOut={{
          message: "Sign in to manage marketplace skills.",
          forceRedirectUrl: "/skills/marketplace",
        }}
        title="Skills Marketplace"
        description={
          selectedPack
            ? `${visibleSkills.length} skill${
                visibleSkills.length === 1 ? "" : "s"
              } for ${selectedPack.name}.`
            : `${visibleSkills.length} skill${
                visibleSkills.length === 1 ? "" : "s"
              } synced from packs.`
        }
        isAdmin={isAdmin}
        adminOnlyMessage="Only organization owners and admins can manage skills."
        stickyHeader
      >
        <div className="space-y-6">
          {gateways.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
              <p className="font-medium text-slate-900">No gateways available yet.</p>
              <p className="mt-2">
                Create a gateway first, then return here to manage installs.
              </p>
              <Link
                href="/gateways/new"
                className={`${buttonVariants({ variant: "primary", size: "md" })} mt-4`}
              >
                Create gateway
              </Link>
            </div>
          ) : (
            <>
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <MarketplaceSkillsTable
                  skills={visibleSkills}
                  isLoading={skillsQuery.isLoading}
                  sorting={sorting}
                  onSortingChange={onSortingChange}
                  stickyHeader
                  canInstallActions={Boolean(resolvedGatewayId)}
                  isMutating={isMutating}
                  onSkillClick={setSelectedSkill}
                  onUninstall={(skill) =>
                    uninstallMutation.mutate({
                      skillId: skill.id,
                      params: { gateway_id: resolvedGatewayId },
                    })
                  }
                  emptyState={{
                    title: "No marketplace skills yet",
                    description: "Add packs first, then synced skills will appear here.",
                    actionHref: "/skills/packs/new",
                    actionLabel: "Add your first pack",
                  }}
                />
              </div>
            </>
          )}

        {skillsQuery.error ? (
          <p className="text-sm text-rose-600">{skillsQuery.error.message}</p>
        ) : null}
        {packsQuery.error ? (
          <p className="text-sm text-rose-600">{packsQuery.error.message}</p>
        ) : null}
        {mutationError ? <p className="text-sm text-rose-600">{mutationError}</p> : null}
      </div>
      </DashboardPageLayout>

      <Dialog
        open={Boolean(selectedSkill)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedSkill(null);
          }
        }}
      >
        <DialogContent
          aria-label="Install skill on gateways"
          className="max-w-xl p-6 sm:p-7"
        >
          <DialogHeader className="pb-1">
            <DialogTitle>{selectedSkill ? selectedSkill.name : "Install skill"}</DialogTitle>
            <DialogDescription>
              Choose one or more gateways where this skill should be installed.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-2 space-y-3.5">
            {isGatewayStatusLoading ? (
              <p className="text-sm text-slate-500">Loading gateways...</p>
            ) : (
              gateways.map((gateway) => {
                const isInstalled = gatewayInstalledById[gateway.id] === true;
                const isInstalling =
                  installMutation.isPending && installingGatewayId === gateway.id;
                return (
                  <div
                    key={gateway.id}
                    className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4"
                  >
                    <div>
                      <p className="text-sm font-medium text-slate-900">{gateway.name}</p>
                      <p className="text-xs text-slate-500">
                        {isInstalled ? "Installed" : "Not installed"}
                      </p>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void handleInstallToGateway(gateway.id)}
                      disabled={isInstalled || installMutation.isPending}
                    >
                      {isInstalled ? "Installed" : isInstalling ? "Installing..." : "Install"}
                    </Button>
                  </div>
                );
              })
            )}
            {gatewayStatusError ? (
              <p className="text-sm text-rose-600">{gatewayStatusError}</p>
            ) : null}
            {installMutation.error ? (
              <p className="text-sm text-rose-600">{installMutation.error.message}</p>
            ) : null}
          </div>

          <DialogFooter className="mt-6 border-t border-slate-200 pt-4">
            <Button
              variant="outline"
              onClick={() => setSelectedSkill(null)}
              disabled={installMutation.isPending}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
