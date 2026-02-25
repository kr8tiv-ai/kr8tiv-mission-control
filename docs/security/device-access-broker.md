# Device Access Broker Policy

This policy governs high-risk computer/device access capabilities (for example Tailscale access, browser automation, and remote control modules such as UPlay Chromium workflows).

## Core Rules

- Default installation mode is `ask_first`.
- High-risk install/enable actions require explicit owner approval.
- Emergency bypass is allowed only through time-bound break-glass override sessions.
- Override sessions require:
  - a non-empty reason,
  - bounded TTL,
  - auditable start/end events.

## Capability Catalog Requirements

All device-access capabilities must be registered with:

- `capability_type=device`,
- risk level classification,
- scoped access metadata (tenant-local by default),
- ownership and review traceability.

## Secure Access Baseline

- Prefer encrypted network paths (for example Tailscale or equivalent private mesh).
- Never persist raw credentials in workspace files or git.
- Use secret-file or managed secret injection at runtime.
- Restrict automation capability activation to approved bundles per tenant tier.

## Operational Safeguards

- Tier quotas gate installation volume and storage impact before activation.
- Break-glass sessions do not remove logging requirements.
- Recovery automation must not bypass owner approval policies for non-emergency changes.
