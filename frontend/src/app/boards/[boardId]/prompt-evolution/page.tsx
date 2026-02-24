"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { Button } from "@/components/ui/button";
import { ApiError, customFetch } from "@/api/mutator";

type PromptPack = {
  id: string;
  name: string;
  scope: string;
  champion_version_id?: string | null;
  challenger_version_id?: string | null;
};

type PromptVersion = {
  id: string;
  version_number: number;
  created_at: string;
  instruction_text: string;
};

type TaskEvalScore = {
  id: string;
  score?: number | null;
  passed?: boolean | null;
  created_at: string;
};

export default function PromptEvolutionPage() {
  const params = useParams();
  const router = useRouter();
  const boardIdParam = params?.boardId;
  const boardId = Array.isArray(boardIdParam) ? boardIdParam[0] : boardIdParam;

  const [packs, setPacks] = useState<PromptPack[]>([]);
  const [versionsByPack, setVersionsByPack] = useState<Record<string, PromptVersion[]>>({});
  const [taskEvals, setTaskEvals] = useState<TaskEvalScore[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const load = useCallback(async () => {
    if (!boardId) return;
    setIsLoading(true);
    setError(null);
    try {
      const packsRes = await customFetch<{ data: PromptPack[] }>(
        `/api/v1/boards/${boardId}/prompt-evolution/packs`,
        { method: "GET" },
      );
      const evalRes = await customFetch<{ data: TaskEvalScore[] }>(
        `/api/v1/boards/${boardId}/prompt-evolution/task-evals`,
        { method: "GET" },
      );
      setPacks(packsRes.data ?? []);
      setTaskEvals(evalRes.data ?? []);

      const next: Record<string, PromptVersion[]> = {};
      await Promise.all(
        (packsRes.data ?? []).map(async (pack) => {
          const versionsRes = await customFetch<{ data: PromptVersion[] }>(
            `/api/v1/boards/${boardId}/prompt-evolution/packs/${pack.id}/versions`,
            { method: "GET" },
          );
          next[pack.id] = versionsRes.data ?? [];
        }),
      );
      setVersionsByPack(next);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to load prompt evolution data.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [boardId]);

  useEffect(() => {
    void load();
  }, [load]);

  const avgScore = useMemo(() => {
    const scores = taskEvals
      .map((item) => item.score)
      .filter((v): v is number => typeof v === "number");
    if (!scores.length) return null;
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  }, [taskEvals]);

  return (
    <DashboardShell>
      <DashboardSidebar />
      <main className="flex-1 overflow-y-auto bg-slate-50 p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Prompt Evolution</h1>
            <p className="text-sm text-slate-500">
              Manual promotion gate, version visibility, and evaluation telemetry.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => router.push(`/boards/${boardId}`)}>
              Back to board
            </Button>
            <Button onClick={() => void load()} disabled={isLoading}>
              {isLoading ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="mb-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Prompt Packs</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{packs.length}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Task Evals</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{taskEvals.length}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Avg Score</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {avgScore === null ? "—" : avgScore.toFixed(3)}
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {packs.map((pack) => {
            const versions = versionsByPack[pack.id] ?? [];
            return (
              <section key={pack.id} className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">{pack.name}</h2>
                    <p className="text-xs text-slate-500">scope: {pack.scope}</p>
                  </div>
                </div>
                <div className="space-y-2">
                  {versions.length === 0 ? (
                    <p className="text-sm text-slate-500">No versions yet.</p>
                  ) : (
                    versions.map((version) => (
                      <div
                        key={version.id}
                        className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
                      >
                        <div className="mb-1 flex items-center justify-between">
                          <span className="font-semibold text-slate-900">v{version.version_number}</span>
                          <span className="text-xs text-slate-500">
                            {new Date(version.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="line-clamp-2 text-xs text-slate-600">{version.instruction_text}</p>
                      </div>
                    ))
                  )}
                </div>
              </section>
            );
          })}
          {!packs.length ? (
            <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
              No prompt packs configured yet.
            </div>
          ) : null}
        </div>
      </main>
    </DashboardShell>
  );
}
