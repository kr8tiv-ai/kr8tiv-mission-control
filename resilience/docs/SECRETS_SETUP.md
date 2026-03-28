# Secrets Setup for Production Deploy

This repository deploy workflow requires GitHub environment `production`.

## Required Secrets

- `VPS_HOST`: public server hostname or IP.
- `VPS_USER`: SSH user with Docker permissions.
- `VPS_SSH_KEY`: private key in PEM/OpenSSH format.
- `DEPLOY_ROOT`: directory on host containing the compose project.

## Optional Variable

- `COMPOSE_FILE`: compose filename (defaults to `compose.yml`).

## Environment Protection

- Require manual approval for `production`.
- Restrict who can trigger `workflow_dispatch`.
- Rotate `VPS_SSH_KEY` if access scope changes.
