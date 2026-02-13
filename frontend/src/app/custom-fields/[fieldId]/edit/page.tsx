"use client";

export const dynamic = "force-dynamic";

import { type FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { useAuth } from "@/auth/clerk";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/mutator";
import {
  type listBoardsApiV1BoardsGetResponse,
  useListBoardsApiV1BoardsGet,
} from "@/api/generated/boards/boards";
import {
  type listOrgCustomFieldsApiV1OrganizationsMeCustomFieldsGetResponse,
  getListOrgCustomFieldsApiV1OrganizationsMeCustomFieldsGetQueryKey,
  useListOrgCustomFieldsApiV1OrganizationsMeCustomFieldsGet,
  useUpdateOrgCustomFieldApiV1OrganizationsMeCustomFieldsTaskCustomFieldDefinitionIdPatch,
} from "@/api/generated/org-custom-fields/org-custom-fields";
import type {
  BoardRead,
  TaskCustomFieldDefinitionRead,
  TaskCustomFieldDefinitionUpdate,
} from "@/api/generated/model";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useOrganizationMembership } from "@/lib/use-organization-membership";

type FormState = {
  fieldKey: string;
  label: string;
  fieldType:
    | "text"
    | "text_long"
    | "integer"
    | "decimal"
    | "boolean"
    | "date"
    | "date_time"
    | "url"
    | "json";
  uiVisibility: "always" | "if_set" | "hidden";
  validationRegex: string;
  description: string;
  required: boolean;
  defaultValue: string;
};

type EditCustomFieldFormProps = {
  field: TaskCustomFieldDefinitionRead;
  boards: BoardRead[];
  boardsLoading: boolean;
  boardsError: string | null;
  saving: boolean;
  onSubmit: (updates: TaskCustomFieldDefinitionUpdate) => Promise<void>;
};

const STRING_FIELD_TYPES = new Set(["text", "text_long", "date", "date_time", "url"]);

const parseDefaultValue = (
  fieldType: FormState["fieldType"],
  value: string,
): { value: unknown | null; error: string | null } => {
  const trimmed = value.trim();
  if (!trimmed) return { value: null, error: null };
  if (fieldType === "text" || fieldType === "text_long") {
    return { value: trimmed, error: null };
  }
  if (fieldType === "integer") {
    if (!/^-?\d+$/.test(trimmed)) {
      return { value: null, error: "Default value must be a valid integer." };
    }
    return { value: Number.parseInt(trimmed, 10), error: null };
  }
  if (fieldType === "decimal") {
    if (!/^-?\d+(\.\d+)?$/.test(trimmed)) {
      return { value: null, error: "Default value must be a valid decimal." };
    }
    return { value: Number.parseFloat(trimmed), error: null };
  }
  if (fieldType === "boolean") {
    if (trimmed.toLowerCase() === "true") return { value: true, error: null };
    if (trimmed.toLowerCase() === "false")
      return { value: false, error: null };
    return { value: null, error: "Default value must be true or false." };
  }
  if (fieldType === "date" || fieldType === "date_time" || fieldType === "url") {
    return { value: trimmed, error: null };
  }
  if (fieldType === "json") {
    try {
      const parsed = JSON.parse(trimmed);
      if (
        parsed === null ||
        typeof parsed !== "object" ||
        (!Array.isArray(parsed) && typeof parsed !== "object")
      ) {
        return {
          value: null,
          error: "Default value must be valid JSON (object or array).",
        };
      }
      return { value: parsed, error: null };
    } catch {
      return {
        value: null,
        error: "Default value must be valid JSON (object or array).",
      };
    }
  }
  try {
    return { value: JSON.parse(trimmed), error: null };
  } catch {
    return { value: trimmed, error: null };
  }
};

const formatDefaultValue = (value: unknown): string => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const canonicalJson = (value: unknown): string =>
  JSON.stringify(value) ?? "undefined";

const extractErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof ApiError) return error.message || fallback;
  if (error instanceof Error) return error.message || fallback;
  return fallback;
};

