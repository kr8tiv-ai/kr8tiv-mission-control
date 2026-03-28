# Operations Runbook

## 1) Build Secret-Free Boot Bundle

```powershell
python scripts/sanitize_openclaw_json.py --input-dir .\examples\raw --output-dir .\examples\sanitized
powershell -ExecutionPolicy Bypass -File .\scripts\build_boot_bundle.ps1 -SourceDir .\examples\sanitized -OutFile .\examples\kr8tiv-boot-bundle.zip
python scripts/validate_public_bundle.py --path .\examples\kr8tiv-boot-bundle.zip
```

## 2) Recovery Drill

1. Mark one agent offline in Mission Control / stop its container.
2. Run deterministic assignment:

```powershell
python scripts/assign_recovery_owner.py --down-agent FRIDAY --candidates ARSENAL JOCASTA EDITH
```

3. Confirm exactly one owner is selected.
4. Confirm owner can re-provision/restart target container.

## 3) Model Failover Drill

1. Simulate primary model unavailable.
2. Confirm runtime behavior follows `config/model-policy.public.yaml`.
3. Confirm no cross-provider route is selected unless explicitly listed as fallback for that agent.
4. Confirm service recovers or escalates without changing committed policy files.

## 4) Public Repo Hygiene

Run before every push:

```powershell
python scripts/validate_public_bundle.py --path .
```

Expected: no secret material detected.

## 5) Incident Log Minimum

For each outage:
- UTC timestamp
- down agent
- elected recovery owner
- recovery method used
- duration to restored heartbeat
- follow-up policy/document updates

## 6) Multi-Agent Recovery Smoke Protocol

Run a dry run before every release:

```bash
bash scripts/smoke_verify_recovery.sh --dry-run
```

Expected output includes:

- `CHECK telegram_ingress`
- `CHECK agent_health_matrix`
- `CHECK gsd_stage_guards`
- `CHECK recovery_under_120s`

Run live verification after deploy:

```bash
bash scripts/smoke_verify_recovery.sh
```
