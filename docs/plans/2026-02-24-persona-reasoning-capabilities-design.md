# Persona Integrity + Max Reasoning + Capabilities Platform Design

Date: 2026-02-24  
Owner: KR8TIV Mission Control  
Status: Approved (design)

## Goals
- Prevent identity drift in all agents while preserving distinct personalities.
- Enforce default max-capacity reasoning behavior per model.
- Support both deployment modes:
  - Team mode (with orchestrator).
  - Individual mode (no orchestrator).
- Provide installable capability management:
  - Skills.
  - Programming libraries.
  - Device/computer access via encrypted Tailscale paths.
  - Automation, voice, computer-control, and app-adapter install packs.
- Add customer-owned backup workflow (never stored by KR8TIV).
- Ensure each customer has access to their own Mission Control.
- Add onboarding Q&A that recommends the right persona/capability setup.
- Enforce tier-based storage and ability limits.
- Add customer change-request intake for post-onboarding modifications.

## Architectural Decision
Chosen approach: Hybrid (git + Mission Control runtime)

- Git repositories hold reusable preset personality packs and public templates.
- Mission Control is live source of truth for per-agent runtime policy and intake customization.
- Provisioning/sync writes runtime templates and enforces policy across OpenClaw workspaces.

## Deployment Modes
### Team Mode
- Uses lead orchestrator + specialist agents.
- Global policy and routing controlled by Mission Control.
- Recovery ownership remains deterministic (single elected owner).

### Individual Mode
- No orchestrator.
- Same persona, reasoning, security, and backup guardrails.
- Single agent still uses Mission Control board/task framework + optional NotebookLM.

## Persona Integrity Protocol
### Precedence (hard rule)
- `SOUL.md > USER.md > IDENTITY.md > AGENTS.md`

### Controls
- Store checksum baseline for `SOUL.md`, `USER.md`, `IDENTITY.md`, `AGENTS.md` per workspace.
- Run periodic drift check on heartbeat/provision sync interval.
- On drift:
  - Alert in Mission Control activity feed.
  - Auto-restore canonical content by policy (configurable strict mode).
- Restrict direct runtime config writes in chat/tooling paths.

### Personality Onboarding
- New `persona_presets` catalog (git-seeded, versioned).
- Intake flow supports:
  - Preset selection (including business archetypes).
  - Custom owner edits at onboarding.
- Persist final profile to:
  - `identity_profile`
  - `identity_template`
  - `soul_template`

### Onboarding Q&A Recommender
- Guided Q&A captures:
  - core use cases
  - communication preferences
  - automation appetite
  - device scope
  - safety posture
- System outputs:
  - recommended persona preset
  - recommended ability bundle
  - recommended voice configuration
  - recommended backup option set
- Personalized deployments auto-propose:
  - voice model enabled
  - computer/device automation capability (UPlay Chromium profile)
  - backup options wizard enabled

## Reasoning Policy (Default)
For all agents by default:
1. Attempt `max` reasoning.
2. If unsupported, use highest supported reasoning tier for that model/provider.
3. If reasoning tiers are unavailable, use model default behavior.

### Enforcement points
- Provisioning-time heartbeat/model config sync.
- Runtime policy sync on agent heartbeat.
- Template sync reconciliation for drift correction.

## Capabilities Module
Add Mission Control `Capabilities` domain with three catalogs:

### 1) Skills Catalog
- Skill package id/version/source.
- Required permissions and risk level.
- Install/rollback metadata.

### 2) Library Catalog
- Approved language libraries + pinned versions.
- Policy tags (`allowed`, `requires_approval`, `blocked`).
- Dependency and vulnerability metadata.

### 3) Device Access Catalog (Tailscale)
- Registered devices/services with owner + environment tags.
- Agent-scope ACL mapping.
- Connection mode via secure access broker only.

## Secure Access Broker (Tailscale)
- No raw Tailscale secrets in agent workspace files.
- Broker issues short-lived access grants.
- Access policy defaults to `ask_first`.
- Every remote action/session is audited:
  - actor
  - target device
  - reason
  - approval state
  - timestamps

## Install & Abilities Module
Support package classes:
- `automation`
- `voice`
- `computer_control` (including UFO3-style control packs)
- `app_adapter`

Each package includes signed manifest:
- id/version
- permissions
- dependencies
- install/uninstall steps
- verification checks
- rollback steps

