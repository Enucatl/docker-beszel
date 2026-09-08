# docker-beszel

Lightweight host + Docker monitoring for the homelab, replacing CheckMK
([docker-checkmk](https://github.com/Enucatl/docker-checkmk)).

Working docs:

- [plan.md](./plan.md) — architecture, phases, non-goals, success criteria
- [implementation_ledger.md](./implementation_ledger.md) — task status and evidence

## Stack

- **Beszel hub** (`henrygd/beszel:0.19.0`) — UI, history, alerts; Traefik
  `beszel.${DOCKER_DOMAIN}` + Authelia + `secured@file`
- **Binary agents** on all monitored hosts (`docker`, `forbearance`, `proxmox`) —
  Puppet `profile::beszel_agent` + systemd as FreeIPA user `beszel` (`nologin`).
  On `docker.home.arpa` the agent is in the local `docker` group and reads
  `/var/run/docker.sock` directly (no compose socket-proxy; Traefik’s proxy is
  for containers, not bare-metal agents)
- **Alerts** — Telegram via Shoutrrr (later)

## Deployment

Copy `.env.example` to `.env` (or keep the project `.env` that sets
`COMPOSE_ENV_FILES=../.env` so `DOCKER_DOMAIN` comes from `/opt/docker/.env`).

```sh
docker compose up -d
```

- Public UI: `https://beszel.<DOCKER_DOMAIN>` (behind Authelia)
- Same-host agent `HUB_URL`: `http://127.0.0.1:8090` (loopback publish only)
- Docker host agent: default Docker socket (`unix:///var/run/docker.sock`)
- Local admin: `admin@docker.home.arpa` (password in
  `secrets/beszel_admin_password`, gitignored)

## Binary agent (Puppet)

Agents are **not** installed via `get.beszel.dev` (local `beszel` user
conflicts with FreeIPA). Use `profile::beszel_agent` in
[puppet-control-repo](https://github.com/Enucatl/puppet-control-repo):

1. FreeIPA user `beszel` (`nologin`) via `freeipa_users::users` on docker;
   SSSD makes it available on all hosts. On the Docker host,
   `freeipa_users::user_groups` adds `beszel` to `docker`.
2. Hub KEY + universal TOKEN → Vault `kv/puppet` as
   `profile::beszel_agent::key` / `profile::beszel_agent::token`
3. Per-node Hiera: `hub_url`, `system_name`, `version` (pin to hub tag),
   and `enable_docker_metrics: true` on the Docker host
4. Puppet installs `/usr/local/bin/beszel-agent`, writes
   `/etc/beszel-agent/{key,token}`, and enables `beszel-agent.service`
   as FreeIPA `beszel`

Same-host example is in `data/nodes/docker.yaml`. Remotes
(`forbearance`, `proxmox`) get the same class with a public/internal
`HUB_URL` once P1-04 is settled.

## Security baseline

This compose project uses the shared
[docker-compose-security-baseline](https://github.com/Enucatl/docker-compose-security-baseline)
for common container hardening defaults (`hardened-small` hub).
