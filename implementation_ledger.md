# Beszel migration — implementation ledger

| Field | Value |
|-------|--------|
| Goal | Replace CheckMK with Beszel for host + Docker monitoring |
| Plan | [plan.md](./plan.md) |
| Last updated | 2026-09-07 (P1-01) |
| Status legend | `planned` · `in_progress` · `done` · `blocked` · `cancelled` |
| Scope boundary | **This bootstrap only:** directory + `plan.md` + this ledger. All Phase 1+ work is resumed **from inside `/opt/docker/beszel`** (open that project / chat there). |

Rules:

- Advance work **only** via tasks in this ledger.
- When a test fails or discovery adds scope, **add a new task** (do not silently expand an existing one).
- Record concrete evidence under **Evidence / test notes** (commands, URLs, observed RSS, alert delivery, etc.).
- Keep **Blocked-by** filled when `blocked`; clear it when unblocked.
- Do not implement compose, agents, Puppet, or CheckMK teardown from the checkmk workspace; continue here.

---

## Phase 0 — Project docs (bootstrap complete)

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P0-01 | Create `/opt/docker/beszel/` directory | done | `mkdir -p /opt/docker/beszel` (2026-09-07) | |
| P0-02 | Write `plan.md` (architecture, phases, non-goals, success criteria) | done | File present at `/opt/docker/beszel/plan.md` | |
| P0-03 | Write `implementation_ledger.md` seeded with Phase 0–3 + optional tasks | done | This file | |
| P0-04 | Confirm bootstrap-only scope; resume Phase 1+ from this directory | done | Agreed 2026-09-07: scaffold = dir + plan/ledger markdown only; no compose/runtime in bootstrap | |

---

## Phase 1 — Stand up Beszel (parallel with CheckMK)

Resume from `/opt/docker/beszel`. Next task to pick up: **P1-02**.

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P1-01 | Init git repo / README for `/opt/docker/beszel` (homelab project conventions) | done | Git already present (`origin` → `Enucatl/docker-beszel`). Expanded README (plan/ledger links, target stack, deploy stub, security-baseline note); added `.gitignore` (`.env`/`*.swp`/`secrets`) and MIT `LICENSE` to match peer stacks | |
| P1-02 | Add `docker-compose.yml`: hub + local agent (unix socket), `traefik_proxy`, security-baseline limits, pinned images | planned | Mirror patterns from `/opt/docker/checkmk/docker-compose.yml` and Beszel same-host socket docs | |
| P1-03 | Traefik labels: `beszel.${DOCKER_DOMAIN}`, HTTPS, Authelia + `secured@file`, correct hub port | planned | | P1-02 |
| P1-04 | Decide agent→hub path if Authelia blocks WebSocket/API (split router vs internal URL) | planned | Record chosen approach here after first agent connect attempt | P1-03 |
| P1-05 | Bring stack up; create admin user; UI reachable via Traefik | planned | | P1-03 |
| P1-06 | Register `docker.home.arpa`; confirm host metrics + Docker container list | planned | Expect containers currently tagged `checkmk_monitor=true` to appear via docker.sock (Beszel monitors all containers unless filtered) | P1-05 |
| P1-07 | Install agent on `forbearance.home.arpa`; system green in hub | planned | Binary or container; `HUB_URL` / `KEY` / `TOKEN` | P1-05 |
| P1-08 | Install agent on `proxmox.home.arpa`; system green in hub | planned | | P1-05 |
| P1-09 | Configure Shoutrrr Telegram notification URL; send test notification | planned | Reuse CheckMK bot/chat if available | P1-05 |
| P1-10 | Enable conservative alerts (host down, high CPU/mem/disk) | planned | Prefer less noise than CheckMK SSL/label churn | P1-09 |
| P1-11 | Parallel-run soak (days): compare signal vs CheckMK; note gaps in Open questions | planned | | P1-06, P1-07, P1-08, P1-10 |

---

## Phase 2 — Cut over

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P2-01 | Mute or disable CheckMK Telegram notifications | planned | Beszel is primary alert path | P1-11 |
| P2-02 | Stop day-to-day use of CheckMK UI; use Beszel as source of truth | planned | | P2-01 |

---

## Phase 3 — Decommission CheckMK

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| P3-01 | `docker compose down` CheckMK; stop/remove `checkmk-deploy` systemd units | planned | | P2-02 |
| P3-02 | Puppet: add `beszel: {}`, remove or mark absent `checkmk` in `git_deploy_projects` | planned | `puppet-control-repo/data/nodes/docker.yaml` | P3-01 |
| P3-03 | Add beszel systemd path/service deploy units (mirror checkmk) | planned | | P1-02 |
| P3-04 | Remove Traefik `checkmk:` entrypoint `:8000` from `traefik/data/traefik.yml` | planned | Agent receiver no longer needed | P3-01 |
| P3-05 | Uninstall CheckMK agents / bakery packages on docker, forbearance, proxmox | planned | | P3-01 |
| P3-06 | Optional: strip `checkmk_monitor=true` / `checkmk_agent=true` labels across compose projects | planned | Cosmetic once CheckMK is gone | P3-01 |
| P3-07 | Remove Vault `checkmk::agent_registration_password` when unused; Authelia URL cleanup if any | planned | | P3-05 |
| P3-08 | Archive/delete checkmk repo volume `checkmk_monitoring` after confirming RRD history not needed | planned | No import into Beszel | P3-01 |
| P3-09 | Verify success criteria: RAM reclaimed; no CheckMK dependency; 3 hosts + containers + Telegram OK | planned | `docker stats`, hub UI, alert test | P3-01…P3-08 |

---

## Optional follow-ups (not v1)

| ID | Task | Status | Evidence / test notes | Blocked-by |
|----|------|--------|----------------------|------------|
| OPT-01 | VyOS Podman Beszel agent (`allow-host-networks`, state under `/config`) | planned | Host health only; not SNMP replacement | P1-11 |
| OPT-02 | External uptime probe for WAN / dead-router visibility | planned | Only path that works when LAN egress is dead | |
| OPT-03 | Authelia OIDC for Beszel (mirror Grafana client pattern) | planned | | P1-05 |

---

## Open questions / learnings

| Date | Note |
|------|------|
| 2026-09-07 | Bootstrap complete (dir + plan + ledger). Phase 1+ resumes from this directory; next pick-up **P1-01**. |
| 2026-09-07 | Router SNMP dropped for v1; Podman agent optional (OPT-01). Total outage alerts need OPT-02. |
| 2026-09-07 | Risk: Authelia may interfere with agent `HUB_URL` on public hostname — resolve under P1-04. |
| 2026-09-07 | P1-01: repo init already done before ledger work; README/gitignore/LICENSE brought in line with checkmk/grafana-loki peers. Next: **P1-02**. |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-09-07 | Ledger created; P0-01…P0-03 marked done; remaining tasks seeded as planned. |
| 2026-09-07 | Scope clarified: bootstrap = scaffold + markdown only; P0-04 done; Phase 1+ deferred to beszel workspace. |
| 2026-09-07 | P1-01 done: README + `.gitignore` + `LICENSE`; next pick-up **P1-02**. |