Default install policy:
- Owner approval required (`ask_first`) before execution.

### Tier Quotas
- Enforce per-tier limits for:
  - max active abilities
  - storage allocation
  - optional max connected devices
- Over-limit actions are blocked with explicit upgrade/guidance messaging.

## Break-Glass Override
- Allowed actors: owner + approved concierge admin.
- Allowed contexts: outage/security incident only.
- Controls:
  - mandatory reason
  - short TTL override session
  - full audit entry
  - automatic return to normal `ask_first` mode
  - mandatory post-incident review

## Backup Protocol (Customer-Owned)
- Backups are initiated by customer and stored where customer chooses.
- KR8TIV does not store backup payloads.
- Mission Control prompts backup twice weekly via:
  - Mission Control UI
  - Telegram/WhatsApp fallback reminder
- Prompt includes explicit warning:
  - declining backups increases risk of irreversible data loss.
- Store only backup confirmation metadata (no payload):
  - timestamp
  - destination type (local path/cloud account chosen by owner)
  - confirmation status

### Backup Options
- Customer chooses backup destination per policy-safe option:
  - local drive path
  - external/attached drive
  - customer-owned cloud connector
  - manual export package
- KR8TIV stores destination metadata only, never backup content.

## Change Request Workflow
- Add customer-facing request form for:
  - add/remove abilities
  - persona adjustments
  - voice model changes
  - device automation scope changes
- Track request lifecycle:
  - submitted
  - triage
  - approved/rejected
  - applied

## Customer Mission Control Access
- Each customer receives isolated Mission Control tenancy/workspace.
- Access controls:
  - tenant-scoped roles
  - tenant data isolation by default
  - no cross-tenant mutation paths
- Team and individual deployments both map into tenant-scoped control plane.

## Data Model Additions (Conceptual)
- `persona_presets`
- `persona_versions`
- `agent_persona_bindings`
- `capability_packages`
- `capability_installations`
- `library_catalog`
- `device_catalog`
- `device_access_grants`
- `backup_reminders`
- `backup_confirmations`
- `override_sessions`
- `tier_quotas`
- `ability_slots`
- `change_requests`
- `onboarding_answers`
- `onboarding_recommendations`

## API Surface Additions (Conceptual)
- `GET/POST /api/v1/persona/presets`
- `POST /api/v1/agents/{id}/persona/apply`
- `POST /api/v1/agents/{id}/persona/verify`
- `GET/POST /api/v1/capabilities/packages`
- `POST /api/v1/capabilities/installations`
- `GET/POST /api/v1/devices`
- `POST /api/v1/devices/{id}/access/request`
- `POST /api/v1/backups/reminders/run`
- `POST /api/v1/backups/confirm`
- `GET /api/v1/tier/quotas`
- `POST /api/v1/change-requests`
- `GET /api/v1/change-requests/{id}`
- `POST /api/v1/onboarding/qa/start`
- `POST /api/v1/onboarding/qa/answer`
- `GET /api/v1/onboarding/qa/recommendation`
- `POST /api/v1/override/start`
- `POST /api/v1/override/end`

## Security + Compliance
- Secretless git policy remains mandatory.
- Runtime secret injection only.
- Audit logs immutable/append-only in practice (operational policy).
- Approval events linked to actor identity and request reason.

## Rollout Strategy
1. Read-only baseline checks (already in artifacts).
2. Implement persona precedence + checksum verification without auto-restore.
3. Enable auto-restore in canary tenants.
4. Enable reasoning default enforcement in canary.
5. Release capabilities catalogs + owner approval workflow.
6. Enable backup reminder workflow.
7. Roll out per-customer Mission Control tenancy defaults.

## Acceptance Criteria
- Identity files remain stable across restarts/syncs unless approved mutation occurs.
- Max reasoning fallback policy is enforced and observable in runtime config.
- Skills/libraries/device installs require owner approval by default.
- Tailscale access occurs only through brokered, audited sessions.
- Backup reminders fire twice weekly and record owner confirmation metadata.
- Every customer can access isolated Mission Control instance/tenant.
- Onboarding Q&A produces persona + ability recommendations that map to tier limits.
- Personalized deployments default to voice + UPlay Chromium automation + backup options.
- Tier quotas prevent over-allocation of abilities/storage with clear customer feedback.
- Change requests are audited and applied only through approved workflows.
