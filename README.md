# docker-beszel

Lightweight host + Docker monitoring for the homelab, replacing CheckMK
([docker-checkmk](https://github.com/Enucatl/docker-checkmk)).

Working docs:

- [plan.md](./plan.md) — architecture, phases, non-goals, success criteria
- [implementation_ledger.md](./implementation_ledger.md) — task status and evidence

## Stack

- **Beszel hub** (`henrygd/beszel:0.19.0`) — UI, history, alerts; Traefik
  `beszel.${DOCKER_DOMAIN}` + Authelia + `secured@file`
- **Local agent** (`henrygd/beszel-agent:0.19.0`) on `docker.home.arpa` — unix
  socket to hub; read-only Docker socket for container metrics
- **Remote agents** on `forbearance.home.arpa` and `proxmox.home.arpa` (later)
- **Alerts** — Telegram via Shoutrrr (later)

## Deployment

Copy `.env.example` to `.env` (or keep the project `.env` that sets
`COMPOSE_ENV_FILES=../.env` so `DOCKER_DOMAIN` comes from `/opt/docker/.env`).

```sh
docker compose up -d
```

- Public UI: `https://beszel.<DOCKER_DOMAIN>` (behind Authelia)
- Local agent hub URL: `http://127.0.0.1:8090` (loopback publish only)
- When adding the docker host in the UI, use Host/IP:
  `/beszel_socket/beszel.sock`
- Set `BESZEL_AGENT_TOKEN` / `BESZEL_AGENT_KEY` from the hub, then
  `docker compose up -d` again

## Security baseline

This compose project uses the shared
[docker-compose-security-baseline](https://github.com/Enucatl/docker-compose-security-baseline)
for common container hardening defaults, including capabilities, no-new-privileges,
memory/swap, and PID limits (`hardened-small` hub, `hardened-tiny` agent).
