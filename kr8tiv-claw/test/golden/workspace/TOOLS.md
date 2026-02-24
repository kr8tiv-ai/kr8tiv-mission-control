# TOOLS

## Policy
- Allowlist:
- web.search
- fs.read
- Denylist:
- shell.exec
- Sandbox non-main sessions: true

## Secret Handling
- Allowed in workspace:
- OPENCLAW_GATEWAY_TOKEN
- Redaction rules:
- redact api keys

## Supermemory
- Enabled: true
- API env key: SUPERMEMORY_API_KEY
- Base URL: https://api.supermemory.ai
- topK: 5
- threshold: 0.5
