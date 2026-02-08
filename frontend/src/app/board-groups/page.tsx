"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";
import Link from "next/link";

import { useAuth } from "@/auth/clerk";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/mutator";
import {
  type listBoardGroupsApiV1BoardGroupsGetResponse,
  getListBoardGroupsApiV1BoardGroupsGetQueryKey,
  useDeleteBoardGroupApiV1BoardGroupsGroupIdDelete,
  useListBoardGroupsApiV1BoardGroupsGet,
} from "@/api/generated/board-groups/board-groups";
import type { BoardGroupRead } from "@/api/generated/model";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConfirmActionDialog } from "@/components/ui/confirm-action-dialog";
import { formatTimestamp } from "@/lib/formatters";
import { TableEmptyStateRow, TableLoadingRow } from "@/components/ui/table-state";

export default function BoardGroupsPage() {
  const { isSignedIn } = useAuth();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<BoardGroupRead | null>(null);

  const groupsKey = getListBoardGroupsApiV1BoardGroupsGetQueryKey();
  const groupsQuery = useListBoardGroupsApiV1BoardGroupsGet<
    listBoardGroupsApiV1BoardGroupsGetResponse,
    ApiError
  >(undefined, {
    query: {
      enabled: Boolean(isSignedIn),
      refetchInterval: 30_000,
      refetchOnMount: "always",
    },
  });

  const groups = useMemo(
    () =>
      groupsQuery.data?.status === 200
        ? (groupsQuery.data.data.items ?? [])
        : [],
    [groupsQuery.data],
  );

  const deleteMutation = useDeleteBoardGroupApiV1BoardGroupsGroupIdDelete<
    ApiError,
    { previous?: listBoardGroupsApiV1BoardGroupsGetResponse }
  >(
    {
      mutation: {
        onMutate: async ({ groupId }) => {
          await queryClient.cancelQueries({ queryKey: groupsKey });
          const previous =
            queryClient.getQueryData<listBoardGroupsApiV1BoardGroupsGetResponse>(
              groupsKey,
            );
          if (previous && previous.status === 200) {
            const nextItems = previous.data.items.filter(
              (group) => group.id !== groupId,
            );
            const removedCount = previous.data.items.length - nextItems.length;
            queryClient.setQueryData<listBoardGroupsApiV1BoardGroupsGetResponse>(
              groupsKey,
              {
                ...previous,
                data: {
                  ...previous.data,
                  items: nextItems,
                  total: Math.max(0, previous.data.total - removedCount),
                },
              },
            );
          }
          return { previous };
        },
        onError: (_error, _group, context) => {
          if (context?.previous) {
            queryClient.setQueryData(groupsKey, context.previous);
          }
        },
        onSuccess: () => {
          setDeleteTarget(null);
        },
        onSettled: () => {
          queryClient.invalidateQueries({ queryKey: groupsKey });
        },
      },
    },
    queryClient,
  );

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate({ groupId: deleteTarget.id });
  };

  const columns = useMemo<ColumnDef<BoardGroupRead>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Group",
        cell: ({ row }) => (
          <Link
            href={`/board-groups/${row.original.id}`}
            className="group block"
          >
            <p className="text-sm font-medium text-slate-900 group-hover:text-blue-600">
              {row.original.name}
            </p>
            {row.original.description ? (
              <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                {row.original.description}
              </p>
            ) : (
              <p className="mt-1 text-xs text-slate-400">No description</p>
            )}
          </Link>
        ),
      },
      {
        accessorKey: "updated_at",
        header: "Updated",
        cell: ({ row }) => (
          <span className="text-sm text-slate-700">
            {formatTimestamp(row.original.updated_at)}
          </span>
        ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center justify-end gap-2">
            <Link
              href={`/board-groups/${row.original.id}/edit`}
              className={buttonVariants({ variant: "ghost", size: "sm" })}
            >
              Edit
            </Link>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeleteTarget(row.original)}
            >
              Delete
            </Button>
          </div>
        ),
      },
    ],
    [],
  );

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: groups,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <>
      <DashboardPageLayout
        signedOut={{
          message: "Sign in to view board groups.",
          forceRedirectUrl: "/board-groups",
        }}
        title="Board groups"
        description={`Group boards so agents can see related work. ${groups.length} group${groups.length === 1 ? "" : "s"} total.`}
        headerActions={
          <Link
            href="/board-groups/new"
            className={buttonVariants({ size: "md", variant: "primary" })}
          >
            Create group
          </Link>
        }
        stickyHeader
      >
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th
                        key={header.id}
                        className="px-6 py-3 text-left font-semibold"
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-slate-100">
                {groupsQuery.isLoading ? (
                  <TableLoadingRow colSpan={columns.length} />
                ) : table.getRowModel().rows.length ? (
                  table.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="transition hover:bg-slate-50">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-6 py-4 align-top">
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )}
                        </td>
                      ))}
                    </tr>
                  ))
                ) : (
                  <TableEmptyStateRow
                    colSpan={columns.length}
                    icon={
                      <svg
                        className="h-16 w-16 text-slate-300"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M3 7h8" />
                        <path d="M3 17h8" />
                        <path d="M13 7h8" />
                        <path d="M13 17h8" />
                        <path d="M3 12h18" />
                      </svg>
                    }
                    title="No groups yet"
                    description="Create a board group to increase cross-board visibility for agents."
                    actionHref="/board-groups/new"
                    actionLabel="Create your first group"
                  />
                )}
              </tbody>
            </table>
          </div>
        </div>

        {groupsQuery.error ? (
          <p className="mt-4 text-sm text-red-500">{groupsQuery.error.message}</p>
        ) : null}
      </DashboardPageLayout>
      <ConfirmActionDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
          }
        }}
        ariaLabel="Delete board group"
        title="Delete board group"
        description={
          <>
            This will remove {deleteTarget?.name}. Boards will be ungrouped.
            This action cannot be undone.
          </>
        }
        errorMessage={deleteMutation.error?.message}
        onConfirm={handleDelete}
        isConfirming={deleteMutation.isPending}
      />
    </>
  );
}
