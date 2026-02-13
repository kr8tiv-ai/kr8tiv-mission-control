import { useMemo, useState } from "react";
import Link from "next/link";

import {
  type ColumnDef,
  type OnChangeFn,
  type SortingState,
  type Updater,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import type { MarketplaceSkillCardRead } from "@/api/generated/model";
import { DataTable, type DataTableEmptyState } from "@/components/tables/DataTable";
import { dateCell } from "@/components/tables/cell-formatters";
import { Button, buttonVariants } from "@/components/ui/button";
import { truncateText as truncate } from "@/lib/formatters";

type MarketplaceSkillsTableProps = {
  skills: MarketplaceSkillCardRead[];
  isLoading?: boolean;
  sorting?: SortingState;
  onSortingChange?: OnChangeFn<SortingState>;
  stickyHeader?: boolean;
  disableSorting?: boolean;
  canInstallActions: boolean;
  isMutating?: boolean;
  onSkillClick?: (skill: MarketplaceSkillCardRead) => void;
  onUninstall: (skill: MarketplaceSkillCardRead) => void;
  onDelete?: (skill: MarketplaceSkillCardRead) => void;
  getEditHref?: (skill: MarketplaceSkillCardRead) => string;
  emptyState?: Omit<DataTableEmptyState, "icon"> & {
    icon?: DataTableEmptyState["icon"];
  };
};

const DEFAULT_EMPTY_ICON = (
  <svg
    className="h-16 w-16 text-slate-300"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
    <path d="M8 7v10" />
    <path d="M16 7v10" />
  </svg>
);

const toPackUrl = (sourceUrl: string): string => {
  try {
    const parsed = new URL(sourceUrl);
    const treeMarker = "/tree/";
    const markerIndex = parsed.pathname.indexOf(treeMarker);
    if (markerIndex > 0) {
      const repoPath = parsed.pathname.slice(0, markerIndex);
      return `${parsed.origin}${repoPath}`;
    }
    return sourceUrl;
  } catch {
    return sourceUrl;
  }
};

const toPackLabel = (packUrl: string): string => {
  try {
    const parsed = new URL(packUrl);
    const segments = parsed.pathname.split("/").filter(Boolean);
    if (segments.length >= 2) {
      return `${segments[0]}/${segments[1]}`;
    }
    return parsed.host;
  } catch {
    return "Open pack";
  }
};

const toPackDetailHref = (packUrl: string): string => {
  const params = new URLSearchParams({ source_url: packUrl });
  return `/skills/packs/detail?${params.toString()}`;
};

export function MarketplaceSkillsTable({
  skills,
  isLoading = false,
  sorting,
  onSortingChange,
  stickyHeader = false,
  disableSorting = false,
  canInstallActions,
  isMutating = false,
  onSkillClick,
  onUninstall,
  onDelete,
  getEditHref,
  emptyState,
}: MarketplaceSkillsTableProps) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([
    { id: "name", desc: false },
  ]);
  const resolvedSorting = sorting ?? internalSorting;
  const handleSortingChange: OnChangeFn<SortingState> =
    onSortingChange ??
    ((updater: Updater<SortingState>) => {
      setInternalSorting(updater);
    });

  const columns = useMemo<ColumnDef<MarketplaceSkillCardRead>[]>(() => {
    const baseColumns: ColumnDef<MarketplaceSkillCardRead>[] = [
      {
        accessorKey: "name",
        header: "Skill",
        cell: ({ row }) => (
          <div>
            {onSkillClick ? (
              <button
                type="button"
                onClick={() => onSkillClick(row.original)}
                className="text-sm font-medium text-blue-700 hover:text-blue-600 hover:underline"
              >
                {row.original.name}
              </button>
            ) : (
              <p className="text-sm font-medium text-slate-900">{row.original.name}</p>
            )}
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">
              {row.original.description || "No description provided."}
            </p>
          </div>
        ),
      },
      {
        accessorKey: "source_url",
        header: "Pack",
        cell: ({ row }) => {
          const packUrl = toPackUrl(row.original.source_url);
          return (
            <Link
              href={toPackDetailHref(packUrl)}
              className="inline-flex items-center gap-1 text-sm font-medium text-slate-700 hover:text-blue-600"
            >
              {truncate(toPackLabel(packUrl), 40)}
            </Link>
          );
        },
      },
      {
        accessorKey: "category",
        header: "Category",
        cell: ({ row }) => (
          <span className="text-sm text-slate-700">
            {row.original.category || "uncategorized"}
          </span>
        ),
      },
      {
        accessorKey: "risk",
        header: "Risk",
        cell: ({ row }) => (
          <span className="text-sm text-slate-700">
            {row.original.risk || "unknown"}
          </span>
        ),
      },
      {
        accessorKey: "source",
        header: "Source",
        cell: ({ row }) => (
          <span className="text-sm text-slate-700" title={row.original.source || ""}>
            {truncate(row.original.source || "unknown", 36)}
          </span>
        ),
      },
      {
        accessorKey: "updated_at",
        header: "Updated",
        cell: ({ row }) => dateCell(row.original.updated_at),
      },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-2">
            {row.original.installed ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onUninstall(row.original)}
                disabled={isMutating || !canInstallActions}
              >
                Uninstall
              </Button>
            ) : null}
            {getEditHref ? (
              <Link
                href={getEditHref(row.original)}
                className={buttonVariants({ variant: "ghost", size: "sm" })}
              >
                Edit
              </Link>
            ) : null}
            {onDelete ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onDelete(row.original)}
                disabled={isMutating}
              >
                Delete
              </Button>
            ) : null}
          </div>
        ),
      },
    ];

    return baseColumns;
  }, [
    canInstallActions,
    getEditHref,
    isMutating,
    onDelete,
    onSkillClick,
    onUninstall,
  ]);

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: skills,
    columns,
    enableSorting: !disableSorting,
    state: {
      ...(!disableSorting ? { sorting: resolvedSorting } : {}),
    },
    ...(disableSorting ? {} : { onSortingChange: handleSortingChange }),
    getCoreRowModel: getCoreRowModel(),
    ...(disableSorting ? {} : { getSortedRowModel: getSortedRowModel() }),
  });

  return (
    <DataTable
      table={table}
      isLoading={isLoading}
      stickyHeader={stickyHeader}
      rowClassName="transition hover:bg-slate-50"
      cellClassName="px-6 py-4 align-top"
      emptyState={
        emptyState
          ? {
              icon: emptyState.icon ?? DEFAULT_EMPTY_ICON,
              title: emptyState.title,
              description: emptyState.description,
              actionHref: emptyState.actionHref,
              actionLabel: emptyState.actionLabel,
            }
          : undefined
      }
    />
  );
}
