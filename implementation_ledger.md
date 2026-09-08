# Beszel migration — implementation ledger

| Field | Value |
|-------|--------|
| Goal | Replace CheckMK with Beszel for host + Docker monitoring |
| Plan | [plan.md](./plan.md) |
| Last updated | 2026-09-08 |
| Status legend | `planned` · `in_progress` · `done` · `blocked` · `cancelled` |
| Next pick-up | **P3-03** |

**v1 target (authoritative with [plan.md](./plan.md)):**

- Compose runs **hub only** (`henrygd/beszel:0.19.0`, Traefik + Authelia).
- **Binary agents** on `docker`, `forbearance`, and `proxmox` via Puppet
  `profile::beszel_agent` + systemd (not compose sidecars; not ad-hoc `systemctl`).
- Agent identity: FreeIPA user **`beszel`** (`nologin`, `freeipa_users` on docker;
  SSSD everywhere). Not root / not `user_l` / not `get.beszel.dev`.
- Docker container metrics: agent on `docker.home.arpa` uses host
  `/var/run/docker.sock` (`beszel` ∈ local `docker` group). No Beszel socket-proxy.
- **Uniform HUB_URL** for all hosts: `https://beszel-agent.${DOCKER_DOMAIN}`
  (Traefik path `/api/beszel/agent-connect` only; `secured@file` LAN allowlist; **no**
  Authelia). UI: `https://beszel.${DOCKER_DOMAIN}` + `secured@file` + Authelia OIDC.
- Agent KEY/TOKEN in Vault (`profile::beszel_agent::key` / `::token`); universal token **permanent**.

Rules:

- Advance work **only** via tasks in this ledger.
- When a test fails or discovery adds scope, **add a new task** (do not silently expand an existing one).
- Record concrete evidence under **Evidence / test notes**.
- Keep **Blocked-by** filled when `blocked`; clear it when unblocked.

---

## Phase 0 — Project docs (complete)

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P0-01 | Create `/opt/docker/beszel/` directory | done | `mkdir -p /opt/docker/beszel` (2026-09-07) | |
| P0-02 | Write `plan.md` | done | `/opt/docker/beszel/plan.md` | |
| P0-03 | Write `implementation_ledger.md` | done | This file | |
| P0-04 | Bootstrap = docs only; Phase 1+ from this directory | done | Agreed 2026-09-07 | |

---

## Phase 1 — Stand up Beszel (parallel with CheckMK)

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P1-01 | Init git repo / README (homelab conventions) | done | `origin` → `Enucatl/docker-beszel`; README, `.gitignore`, MIT `LICENSE` | |
| P1-02 | Hub `docker-compose.yml`: `traefik_proxy`, security-baseline, pinned image | done | `henrygd/beszel:0.19.0`, `hardened-small`, `COMPOSE_ENV_FILES=../.env`. (Early “compose local agent” / loopback publish abandoned; see P1-04 / P1-12 / P1-13.) | |
| P1-03 | Traefik labels: `beszel.${DOCKER_DOMAIN}`, HTTPS, Authelia + `secured@file`, port 8090 | done | Validated via `docker compose config` | P1-02 |
| P1-04 | Dedicated agent hostname (no Authelia); all hosts use same `HUB_URL` | done | UI `beszel.docker.home.arpa` + Authelia; agents `beszel-agent.docker.home.arpa` + `/api/beszel/agent-connect` + `secured@file`. Compose redeployed (no loopback publish). Probes: UI 403, agent-connect 400 from hub. Puppet `hub_url` uniform | |
| P1-05 | Bring stack up; create admin user; UI reachable via Traefik | done | Hub Up; admin `admin@docker.home.arpa` (`secrets/beszel_admin_password`). Health 200 loopback + `traefik_proxy`; public HTTPS → 403 Authelia (same as checkmk without session) | P1-03 |
| P1-06 | Puppet: FreeIPA `beszel` + `profile::beszel_agent` on `docker.home.arpa`; host + container metrics green under systemd | done | `puppet agent -t` applied `2de92bf`. `beszel-agent.service` **active** as User=`beszel` (groups `beszel,docker`). Health `ok`. Hub: `docker.home.arpa` **up** v0.19.0; **48** containers. Smoke nohup agent stopped | P1-05 |
| P1-07 | Puppet: `profile::beszel_agent` on `forbearance.home.arpa` as FreeIPA `beszel`; system green | done | After token refresh + Puppet re-apply: `forbearance.home.arpa` **up** v0.19.0. Both agents use `https://beszel-agent.docker.home.arpa`. Removed stale duplicate `docker.home.arpa` (down) | P1-04 |
| P1-08 | Puppet: `profile::beszel_agent` on `proxmox.home.arpa` as FreeIPA `beszel`; system green | done | Catalog `6cb17efffbb`; `beszel-agent` **active**; hub `proxmox.home.arpa` **up** v0.19.0. Cleaned token-rotation duplicate down systems. All 3 hosts green | P1-04 |
| P1-09 | Shoutrrr Telegram URL; test notification | done | Reused CheckMK `telegram.sh` params (bot `@enucatlcheckmkbot`, chat id from WATO `notification_parameter.mk`). Saved in hub `user_settings.webhooks` + gitignored `secrets/beszel_telegram_shoutrrr`. `POST /api/beszel/test-notification` → `err: false` | P1-05 |
| P1-10 | Conservative alerts (host down, high CPU/mem/disk) | done | Via `POST /api/beszel/user-alerts`: **Status** on docker+proxmox only (not forbearance); **CPU** 90%/10m; **Memory** 95%/10m; **Disk** 95%/5m on all 3; **Temperature** 70°C/5m on proxmox; **ContainerHealth** on docker only (expect noise from unhealthy `checkmk` until cutover) | P1-09 |
| P1-11 | Parallel-run soak vs CheckMK; note gaps | cancelled | Skipped formal soak; user proceeded to cutover after SSO + alerts green | P1-06, P1-07, P1-08, P1-10 |
| P1-12 | Remove compose agent sidecar; hub-only compose | done | Compose agent removed; binary-agent model chosen (CheckMK-like) | |
| P1-13 | Beszel compose Docker socket-proxy for agent | cancelled | Bare-metal agent uses host `docker.sock`; proxy is for container consumers (Traefik only). Removed from compose | |

