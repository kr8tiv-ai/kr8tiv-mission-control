"""Run a deterministic 50-question NotebookLM sweep and persist markdown evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.services.notebooklm_adapter import NotebookLMError, query_notebook

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

QUESTIONS: tuple[str, ...] = (
    "What are the current hard safety constraints for sniper execution on Solana?",
    "What runtime checks are required before any buy order is placed?",
    "What are the exact freeze authority and mint authority checks required for token safety?",
    "What are the required fallback actions when authority checks cannot be completed?",
    "What is the canonical anti-honeypot pre-trade checklist?",
    "What is the expected behavior when RPC calls are degraded or timing out?",
    "What blockhash refresh strategy is required during high-volatility execution?",
    "What idempotency key rules prevent double-buy under retries?",
    "What are the required tip escalation rules for failed Jito/Jupiter submissions?",
    "What is the exact retry budget for swap execution attempts?",
    "What are the stop-loss and take-profit execution guarantees required by spec?",
    "What are the account/session wallet isolation requirements for sniper mode?",
    "How should session wallets be generated to avoid deterministic/shared key reuse?",
    "What telemetry must be recorded for each sniper order lifecycle stage?",
    "What incident conditions require automatic trading halt?",
    "What is the required kill-switch precedence order (local, board, global)?",
    "What are the required owner-approval gates before enabling autonomous execution?",
    "What are the mandatory checks for private-key handling and secret storage?",
    "What are the approved patterns for avoiding client-side secret leakage in web apps?",
    "What endpoint proxy pattern is required for Bags.fm API access?",
    "What are the mandatory JSON schema validation boundaries for LLM trade outputs?",
    "What is the fallback behavior when LLM output fails strict schema validation?",
    "What prompt-injection defenses are required for public channel agent control?",
    "What are the approved owner-only command channels and non-owner restrictions?",
    "What are the DM policy requirements for bots in Telegram?",
    "What are the public group moderation and mention/reply routing requirements?",
    "What should happen when Mission Control is unavailable during agent heartbeat loops?",
    "What are the required degraded-mode behaviors when Mission Control returns 404/401/5xx?",
    "What are the required heartbeat interval guards to prevent self-timeout storms?",
    "What duplicate ingress suppression rules are required for Telegram updates?",
    "What are the required model locks for Friday, Arsenal, Edith, and Jocasta?",
    "What is the approved runtime for Friday and how is thinking mode configured?",
    "What is the approved runtime for Arsenal and required fallback if unavailable?",
    "What are the required auth scopes for OpenClaw operator workflows?",
    "What changed in latest OpenClaw security patches that affects operator scopes?",
    "What are required rollout validation checks before enabling upgraded bot images?",
    "What canary criteria must pass before full bot fleet rollout?",
    "What logs/metrics are required to prove Telegram poller conflict resolution?",
    "What are required signals for confirming board delegation is healthy?",
    "What are the required acceptance tests for arena mode reviewer verdict flow?",
    "What are the required acceptance tests for Supermemory context injection in arena mode?",
    "What are required tests for preserving context after prompt truncation?",
    "What are required checks for NotebookLM CLI compatibility and profile fallback?",
    "What evidence fields are required in NotebookLM query audit logs?",
    "How should GSD spec-driven context be injected into final arena verdict prompts?",
    "What are the required reasons/tags when fallback routing is triggered?",
    "What are the mandatory rollout/rollback steps for production recovery incidents?",
    "What are the required operator dashboards and alert thresholds for this stack?",
    "What unresolved high-risk gaps remain for sniper production hardening right now?",
    "What should be the next three highest-priority tasks to reduce production risk this week?",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run 50-question NotebookLM sweep.")
    parser.add_argument("--notebook-id", required=True, help="NotebookLM notebook id.")
    parser.add_argument("--profile", default="auto", help="NotebookLM profile (default: auto).")
    parser.add_argument(
        "--output-md",
        default=str(REPO_ROOT / "docs" / "operations" / "2026-02-28-notebooklm-50q-results.md"),
        help="Markdown output path.",
    )
    parser.add_argument(
        "--output-json",
        default=str(BACKEND_ROOT / "artifacts" / "notebooklm_50q_results.json"),
        help="JSON output path.",
    )
    return parser


async def _run_sweep(notebook_id: str, profile: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx, question in enumerate(QUESTIONS, start=1):
        try:
            result = await query_notebook(notebook_id=notebook_id, query=question, profile=profile)
            rows.append(
                {
                    "index": idx,
                    "question": question,
                    "answer": result.answer,
                    "conversation_id": result.conversation_id,
                    "ok": True,
                    "error": result.error,
                }
            )
        except NotebookLMError as exc:
            rows.append(
                {
                    "index": idx,
                    "question": question,
                    "answer": "",
                    "conversation_id": None,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return rows


def _write_markdown(path: Path, notebook_id: str, profile: str, rows: list[dict[str, object]]) -> None:
    success_count = sum(1 for row in rows if bool(row.get("ok")))
    generated_at = datetime.now(UTC).isoformat()
    lines = [
        "# 2026-02-28 NotebookLM 50-Question Sniper Sweep",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Notebook ID: `{notebook_id}`",
        f"- Profile: `{profile}`",
        f"- Success: `{success_count}/{len(rows)}`",
        "",
        "| # | Status | Conversation ID | Question |",
        "|---|---|---|---|",
    ]
    for row in rows:
        status = "ok" if bool(row.get("ok")) else f"error: {row.get('error')}"
        conversation = str(row.get("conversation_id") or "")
        question = str(row.get("question") or "").replace("\n", " ").strip()
        lines.append(f"| {row.get('index')} | {status} | {conversation} | {question} |")
    lines.append("")
    lines.append("## Answers")
    lines.append("")
    for row in rows:
        idx = row.get("index")
        question = str(row.get("question") or "").strip()
        answer = str(row.get("answer") or "").strip()
        error = str(row.get("error") or "").strip()
        lines.append(f"### Q{idx}: {question}")
        lines.append("")
        if answer:
            lines.append(answer)
        elif error:
            lines.append(f"_error_: {error}")
        else:
            lines.append("_no answer returned_")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> int:
    args = _build_parser().parse_args()
    notebook_id = args.notebook_id.strip()
    profile = args.profile.strip() or "auto"
    if not notebook_id:
        raise SystemExit("--notebook-id is required")

    rows = asyncio.run(_run_sweep(notebook_id=notebook_id, profile=profile))
    _write_markdown(Path(args.output_md), notebook_id=notebook_id, profile=profile, rows=rows)
    _write_json(Path(args.output_json), rows=rows)
    success_count = sum(1 for row in rows if bool(row.get("ok")))
    print(f"NotebookLM sweep complete: {success_count}/{len(rows)} succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
