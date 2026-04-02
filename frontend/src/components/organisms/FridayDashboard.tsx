"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Activity,
  Bot,
  Brain,
  MessagesSquare,
  RefreshCw,
  Send,
  ShieldCheck,
} from "lucide-react";

import { customFetch } from "@/api/mutator";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type FridayAgentStatus = {
  id: string;
  label: string;
  status: "online" | "offline" | "degraded" | "unknown";
  model?: string | null;
  interface?: string | null;
  detail?: string | null;
};

type FridayStatusResponse = {
  provider: string;
  model: string;
  service_url: string;
  reachable: boolean;
  detail?: string | null;
  agents: FridayAgentStatus[];
};

type FridayMemoryItem = {
  id?: string | null;
  content: string;
  created_at?: string | null;
  tags: string[];
};

type FridayMemoryResponse = {
  reachable: boolean;
  items: FridayMemoryItem[];
};

type FridayTelegramLogItem = {
  id?: string | null;
  direction: "incoming" | "outgoing" | "system";
  chat_id?: string | null;
  text: string;
  timestamp?: string | null;
};

type FridayTelegramLogsResponse = {
  reachable: boolean;
  items: FridayTelegramLogItem[];
};

type FridayChatResponse = {
  response: string;
  provider: string;
  model: string;
  memory_ids: string[];
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
};

const FALLBACK_STATUS: FridayStatusResponse = {
  provider: "zhipuai",
  model: "glm-5",
  service_url: "http://friday:8001",
  reachable: false,
  detail: null,
  agents: [
    {
      id: "friday",
      label: "Friday",
      status: "online",
      model: "glm-5",
      interface: "telegram + mission-control",
      detail: "Primary KR8TIV operator",
    },
    {
      id: "arsenal",
      label: "Arsenal",
      status: "offline",
      model: null,
      interface: null,
      detail: "Offline by policy",
    },
    {
      id: "edith",
      label: "Edith",
      status: "offline",
      model: null,
      interface: null,
      detail: "Offline by policy",
    },
    {
      id: "jocasta",
      label: "Jocasta",
      status: "offline",
      model: null,
      interface: null,
      detail: "Offline by policy",
    },
  ],
};

async function getApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await customFetch<{ data: T }>(path, init ?? { method: "GET" });
  return response.data;
}

