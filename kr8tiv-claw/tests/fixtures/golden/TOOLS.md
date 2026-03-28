# TOOLS

## Allow
- sessions.list
- sessions.send
- browser.read

## Deny
- shell.exec

## Elevated Mode
- disabled

## Mission Control Hooks
- resolve_pack_endpoint: http://mission-control:8000/api/v1/runtime/packs/resolve
- telemetry_endpoint: http://mission-control:8000/api/v1/runtime/runs
- token_file: /run/secrets/mission_control_token
- cross_tenant_learning: false
- cross_user_learning: false
