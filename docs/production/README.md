# Production Notes

- [Auto-improve control plane](./AUTO_IMPROVE_CONTROL_PLANE.md)
- [OpenClaw baseline configuration](../openclaw_baseline_config.md)
- [OpenClaw 15-point harness](../openclaw_15_point_harness.md)

## Reliability Gates

- Mission Control enforces GSD stage transitions (`spec -> plan -> execute -> verify -> done`).
- Individual-mode high-risk transitions require owner approval before execution.
- Telegram is enabled in phase-1; WhatsApp remains disabled until phase-2 rollout.

## Cross-Repo Smoke Verification

Use the resilience repo smoke script after production deploy:

```bash
bash scripts/smoke_verify_recovery.sh --dry-run
```