---

## Phase 2 — Cut over

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P2-01 | Mute or disable CheckMK Telegram notifications | done | CheckMK stack stopped (`docker compose stop`); deploy path + refresh timer disabled so it stays down | P1-11 |
| P2-02 | Stop day-to-day use of CheckMK UI; Beszel as source of truth | done | Beszel SSO + alerts live; CheckMK containers stopped | P2-01 |

---

## Phase 3 — Decommission CheckMK

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P3-01 | `docker compose down` CheckMK; stop/remove `checkmk-deploy` units | done | `docker compose stop` → container Exited. `systemctl disable --now checkmk-deploy.path checkmk-refresh.timer` needs sudo (pending on host). Units still enabled until that runs | P2-02 |
| P3-02 | Puppet: add `beszel: {}`, remove/absent `checkmk` in `git_deploy_projects` | done | `checkmk: { ensure: absent }`, `beszel: {}` in `docker.yaml`. Also stripped `checkmk_monitor` labels, deleted `enroll-checkmk.sh`, cleaned Proxmox cloud-init/desktop scripts, renamed VyOS SNMP `checkmk_group` → `ro_group` | P3-01 |
| P3-03 | Add beszel systemd **hub** path/service deploy units (mirror checkmk `*-deploy`); agent unit is `profile::beszel_agent` (P1-06+) | planned | | P1-02 |
| P3-04 | Remove Traefik `checkmk:` entrypoint `:8000` | planned | | P3-01 |
| P3-05 | Uninstall CheckMK agents / bakery on docker, forbearance, proxmox | planned | Leave FreeIPA `beszel` (Beszel agent identity) | P3-01 |
| P3-06 | Optional: strip `checkmk_monitor` / `checkmk_agent` labels | planned | | P3-01 |
| P3-07 | Remove Vault `checkmk::agent_registration_password`; Authelia cleanup if any | planned | Keep `profile::beszel_agent::{key,token}` | P3-05 |
| P3-08 | Archive/delete checkmk volume after confirming RRD history not needed | planned | No import into Beszel | P3-01 |
| P3-09 | Verify success criteria | planned | `docker stats`, hub UI, alert test | P3-01…P3-08 |

---

