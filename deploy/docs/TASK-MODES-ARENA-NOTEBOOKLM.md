# Task Modes + Arena + NotebookLM Runbook

This runbook documents the Mission Control configuration needed for KR8TIV-style task execution modes:

- **task mode**: structured automated execution pipeline
- **arena**: multi-agent rounds with reviewer verdict loop
- **notebook** / **notebook_creation**: NotebookLM-assisted execution mode
- **arena_notebook**: arena flow with notebook context support

---

## 1) Required environment variables

Set these in your Mission Control stack (backend + worker):

```yaml
ARENA_ALLOWED_AGENTS: friday,arsenal,edith,jocasta
ARENA_REVIEWER_AGENT: arsenal
NOTEBOOKLM_RUNNER_CMD: uvx --from notebooklm-mcp-cli@latest nlm
NOTEBOOKLM_PROFILES_ROOT: /var/lib/notebooklm/profiles
NOTEBOOKLM_TIMEOUT_SECONDS: 120
```

> These are now included in `docker-templates/mission-control.yml`.

---

## 2) Arena reliability hardening checklist

When enabling arena execution at scale, enforce these controls:

1. **Participant preflight check**
   - verify each agent exists and has a live session
   - fail fast if *all* participants are unavailable
   - degrade gracefully if only some are unavailable

2. **Response polling with backoff**
   - poll history for new replies after dispatch
   - use bounded backoff (example: 2s, 4s, 8s, 16s, 30s)
   - fail with explicit error when no response arrives

3. **Reviewer verdict parsing**
   - require explicit `VERDICT: APPROVED` or `VERDICT: REVISE`
   - tolerate optional colon formatting (`VERDICT APPROVED` / `VERDICT: APPROVED`)

4. **Prompt/context truncation guard**
   - cap assembled round transcripts
   - keep task header + recent rounds when truncating

5. **Partial progress safety**
   - if iterations already exist, do **not** reset task to `inbox` on transient failure

---

## 3) NotebookLM operational notes

- Use a pinned command path in production (or `@latest` if you prefer auto-updates).
- Ensure worker container can access `NOTEBOOKLM_PROFILES_ROOT` with correct volume ownership.
- Keep timeout conservative (120s default) to avoid queue starvation.

---

## 4) Deployment verification

After deploy, verify:

```bash
# backend health
curl -fsS http://localhost:8100/healthz

# env wiring in backend
docker compose exec backend env | egrep 'ARENA_|NOTEBOOKLM_'

# env wiring in worker
docker compose exec webhook-worker env | egrep 'ARENA_|NOTEBOOKLM_'
```

Then run one task each in:
- `arena`
- `notebook`
- `arena_notebook`

Confirm execution comments and iteration artifacts are written as expected.

---

## 5) Known gotchas

- Missing/expired OpenClaw sessions will look like silent arena failures unless preflight checks are active.
- If NotebookLM runner binaries are unavailable in the worker image, notebook modes will fail quickly.
- Long transcripts can bloat queue payloads and cause unstable reviewer responses without truncation controls.
