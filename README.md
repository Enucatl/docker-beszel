# docker-beszel

Lightweight host + Docker monitoring for the homelab, replacing CheckMK
([docker-checkmk](https://github.com/Enucatl/docker-checkmk)).

Working docs:

- [plan.md](./plan.md) — architecture, phases, non-goals, success criteria
- [implementation_ledger.md](./implementation_ledger.md) — task status and evidence

## Stack (target)

- **Beszel hub** — UI, history, alerts; Traefik `beszel.${DOCKER_DOMAIN}` + Authelia
- **Local agent** on `docker.home.arpa` — unix socket to hub; read-only Docker socket for container metrics
- **Remote agents** on `forbearance.home.arpa` and `proxmox.home.arpa`
- **Alerts** — Telegram via Shoutrrr

Compose and runtime land in Phase 1 of the ledger (`P1-02` onward). Until then this
repo holds the migration plan and tracking only.

## Deployment

Once `docker-compose.yml` exists, copy `.env.example` to `.env`, set `DOCKER_DOMAIN`,
then:

```sh
docker compose up -d
```

UI: `https://beszel.<DOCKER_DOMAIN>` (behind Authelia).

## Security baseline

This compose project will use the shared
[docker-compose-security-baseline](https://github.com/Enucatl/docker-compose-security-baseline)
for common container hardening defaults, including capabilities, no-new-privileges,
memory/swap, and PID limits.