function EditCustomFieldForm({
  field,
  boards,
  boardsLoading,
  boardsError,
  saving,
  onSubmit,
}: EditCustomFieldFormProps) {
  const [formState, setFormState] = useState<FormState>(() => ({
    fieldKey: field.field_key,
    label: field.label ?? field.field_key,
    fieldType: field.field_type ?? "text",
    uiVisibility: field.ui_visibility ?? "always",
    validationRegex: field.validation_regex ?? "",
    description: field.description ?? "",
    required: field.required === true,
    defaultValue: formatDefaultValue(field.default_value),
  }));
  const [boardSearch, setBoardSearch] = useState("");
  const [selectedBoardIds, setSelectedBoardIds] = useState<Set<string>>(
    () => new Set(field.board_ids ?? []),
  );
  const [saveError, setSaveError] = useState<string | null>(null);

  const filteredBoards = useMemo(() => {
    const query = boardSearch.trim().toLowerCase();
    if (!query) return boards;
    return boards.filter(
      (board) =>
        board.name.toLowerCase().includes(query) ||
        board.slug.toLowerCase().includes(query),
    );
  }, [boardSearch, boards]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);

    const trimmedLabel = formState.label.trim();
    const trimmedValidationRegex = formState.validationRegex.trim();
    if (!trimmedLabel) {
      setSaveError("Label is required.");
      return;
    }
    if (selectedBoardIds.size === 0) {
      setSaveError("Select at least one board.");
      return;
    }
    if (
      trimmedValidationRegex &&
      !STRING_FIELD_TYPES.has(formState.fieldType)
    ) {
      setSaveError("Validation regex is only supported for string field types.");
      return;
    }
    const parsedDefaultValue = parseDefaultValue(
      formState.fieldType,
      formState.defaultValue,
    );
    if (parsedDefaultValue.error) {
      setSaveError(parsedDefaultValue.error);
      return;
    }

    const payload = {
      label: trimmedLabel,
      field_type: formState.fieldType,
      ui_visibility: formState.uiVisibility,
      validation_regex: trimmedValidationRegex || null,
      description: formState.description.trim() || null,
      required: formState.required,
      default_value: parsedDefaultValue.value,
      board_ids: Array.from(selectedBoardIds),
    };

    const updates: TaskCustomFieldDefinitionUpdate = {};
    if (payload.label !== (field.label ?? field.field_key)) {
      updates.label = payload.label;
    }
    if (payload.field_type !== (field.field_type ?? "text")) {
      updates.field_type = payload.field_type;
    }
    if (payload.ui_visibility !== (field.ui_visibility ?? "always")) {
      updates.ui_visibility = payload.ui_visibility;
    }
    if (payload.validation_regex !== (field.validation_regex ?? null)) {
      updates.validation_regex = payload.validation_regex;
    }
    if (payload.description !== (field.description ?? null)) {
      updates.description = payload.description;
    }
    if (payload.required !== (field.required === true)) {
      updates.required = payload.required;
    }
    if (
      canonicalJson(payload.default_value) !==
      canonicalJson(field.default_value)
    ) {
      updates.default_value = payload.default_value;
    }
    const currentBoardIds = [...(field.board_ids ?? [])].sort();
    const nextBoardIds = [...payload.board_ids].sort();
    if (JSON.stringify(currentBoardIds) !== JSON.stringify(nextBoardIds)) {
      updates.board_ids = payload.board_ids;
    }
    if (Object.keys(updates).length === 0) {
      setSaveError("No changes were made.");
      return;
    }

    try {
      await onSubmit(updates);
    } catch (error) {
      setSaveError(
        extractErrorMessage(error, "Failed to update custom field."),
      );
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-6"
    >
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Basic configuration
        </p>
        <div className="mt-4 grid gap-6 md:grid-cols-2">
          <label className="space-y-1">
            <span className="text-sm font-semibold text-slate-900">
              Field key
            </span>
            <Input
              value={formState.fieldKey}
              placeholder="e.g. client_name"
              readOnly
              disabled
            />
            <span className="text-xs text-slate-500">
              Field key cannot be changed after creation.
            </span>
          </label>
          <label className="space-y-1">
            <span className="text-sm font-semibold text-slate-900">Label</span>
            <Input
              value={formState.label}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, label: event.target.value }))
              }
              placeholder="e.g. Client name"
              disabled={saving}
              required
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-semibold text-slate-900">
              Field type
            </span>
            <Select
              value={formState.fieldType}
              onValueChange={(value) =>
                setFormState((prev) => ({
                  ...prev,
                  fieldType: value as FormState["fieldType"],
                }))
              }
              disabled={saving}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select field type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text">Text</SelectItem>
                <SelectItem value="text_long">Text (long)</SelectItem>
                <SelectItem value="integer">Integer</SelectItem>
                <SelectItem value="decimal">Decimal</SelectItem>
                <SelectItem value="boolean">Boolean (true/false)</SelectItem>
                <SelectItem value="date">Date</SelectItem>
                <SelectItem value="date_time">Date &amp; time</SelectItem>
                <SelectItem value="url">URL</SelectItem>
                <SelectItem value="json">JSON</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="space-y-1">
            <span className="text-sm font-semibold text-slate-900">
              UI visible
            </span>
            <Select
              value={formState.uiVisibility}
              onValueChange={(value) =>
                setFormState((prev) => ({
                  ...prev,
                  uiVisibility: value as FormState["uiVisibility"],
                }))
              }
              disabled={saving}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select visibility" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="always">Always</SelectItem>
                <SelectItem value="if_set">If set</SelectItem>
                <SelectItem value="hidden">Hidden</SelectItem>
              </SelectContent>
            </Select>
          </label>
        </div>
        <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={formState.required}
            onChange={(event) =>
              setFormState((prev) => ({
                ...prev,
                required: event.target.checked,
              }))
            }
            disabled={saving}
          />
          Required
        </label>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Validation and defaults
        </p>
        <div className="mt-4 space-y-4">
          <label className="space-y-1">
            <span className="text-sm font-semibold text-slate-900">
              Validation regex
            </span>
            <Input
              value={formState.validationRegex}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  validationRegex: event.target.value,
                }))
              }
              placeholder="Optional. Example: ^[A-Z]{3}$"
              disabled={saving || !STRING_FIELD_TYPES.has(formState.fieldType)}
            />
            <p className="text-xs text-slate-500">
              Supported for text/date/date-time/url fields.
            </p>
          </label>
          <label className="space-y-1">
            <span className="text-sm font-semibold text-slate-900">
              Default value
            </span>
            <Textarea
              value={formState.defaultValue}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  defaultValue: event.target.value,
                }))
              }
              rows={3}
              placeholder='Optional default value. For booleans use "true"/"false"; for JSON use an object or array.'
              disabled={saving}
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-semibold text-slate-900">
              Description
            </span>
            <Textarea
              value={formState.description}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  description: event.target.value,
                }))
              }
              rows={3}
              placeholder="Optional description used by agents and UI"
              disabled={saving}
            />
          </label>
        </div>
      </div>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Board bindings
          </p>
          <span className="text-xs text-slate-500">
            {selectedBoardIds.size} selected
          </span>
        </div>
        <div className="mt-4 space-y-2">
          <Input
            value={boardSearch}
            onChange={(event) => setBoardSearch(event.target.value)}
            placeholder="Search boards..."
            disabled={saving}
          />
          <div className="max-h-64 overflow-auto rounded-xl border border-slate-200 bg-slate-50/40">
            {boardsLoading ? (
              <div className="px-4 py-6 text-sm text-slate-500">
                Loading boards…
              </div>
            ) : boardsError ? (
              <div className="px-4 py-6 text-sm text-rose-700">{boardsError}</div>
            ) : filteredBoards.length === 0 ? (
              <div className="px-4 py-6 text-sm text-slate-500">
                No boards found.
              </div>
            ) : (
              <ul className="divide-y divide-slate-200">
                {filteredBoards.map((board) => {
                  const checked = selectedBoardIds.has(board.id);
                  return (
                    <li key={board.id} className="px-4 py-3">
                      <label className="flex cursor-pointer items-start gap-3">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600"
                          checked={checked}
                          onChange={() => {
                            setSelectedBoardIds((prev) => {
                              const next = new Set(prev);
                              if (next.has(board.id)) {
                                next.delete(board.id);
                              } else {
                                next.add(board.id);
                              }
                              return next;
                            });
                          }}
                          disabled={saving}
                        />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">
                            {board.name}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {board.slug}
                          </p>
                        </div>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          <p className="text-xs text-slate-500">
            Required. The custom field appears on tasks in selected boards.
          </p>
        </div>
      </div>

      {saveError ? <p className="text-sm text-rose-600">{saveError}</p> : null}
      <div className="flex items-center gap-2">
        <Link
          href="/custom-fields"
          className={buttonVariants({ variant: "outline" })}
          aria-disabled={saving}
        >
          Cancel
        </Link>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save changes"}
        </Button>
      </div>
    </form>
  );
}

export default function EditCustomFieldPage() {
  const router = useRouter();
  const params = useParams();
  const fieldIdParam = params?.fieldId;
  const fieldId = Array.isArray(fieldIdParam) ? fieldIdParam[0] : fieldIdParam;

  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const queryClient = useQueryClient();

  const customFieldsQuery =
    useListOrgCustomFieldsApiV1OrganizationsMeCustomFieldsGet<
      listOrgCustomFieldsApiV1OrganizationsMeCustomFieldsGetResponse,
      ApiError
    >({
      query: {
        enabled: Boolean(isSignedIn && fieldId),
        refetchOnMount: "always",
      },
    });
  const field = useMemo(() => {
    if (!fieldId || customFieldsQuery.data?.status !== 200) return null;
    return (
      customFieldsQuery.data.data.find((item) => item.id === fieldId) ?? null
    );
  }, [customFieldsQuery.data, fieldId]);

  const boardsQuery = useListBoardsApiV1BoardsGet<
    listBoardsApiV1BoardsGetResponse,
    ApiError
  >(
    { limit: 200 },
    {
      query: {
        enabled: Boolean(isSignedIn),
        refetchOnMount: "always",
        retry: false,
      },
    },
  );
  const boards = useMemo(
    () =>
      boardsQuery.data?.status === 200
        ? (boardsQuery.data.data.items ?? [])
        : [],
    [boardsQuery.data],
  );

  const updateMutation =
    useUpdateOrgCustomFieldApiV1OrganizationsMeCustomFieldsTaskCustomFieldDefinitionIdPatch<ApiError>();
  const saving = updateMutation.isPending;
  const customFieldsKey =
    getListOrgCustomFieldsApiV1OrganizationsMeCustomFieldsGetQueryKey();

  const loadError = useMemo(() => {
    if (!fieldId) return "Missing custom field id.";
    if (customFieldsQuery.error) {
      return extractErrorMessage(
        customFieldsQuery.error,
        "Failed to load custom field.",
      );
    }
    if (!customFieldsQuery.isLoading && !field)
      return "Custom field not found.";
    return null;
  }, [customFieldsQuery.error, customFieldsQuery.isLoading, field, fieldId]);

  const handleSubmit = async (updates: TaskCustomFieldDefinitionUpdate) => {
    if (!fieldId) return;
    await updateMutation.mutateAsync({
      taskCustomFieldDefinitionId: fieldId,
      data: updates,
    });
    await queryClient.invalidateQueries({ queryKey: customFieldsKey });
    router.push("/custom-fields");
  };

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to manage custom fields.",
        forceRedirectUrl: "/custom-fields",
        signUpForceRedirectUrl: "/custom-fields",
      }}
      title="Edit custom field"
      description="Update custom-field metadata and board bindings."
      isAdmin={isAdmin}
      adminOnlyMessage="Only organization owners and admins can manage custom fields."
      stickyHeader
    >
      {customFieldsQuery.isLoading ? (
        <div className="max-w-3xl rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
          Loading custom field…
        </div>
      ) : null}
      {!customFieldsQuery.isLoading && loadError ? (
        <div className="max-w-3xl rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700 shadow-sm">
          {loadError}
        </div>
      ) : null}
      {!customFieldsQuery.isLoading && !loadError && field ? (
        <EditCustomFieldForm
          key={field.id}
          field={field}
          boards={boards}
          boardsLoading={boardsQuery.isLoading}
          boardsError={boardsQuery.error?.message ?? null}
          saving={saving}
          onSubmit={handleSubmit}
        />
      ) : null}
    </DashboardPageLayout>
  );
}
