# Rollout Gate Ops Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an operator-safe script to update rollout gate secrets (`RUNTIME_HEALTH_URLS`, optional `RUNTIME_ROLLBACK_COMMAND`) and optionally run a `gate_only` publish workflow dispatch.

**Architecture:** Add a standalone Python script under `scripts/ci/` with small pure functions for parsing/execution and a thin GitHub Actions API client using PAT auth. Unit tests load the script module directly and validate parsing plus orchestration behavior without network calls.

**Tech Stack:** Python 3.12, stdlib HTTP (`urllib`), Git credential manager token fallback, PyNaCl sealed-box encryption for GitHub Actions secrets, pytest.

---

### Task 1: Add Failing Tests for Rollout Ops Script

**Files:**
- Test: `backend/tests/test_rollout_gate_ops.py`

**Step 1: Write the failing tests**

- Parse and validate health URL list.
- Ensure rollout config execution writes required secret values.
- Ensure optional rollback secret write behavior.
- Ensure optional gate-only workflow dispatch behavior.

**Step 2: Run tests to verify fail**

Run: `uv run pytest backend/tests/test_rollout_gate_ops.py -q`  
Expected: FAIL due missing script implementation.

### Task 2: Implement Rollout Ops Script

**Files:**
- Create: `scripts/ci/rollout_gate_ops.py`

**Step 1: Add minimal implementation for tests**

- `RolloutOpsConfig` dataclass
- `parse_health_urls(...)`
- `execute_config(...)`
- `GitHubActionsApi` with secret write + workflow dispatch helpers

**Step 2: Add CLI entrypoint**

- Parse args for owner/repo/workflow, health URLs, rollback command updates, and gate dispatch.
- Resolve token from env first, then `git credential fill`.

**Step 3: Run tests to verify pass**

Run: `uv run pytest backend/tests/test_rollout_gate_ops.py -q`  
Expected: PASS.

### Task 3: Document Operator Usage

**Files:**
- Modify: `docs/production/runtime-image-policy.md`

**Step 1: Add concise usage section**

- Include example command to rotate health URLs.
- Include example command to set rollback command + dispatch gate-only validation.

### Task 4: Apply Live Secret Update + Validate

**Files:**
- N/A (runtime operation)

**Step 1: Set rollback secret and run gate-only dispatch**

Run script with owner/repo and target workflow to update secrets and dispatch gate-only check.

**Step 2: Verify latest workflow run succeeds**

- Confirm run id and conclusion via GitHub API.
