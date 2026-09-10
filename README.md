# docker-beszel

Lightweight host + Docker monitoring for the homelab, replacing CheckMK
([docker-checkmk](https://github.com/Enucatl/docker-checkmk)).

Working docs:

- [plan.md](./plan.md) — architecture, phases, non-goals, success criteria
- [implementation_ledger.md](./implementation_ledger.md) — task status and evidence

## Stack

- **Beszel hub** (`henrygd/beszel:0.19.0`) — UI, history, alerts; Traefik
  `beszel.${DOCKER_DOMAIN}` + `secured@file` + Authelia OIDC (Grafana-style SSO)
- **Binary agents** on all Debian hosts via Puppet `os/Debian.yaml`
  (`profile::beszel_agent` + systemd as FreeIPA user `beszel` / `nologin`).
  Fleet: `docker`, `forbearance`, `proxmox`, `proxmox-cortex`, `complex`.
  On `docker.home.arpa` the agent is in the local `docker` group and reads
  `/var/run/docker.sock` directly (no compose socket-proxy; Traefik’s proxy is
  for containers, not bare-metal agents)
- **Alerts** — Telegram via Shoutrrr (same CheckMK bot/chat; URL in
  `secrets/beszel_telegram_shoutrrr` and hub Settings → Notifications).
  Rules: Status (down) on docker+proxmox only (not forbearance /
  proxmox-cortex / complex); CPU 90% / 10m; Memory 95% / 10m; Disk 95% / 5m
  on all hosts; Temperature 80°C / 5m on proxmox + proxmox-cortex;
  ContainerHealth on docker (Docker unhealthy status)

## Resource footprint

Measured 2026-09-08 (RSS / container stats), five agents + hub:

| Component | RAM |
|-----------|-----|
| Hub (`beszel` container) | ~18 MiB (capped at 256 MiB) |
| Agent `docker` | ~16 MiB |
| Agent `forbearance` | ~14 MiB |
| Agent `proxmox` | ~15 MiB |
| Agent `proxmox-cortex` | ~15 MiB |
| Agent `complex` | ~15 MiB |
| **Beszel total** | **~92 MiB** |

CheckMK (Ultimate site on docker) was using around **2 GiB** for the same
homelab monitoring job.

## Deployment

Copy `.env.example` to `.env` (or keep the project `.env` that sets
`COMPOSE_ENV_FILES=../.env` so `DOCKER_DOMAIN` comes from `/opt/docker/.env`).

```sh
docker compose up -d --wait beszel
docker compose run --rm alerts-init
```

The tracked [config.yml](./config.yml) is Beszel's native startup configuration
for the complete system inventory. It intentionally omits agent tokens so
normal redeploys preserve the existing fingerprint records in `beszel_data`.
It is not a fresh-database recovery file; do not remove systems from it unless
they should be removed from Beszel.

The tracked [alerts.yml](./alerts.yml) is the exact alert policy. The one-shot
`alerts-init` service applies it through Beszel's API after the hub is healthy,
including removing managed alerts that are absent from the file. It uses the
gitignored `secrets/beszel_admin_password` only at deployment time and exits
after reconciliation.

- Public UI: `https://beszel.<DOCKER_DOMAIN>` (LAN allowlist + Authelia OIDC SSO)
- Agent `HUB_URL` (all hosts): `https://beszel-agent.<DOCKER_DOMAIN>`
  (Traefik: agent-connect path only; LAN allowlist; no Authelia)
- Docker host agent: default Docker socket (`unix:///var/run/docker.sock`)
- Hub admin: FreeIPA `user@home.arpa` via Authelia OIDC (password login
  disabled). PocketBase superuser break-glass:
  `admin@docker.home.arpa` + `secrets/beszel_admin_password` (gitignored).
  OIDC client secret: `secrets/oidc_client_secret` (Authelia digest under
  `/opt/docker/authelia/secrets/oidc_beszel_client_secret_digest`).

## Binary agent (Puppet)

Agents are **not** installed via `get.beszel.dev` (local `beszel` user
conflicts with FreeIPA). Use `profile::beszel_agent` in
[puppet-control-repo](https://github.com/Enucatl/puppet-control-repo):

1. FreeIPA user `beszel` (`nologin`) via `freeipa_users::users` on docker;
   SSSD makes it available on all hosts. On the Docker host,
   `freeipa_users::user_groups` adds `beszel` to `docker`.
2. Hub KEY + universal TOKEN → Vault `kv/puppet` as
   `profile::beszel_agent::key` / `profile::beszel_agent::token`
3. Hiera: class in `os/Debian.yaml`; shared `hub_url` / `version` / `user` in
   `common.yaml`; `enable_docker_metrics: true` on the Docker host only
4. Puppet installs `/usr/local/bin/beszel-agent`, writes
   `/etc/beszel-agent/{key,token}`, and enables `beszel-agent.service`
   as FreeIPA `beszel`

Same-host and remotes share the agent hostname. UI stays on `beszel.<DOCKER_DOMAIN>`.

## Security baseline

This compose project uses the shared
[docker-compose-security-baseline](https://github.com/Enucatl/docker-compose-security-baseline)
for common container hardening defaults (`hardened-small` hub).