function formatTimestamp(value?: string | null): string {
  if (!value) {
    return "Just now";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function badgeVariantForStatus(status: FridayAgentStatus["status"]) {
  if (status === "online") return "success" as const;
  if (status === "degraded") return "warning" as const;
  if (status === "offline") return "outline" as const;
  return "default" as const;
}

export function FridayDashboard() {
  const [status, setStatus] = useState<FridayStatusResponse>(FALLBACK_STATUS);
  const [memoryFeed, setMemoryFeed] = useState<FridayMemoryItem[]>([]);
  const [telegramLogs, setTelegramLogs] = useState<FridayTelegramLogItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [prompt, setPrompt] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  const onlineCount = useMemo(
    () => status.agents.filter((agent) => agent.status === "online").length,
    [status.agents],
  );

  const refreshPanels = async () => {
    setIsRefreshing(true);
    try {
      const [statusResponse, memoryResponse, telegramResponse] = await Promise.all([
        getApi<FridayStatusResponse>("/api/v1/friday/status", { method: "GET" }),
        getApi<FridayMemoryResponse>("/api/v1/friday/memory/recent?limit=8", {
          method: "GET",
        }),
        getApi<FridayTelegramLogsResponse>("/api/v1/friday/telegram/logs?limit=8", {
          method: "GET",
        }),
      ]);
      setStatus(statusResponse);
      setMemoryFeed(memoryResponse.items);
      setTelegramLogs(telegramResponse.items);
      setPanelError(null);
    } catch (error) {
      setPanelError(error instanceof Error ? error.message : "Unable to refresh Friday panels.");
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    void refreshPanels();
    const intervalId = window.setInterval(() => {
      void refreshPanels();
    }, 15000);
    return () => window.clearInterval(intervalId);
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanedPrompt = prompt.trim();
    if (!cleanedPrompt) {
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: cleanedPrompt,
      createdAt: new Date().toISOString(),
    };

    setMessages((current) => [...current, userMessage]);
    setPrompt("");
    setChatError(null);
    setIsSending(true);

    try {
      const response = await getApi<FridayChatResponse>("/api/v1/friday/chat", {
        method: "POST",
        body: JSON.stringify({ message: cleanedPrompt, session_id: "mission-control" }),
      });
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: response.response,
          createdAt: new Date().toISOString(),
        },
      ]);
      void refreshPanels();
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Friday chat request failed.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to access Friday Mission Control.",
        forceRedirectUrl: "/dashboard",
        signUpForceRedirectUrl: "/dashboard",
        mode: "redirect",
      }}
      title="Friday"
      description="GLM-5 powered mission execution, memory continuity, and Telegram-linked operator control."
      headerActions={
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={status.reachable ? "success" : "warning"}>
            {status.reachable ? "Friday API reachable" : "Friday API pending"}
          </Badge>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => {
              void refreshPanels();
            }}
            disabled={isRefreshing}
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      }
      mainClassName="bg-[#09090b]"
      headerClassName="border-white/10 bg-[#050505]"
      contentClassName="bg-[#09090b]"
    >
      <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <Card className="border border-white/10 bg-black/60 shadow-[0_20px_80px_rgba(0,0,0,0.45)]">
          <CardHeader className="border-b border-white/10 pb-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-zinc-400">
                  <MessagesSquare className="h-4 w-4 text-[#2cffd5]" />
                  Friday chat
                </div>
                <h2 className="mt-2 text-2xl font-semibold text-white">
                  Direct operator channel
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="accent">{status.model}</Badge>
                <Badge variant="outline">{status.provider}</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-5">
            <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1">
              {messages.length ? (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`border px-4 py-3 ${
                      message.role === "assistant"
                        ? "border-white/10 bg-white/[0.03]"
                        : "border-[#2cffd5]/30 bg-[#2cffd5]/10"
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between gap-3 text-[11px] font-semibold uppercase tracking-[0.2em]">
                      <span className={message.role === "assistant" ? "text-zinc-400" : "text-[#2cffd5]"}>
                        {message.role === "assistant" ? "Friday" : "Matt"}
                      </span>
                      <span className="text-zinc-500">{formatTimestamp(message.createdAt)}</span>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-100">
                      {message.content}
                    </p>
                  </div>
                ))
              ) : (
                <div className="border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm leading-6 text-zinc-400">
                  Friday is ready. Ask for execution updates, campaign direction, ops triage, or Telegram-linked follow-up.
                </div>
              )}
            </div>

            {chatError ? (
              <div className="border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {chatError}
              </div>
            ) : null}

            <form onSubmit={handleSubmit} className="space-y-3">
              <Textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Tell Friday what needs to happen next…"
                className="min-h-[140px] rounded-none border-white/10 bg-white/[0.03] text-white placeholder:text-zinc-600"
                disabled={isSending}
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">
                  Friday is the only online agent.
                </p>
                <Button
                  type="submit"
                  size="lg"
                  className="rounded-none bg-[#2cffd5] text-black hover:bg-[#7dffea]"
                  disabled={isSending}
                >
                  <Send className="h-4 w-4" />
                  {isSending ? "Sending…" : "Send to Friday"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="grid gap-6">
          <Card className="border border-white/10 bg-black/60">
            <CardHeader className="border-b border-white/10 pb-5">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-zinc-400">
                <ShieldCheck className="h-4 w-4 text-[#2cffd5]" />
                Agent status
              </div>
              <div className="mt-2 flex items-center gap-3 text-white">
                <span className="text-3xl font-semibold">{onlineCount}</span>
                <span className="text-sm text-zinc-400">agent online</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 pt-5">
              {status.agents.map((agent) => (
                <div key={agent.id} className="border border-white/10 bg-white/[0.02] px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold text-white">
                        <Bot className="h-4 w-4 text-[#2cffd5]" />
                        {agent.label}
                      </div>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-zinc-500">
                        {agent.interface ?? "offline"}
                      </p>
                    </div>
                    <Badge variant={badgeVariantForStatus(agent.status)}>{agent.status}</Badge>
                  </div>
                  {agent.model ? (
                    <div className="mt-3 flex items-center gap-2 text-xs text-zinc-400">
                      <Brain className="h-3.5 w-3.5" />
                      {agent.model}
                    </div>
                  ) : null}
                  {agent.detail ? (
                    <p className="mt-2 text-sm text-zinc-400">{agent.detail}</p>
                  ) : null}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border border-white/10 bg-black/60">
            <CardHeader className="border-b border-white/10 pb-5">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-zinc-400">
                <Activity className="h-4 w-4 text-[#2cffd5]" />
                Supermemory feed
              </div>
            </CardHeader>
            <CardContent className="space-y-3 pt-5">
              {memoryFeed.length ? (
                memoryFeed.map((entry, index) => (
                  <div key={entry.id ?? `${entry.created_at ?? "memory"}-${index}`} className="border border-white/10 bg-white/[0.02] px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">memory</Badge>
                        {entry.tags.slice(0, 3).map((tag) => (
                          <Badge key={tag} variant="default">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                      <span className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
                        {formatTimestamp(entry.created_at)}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-zinc-200">{entry.content}</p>
                  </div>
                ))
              ) : (
                <div className="border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm text-zinc-400">
                  No recent Friday memory entries have been surfaced yet.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border border-white/10 bg-black/60">
            <CardHeader className="border-b border-white/10 pb-5">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-zinc-400">
                <MessagesSquare className="h-4 w-4 text-[#2cffd5]" />
                Telegram log
              </div>
            </CardHeader>
            <CardContent className="space-y-3 pt-5">
              {telegramLogs.length ? (
                telegramLogs.map((entry, index) => (
                  <div key={entry.id ?? `${entry.timestamp ?? "telegram"}-${index}`} className="border border-white/10 bg-white/[0.02] px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            entry.direction === "incoming"
                              ? "outline"
                              : entry.direction === "outgoing"
                                ? "accent"
                                : "default"
                          }
                        >
                          {entry.direction}
                        </Badge>
                        {entry.chat_id ? (
                          <span className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
                            {entry.chat_id}
                          </span>
                        ) : null}
                      </div>
                      <span className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
                        {formatTimestamp(entry.timestamp)}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-zinc-200">{entry.text}</p>
                  </div>
                ))
              ) : (
                <div className="border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm text-zinc-400">
                  Telegram activity will appear here once Friday starts recording traffic.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {panelError ? (
        <div className="mt-6 border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100">
          {panelError}
        </div>
      ) : null}
    </DashboardPageLayout>
  );
}
