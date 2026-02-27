# Telegram Ingress + Arena Matrix Check

Date: 2026-02-27  
Environment: local backend test harness (`sqlite+aiosqlite`)

## Scope

This validation pass covers two areas:

1. Telegram ingress safety controls
2. Arena/task-mode execution behavior across task types

## Telegram ingress policy matrix

Validated by tests in:
- `backend/tests/test_channel_ingress_policy.py`
- `backend/tests/test_board_webhooks_api.py`
- `backend/tests/test_board_memory_notifications.py`
- `backend/tests/test_board_group_memory_notifications.py`

Policy scenarios covered:
- Non-owner DM is blocked from processing/task direction
- Owner public-channel message requires mention or reply-to-bot
- Non-owner public message cannot issue task direction
- Prompt-injection patterns downgrade to no-task-direction
- Blocked ingress is persisted for audit but not enqueued for execution
- Public board/group chat fanout reaches all non-sender agents
- Sensitive snippets are redacted before agent fanout

## Arena/task-mode matrix

Validated by tests in:
- `backend/tests/test_task_mode_schema.py`
- `backend/tests/test_task_mode_arena_config.py`
- `backend/tests/test_task_mode_verdict.py`
- `backend/tests/test_task_mode_notebook_capability_gate.py`
- `backend/tests/test_task_mode_supermemory_callout.py`
- `backend/tests/test_task_mode_execution_dispatch.py`

Task mode scenarios covered:
- `standard` -> no-op
- `notebook` -> notebook executor path, status transition to `review`
- `arena` -> arena executor path, verdict loop handling
- `arena_notebook` -> arena path with notebook-aware compatibility
- `notebook_creation` -> notebook creation path
- Unsupported mode -> error comment + reset to `inbox`
- Failure with existing iterations -> retains `in_progress` (no work loss)
- Supermemory context behavior:
  - enabled -> injected
  - disabled -> skipped
  - lookup failure -> graceful continue
  - prompt truncation preserves context

## Command evidence

### Arena/task-mode suite

```bash
pytest backend/tests/test_task_mode_schema.py \
  backend/tests/test_task_mode_arena_config.py \
  backend/tests/test_task_mode_verdict.py \
  backend/tests/test_task_mode_notebook_capability_gate.py \
  backend/tests/test_task_mode_supermemory_callout.py \
  backend/tests/test_task_mode_execution_dispatch.py -q
```

Result: `25 passed`

### Telegram ingress + webhook/chat safety suite

```bash
pytest backend/tests/test_channel_ingress_rollout.py \
  backend/tests/test_channel_ingress_policy.py \
  backend/tests/test_board_webhooks_api.py \
  backend/tests/test_board_memory_notifications.py \
  backend/tests/test_board_group_memory_notifications.py -q
```

Result: `13 passed`

## Runtime config required for production intent

Set these in runtime env:

- `TELEGRAM_OWNER_USER_ID=<your telegram numeric id>`
- `TELEGRAM_BOT_USERNAME=<bot username>`
- `TELEGRAM_BOT_USER_ID=<bot numeric id>`
- `TELEGRAM_STRICT_DM_POLICY=true`
- `TELEGRAM_REQUIRE_OWNER_TAG_OR_REPLY=true`
- `TELEGRAM_REQUIRE_OWNER_FOR_TASK_DIRECTION=true`
- `TELEGRAM_ALLOW_PUBLIC_MODERATION=true`