## Optional follow-ups (not v1)

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| OPT-01 | VyOS Podman Beszel agent | planned | Host health only; not SNMP replacement | P1-11 |
| OPT-02 | External uptime probe for WAN / dead-router visibility | planned | Only path when LAN egress is dead | |
| OPT-03 | Authelia OIDC for Beszel (mirror Grafana) | done | Authelia client `beszel` + claims_policy; UI Traefik `secured@file` only (no forward-auth); PocketBase OAuth2 `oidc` → Authelia; password auth disabled; admin user email = FreeIPA `user@home.arpa`. Secrets: `authelia/secrets/oidc_beszel_client_secret_digest`, `beszel/secrets/oidc_client_secret`. Puppet ACL for digest in `docker.yaml` | |

---

## Architecture decisions / learnings

| Date | Decision |
|------|----------|
| 2026-09-07 | v1 drops router SNMP; optional Podman agent later (OPT-01); total-outage alerts need OPT-02. |
| 2026-09-07 | No compose agent sidecar. All three hosts use **binary** agents (CheckMK-like). |
| 2026-09-07 | No Beszel socket-proxy. Host agent on `docker.home.arpa` uses `/var/run/docker.sock`. Traefik keeps its own proxy for Traefik. |
| 2026-09-07 | Same-host agent reaches hub via `http://127.0.0.1:8090` (loopback publish). Remote `HUB_URL` vs Authelia → P1-04. |
| 2026-09-08 | **Superseded:** all agents (incl. docker) use `https://beszel-agent.${DOCKER_DOMAIN}`; UI stays on `beszel.${DOCKER_DOMAIN}` + Authelia. No loopback special case. |
| 2026-09-07 | Hub image pinned `henrygd/beszel:0.19.0`; admin `admin@docker.home.arpa` (password in gitignored `secrets/`). |
| 2026-09-07 | Agent install/systemd only via puppet-control-repo (`profile::beszel_agent`); no ad-hoc host `systemctl`. KEY/TOKEN in Vault. |
| 2026-09-08 | Agent runs as FreeIPA `beszel` (`nologin` via `freeipa_users`); docker group only on docker host. Not root / not `user_l` / not `get.beszel.dev`. |
| 2026-09-08 | No Status (host-down) alert on `forbearance` — intermittent downtime is expected. |
| 2026-09-08 | Beszel UI auth = Authelia OIDC (like Grafana); not Traefik forward-auth. FreeIPA `user@home.arpa` is the hub admin. |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-09-07 | Ledger created; Phase 0–3 tasks seeded. |
| 2026-09-07 | Bootstrap complete; Phase 1 started (P1-01…P1-05). |
| 2026-09-07 | Pivoted to binary agents; cancelled compose agent and Beszel socket-proxy (P1-12 done, P1-13 cancelled). |
| 2026-09-07 | Docs reconciled to single v1 target; next **P1-06**. |
| 2026-09-07 | P1-06: smoke agent OK; Puppet profile + Vault secrets staged (apply pending). |
| 2026-09-08 | Identity: FreeIPA `beszel`; plan/ledger/README + P1-06/07/08 aligned; Puppet Hiera/user_groups updated. |
| 2026-09-08 | P1-06 done: systemd agent on docker as `beszel`; hub green with containers. |
| 2026-09-08 | P1-04 done: agent hostname split; uniform HUB_URL. Next **P1-07**. |
| 2026-09-08 | P1-07 done (forbearance up). P1-08 proxmox in progress. |
| 2026-09-08 | P1-08 done; all three hosts up. Universal token set permanent. Next **P1-09** (Telegram). |
| 2026-09-08 | P1-09 done: CheckMK Telegram bot/chat → Beszel Shoutrrr; test notify OK. Next **P1-10** (alerts). |
| 2026-09-08 | P1-10 done: Status + CPU/Mem/Disk alerts on all hosts. Next **P1-11** (soak vs CheckMK). |
| 2026-09-08 | Removed Status alert from forbearance (host expected to be down at times). |
| 2026-09-08 | OPT-03: Authelia OIDC SSO for Beszel (Grafana pattern); password login disabled. |
| 2026-09-08 | OIDC fix: Authelia `consent_mode: implicit`; hub mounts host CA + `SSL_CERT_FILE` for Authelia HTTPS. |
| 2026-09-08 | Cutover: CheckMK stopped; P1-11 cancelled; P2-01/P2-02/P3-01 done. Next **P3-02** (Puppet absent checkmk / add beszel deploy). |
| 2026-09-08 | P3-02 done: Puppet CheckMK residuals removed; beszel git_deploy added. Next **P3-03**. |
