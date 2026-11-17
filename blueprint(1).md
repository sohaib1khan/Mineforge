# MineForge — Build Blueprint

> A self-hosted, containerized control panel for a Minecraft **Bedrock** Dedicated Server:
> safe world switching, backups & restore, add-on management, users, metrics, and hosting tools —
> in a calm, Minecraft-flavored, mobile-first PWA.

---

## 0. Instructions for Cursor (read first, follow always)

1. **Build phase by phase** (Section 17). Finish a phase, meet its acceptance criteria, then stop and summarize before starting the next. Never skip ahead or half-build future phases.
2. **Keep the project clean and well structured.** Follow the folder layout in Section 5 exactly. One responsibility per module. No god-files. No dead code, no commented-out blocks, no leftover debug prints.
3. **Business logic lives in `services/`**, never in route handlers or React components. Routes validate input, call a service, return a response.
4. **Typed everywhere:** Python type hints + Pydantic schemas; TypeScript `strict: true`. No `any`.
5. **Small, readable functions.** Clear names. Docstrings on every service function explaining what it does and what can fail.
6. **Tests ship with features.** Every service gets unit tests; risky flows (switch, backup, restore, add-on apply) get integration tests with rollback cases.
7. **Never hardcode secrets, IPs, gamertags, domains, or passwords.** Config comes from environment variables (see `.env.example`). Never write real values into code, tests, docs, or fixtures.
8. **Never commit** anything listed in Section 15. Check `git status` before every commit.
9. **No shell=True, no string-built shell commands.** Use library APIs (Docker SDK, `zipfile`, `tarfile`, `pathlib`).
10. **Ask before changing a locked decision** in Section 2.
11. Keep `README.md` and `docs/` updated at the end of each phase.

---

## 1. Goals

- **Switch worlds safely**, with a guarantee: you either land on the new world fully working, or you are automatically put back on the previous one.
- **Backup & restore** that are automatic, verified, and one click.
- **Web UI** with first-run admin setup, admin + regular users.
- **Add-on (pack) management in the browser** — no more `scp`/`mv`. Upload, enable/disable per world, test with auto-revert.
- **Server/hosting tools** inside the dashboard (status, console, network/port settings, allowlist, help guides).
- **Metrics dashboard** (who's playing, playtime, resource usage; in-game stats later).
- **Containerized:** one `docker compose up -d` brings up the app + Bedrock server.
- **Calm, smooth, mobile-first PWA** with a light Minecraft feel.

---

## 2. Locked decisions

| Area | Decision |
|---|---|
| Name | **MineForge** (keep the display name in ONE config constant + `manifest.webmanifest` so it can be renamed, e.g. to "MineScroll") |
| Backend | Python 3.12, **FastAPI**, SQLModel/SQLAlchemy, **SQLite**, Alembic migrations |
| Frontend | **React + Vite + TypeScript + Tailwind**, Framer Motion, TanStack Query, React Router |
| PWA | `vite-plugin-pwa` (installable, offline app shell) |
| Server control | **App container + Bedrock container (`itzg/minecraft-bedrock-server`) + locked-down Docker socket proxy.** App never mounts `/var/run/docker.sock` directly. |
| First run | "Create admin" page, protected by a **one-time setup code printed in the app container logs** |
| Regular users | Can switch worlds; **blocked while other players are online unless all agree**; admin can force. Can change own password. |
| Add-ons | Browser upload, auto-detect BP/RP pairs, warnings (missing half, Marketplace/encrypted, needs experiments), **per-world profiles**, **test with auto-revert** |
| Metrics | Phase 7: basic (logs + Docker stats). Later phase: in-game telemetry add-on |
| Backups | Nightly + before every switch/restore/add-on change; keep 7 days (configurable); verified; one-click restore. Off-site (rclone) = later phase |
| Server page | Status, console, version info, network/NetherNet settings, public IP check, allowlist & ops, gamerules, built-in help guides |
| Look | Calm deepslate/moss/sky palette, pixel-style headings, clean body text, subtle animation, dark + light, mobile-first |
| Packaging | Single app image (FastAPI serves the built SPA), multi-stage Dockerfile |

---

## 3. Architecture

```
                 Browser / installed PWA (phone, PC)
                               │ HTTPS (via your reverse proxy)
                               ▼
┌──────────────────────── docker compose ────────────────────────┐
│                                                                │
│  mineforge (app)  ── FastAPI + built React SPA, port 8080      │
│     │   │                                                      │
│     │   └── internal network ──► socket-proxy ──► docker.sock  │
│     │        (start/stop/restart/attach/logs/stats only)       │
│     │                                                          │
│     └── shared volume /data ◄──────────────┐                   │
│                                            │                   │
│  bedrock (itzg/minecraft-bedrock-server) ──┘                   │
│     TCP 19132 (NetherNet signaling)                            │
│     UDP 19140-19155 (NetherNet game traffic)                   │
└────────────────────────────────────────────────────────────────┘
```

- **Shared volume** `/data` = the Bedrock server's data dir (worlds, packs, `server.properties`, `allowlist.json`). The app reads/writes it.
- **App-owned volume** `/app-data` = SQLite DB, backups, uploaded pack library, logs.
- **Console commands** are sent by writing to the Bedrock container's stdin via the Docker **attach** API (the itzg `send-command` helper fails when the container runs with a custom UID — don't use it).
- **Live logs/progress** stream to the browser over **Server-Sent Events** (or WebSocket for the console).
- **One operation at a time:** a global operation lock (DB row + in-process lock) guards switch/backup/restore/add-on apply.

---

## 4. Tech details

**Backend:** FastAPI, Uvicorn, SQLModel, Alembic, Pydantic v2, `docker` (Python SDK), `argon2-cffi`, APScheduler, `zstandard`, `httpx`, `slowapi` (rate limiting), `structlog`, pytest + pytest-asyncio.

**Frontend:** React 18, Vite, TypeScript (strict), Tailwind, Radix UI primitives (accessible dialogs/menus), Framer Motion, TanStack Query, React Router, Recharts (metrics), `vite-plugin-pwa`, Vitest + Testing Library, Playwright (a few e2e smoke tests).

**Fonts (self-hosted, no CDN — needed for offline PWA):** a pixel font for headings (e.g. *Silkscreen*, OFL) + *Inter* for body text.

---

## 5. Project structure

```
mineforge/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app factory, router mounting, static SPA serving
│   │   ├── core/                   # config.py, security.py, logging.py, errors.py
│   │   ├── db/                     # session.py, base.py
│   │   ├── models/                 # SQLModel tables (one file per entity)
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── deps.py             # auth/role dependencies
│   │   │   └── routes/             # auth, setup, users, worlds, addons, backups,
│   │   │                           # server, console, metrics, operations, audit
│   │   ├── services/
│   │   │   ├── docker_client.py    # ONLY place that talks to Docker
│   │   │   ├── console.py          # send command, read responses
│   │   │   ├── logwatch.py         # parse server log: joins/leaves, started, errors
│   │   │   ├── server_props.py     # safe read/write of server.properties
│   │   │   ├── operations.py       # lock, job state machine, rollback orchestration
│   │   │   ├── worlds.py
│   │   │   ├── addons.py           # parse, validate, pair, apply profiles
│   │   │   ├── backups.py
│   │   │   ├── metrics.py
│   │   │   ├── network.py          # public IP lookup, port config
│   │   │   └── archive_safety.py   # safe zip/tar extraction (see Section 12)
│   │   └── workers/scheduler.py    # nightly backups, retention, metric sampling
│   ├── migrations/                 # Alembic
│   ├── tests/  (unit/ integration/ fixtures/  — fixtures use fake data only)
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                    # router, providers, layout shell
│   │   ├── components/ui/          # buttons, cards, dialogs, toasts (design system)
│   │   ├── features/               # auth, setup, dashboard, worlds, addons, backups,
│   │   │                           # server, console, users, metrics, help, settings
│   │   ├── lib/                    # api client, sse helpers, formatters
│   │   ├── styles/                 # tokens.css (theme variables), fonts
│   │   └── main.tsx
│   ├── public/                     # icons, manifest assets (original art only)
│   └── vite.config.ts
├── deploy/
│   ├── docker-compose.yml
│   └── .env.example                # placeholders only, never real values
├── docs/                           # architecture.md, operations.md, security.md, user-guide.md
├── .github/
│   ├── workflows/ci.yml            # lint, typecheck, test, build, gitleaks
│   └── dependabot.yml
├── .cursor/rules/                  # copy of Section 0 + Section 15 as project rules
├── Dockerfile                      # multi-stage: build SPA → python runtime, non-root
├── .dockerignore
├── .gitignore
├── .pre-commit-config.yaml         # gitleaks, ruff, black, eslint, prettier
├── SECURITY.md
└── README.md
```

---

## 6. Data model (SQLite)

- **User** — id, username (unique), password_hash (argon2id), role (`admin`|`player`), is_active, must_change_password, created_at, last_login_at
- **Session** — id, user_id, token_hash, csrf_token, created_at, expires_at, ip, user_agent
- **World** — id, display_name, folder_name (unique), description, gamemode, difficulty, seed, size_bytes, is_active, created_at, last_played_at, needs_experiments (bool)
- **Addon** — id, name, pack_uuid, version, kind (`behavior`|`resource`), pair_addon_id, source_filename, sha256, size_bytes, flags (missing_pair, encrypted, needs_beta_apis), uploaded_by, created_at, notes
- **WorldAddon** — world_id, addon_id, enabled, load_order
- **Backup** — id, world_id, kind (`scheduled`|`manual`|`pre_switch`|`pre_restore`|`pre_addon`), path, size_bytes, sha256, verified, created_at, created_by
- **Operation** — id, type (`switch`|`backup`|`restore`|`addon_apply`|`addon_test`), status (`queued`|`running`|`succeeded`|`failed`|`rolled_back`), params (json), started_by, started_at, finished_at, log (text), rollback_performed
- **PlayerSession** — id, gamertag, xuid, joined_at, left_at, world_id
- **MetricSample** — ts, cpu_pct, mem_bytes, net_rx, net_tx, players_online
- **AuditLog** — ts, user_id, action, target, details (json), ip
- **Setting** — key, value (e.g. backup retention, player switch rules, theme default)

---

## 7. Roles & permissions

| Action | Admin | Player |
|---|:-:|:-:|
| View dashboard, worlds, status | ✅ | ✅ |
| Switch world | ✅ (can force) | ✅ (rules below) |
| Change own password | ✅ | ✅ |
| Users CRUD, reset passwords | ✅ | ❌ |
| Worlds create/import/rename/clone/export/delete | ✅ | ❌ |
| Add-ons upload/enable/disable/delete/test | ✅ | ❌ |
| Backups create/restore/delete | ✅ | create only (configurable) |
| Console, server.properties, network, allowlist/ops | ✅ | ❌ |
| Settings, audit log | ✅ | ❌ |

**Player switch rules:** allowed only if no *other* players are online, or every online player has tapped "OK" on a switch request in the UI (request expires after 2 min). Configurable cooldown (default 10 min) between switches. Admin "Force switch" shows a warning listing online players.

---

## 8. The safety engine (the "guarantee")

All risky actions run through `services/operations.py` as a **job** with a state machine, a global lock, a streamed log, and automatic rollback.

**Switch world (A → B):**
1. **Pre-flight:** acquire lock; B exists and is valid (`level.dat`, `db/`); enough free disk (≥ 2× world size); permission rules (Section 7) pass.
2. **Warn players** in-game (`say` via console), 30-second countdown (admin can skip).
3. **Backup A** live: `save hold` → poll `save query` until ready → copy listed files, truncating each to the length `save query` reports → `save resume`. Archive as `.tar.zst`, record sha256, **verify** by listing the archive. If backup fails → abort, nothing changed.
4. **Stop** the Bedrock container cleanly (`stop` command, then container stop with timeout).
5. **Switch:** set `level-name` in `server.properties`; write B's add-on profile into `world_behavior_packs.json` / `world_resource_packs.json` (**merge** B's world-embedded packs + enabled profile, see Section 14).
6. **Start** and **health-check:** within 120 s the log shows `Server started`, the Pack Stack matches the expected packs, and TCP 19132 is listening.
7. **Success** → mark B active, release lock, audit log.
   **Failure at 5–6** → **rollback:** stop, restore A's `server.properties` + pack JSONs, start A, health-check, mark job `rolled_back`, show the reason.

**Restore backup:** take a `pre_restore` backup first → stop → extract to a temp dir (safe extraction) → atomic swap of the world folder → start → health-check → on failure swap back.

**Add-on apply / test:** `pre_addon` backup of the pack JSONs → apply → restart → health-check. **Test mode:** after success the UI shows "Keep or revert?" with a countdown (default 10 min); no answer = automatic revert.

Rules: every step is logged to the Operation and streamed to the UI; any unexpected exception triggers rollback; the lock is always released (`finally`).

---

## 9. Features by page

- **First-run Setup:** shown only when no users exist; requires the setup code from container logs; creates the admin; the code is invalidated after use.
- **Login:** username/password, rate limited, lockout after repeated failures.
- **Dashboard:** server status (online/offline, version, uptime), active world card, players online, last backup, quick actions (Switch world, Backup now), recent operations.
- **Worlds:** grid of world cards (icon from `world_icon.jpeg`, size, last played, add-on count, warnings). Actions: Switch, Create (name/seed/gamemode/difficulty), Import `.mcworld`, Export/Download, Rename, Clone, Delete (admin, auto-backup first).
- **Add-ons:** library table with name, version, BP/RP pairing, flags, used-by-worlds. Upload `.mcaddon`/`.mcpack` (drag & drop, multiple). Per-world tab: toggle, reorder, Apply, Test. Clear warnings (Section 14).
- **Backups:** list per world (kind, size, verified ✓), Backup now, Restore, Download, Delete, retention settings.
- **Server:** status & controls (start/stop/restart), live **console** (send commands, live output), `server.properties` editor (safe whitelisted keys with descriptions), gamerules quick toggles, allowlist & ops management, version info, **Network** panel (public IP check, NetherNet ports, reachability help).
- **Metrics:** see Section 10.
- **Users (admin):** CRUD, role, reset password (forces change on next login), deactivate.
- **Account:** change own password, theme preference.
- **Help:** built-in guides (Section 13).
- **Audit log (admin):** filterable list of who did what.

---

## 10. Metrics

**Phase 7 (basic):**
- From logs: players online, sessions, playtime per player (day/week), joins over time.
- From Docker stats (sampled every 30 s, 30-day retention): CPU, memory, network.
- From disk: world sizes, backup storage used.
- Charts: online players timeline, playtime leaderboard, CPU/RAM sparklines, backup history.

**Later phase (in-game telemetry):** an optional MineForge behavior pack using `@minecraft/server-net` (BDS only; must be allowed in the server's `config/` permissions) that POSTs entity counts, loaded chunks, and tick timing to an internal app endpoint authenticated with a per-install token. Off by default.

---

## 11. UI / UX & theme

- **Feel:** calm, smooth, uncluttered. Minecraft flavor through color, pixel headings, and subtle block motifs — **not** loud.
- **Palette tokens (dark):** background *deepslate* `#1E2226`, surface *stone* `#2A3035`, border `#3A4248`, text `#E8ECEF`, muted `#9AA5AD`, primary *moss* `#6FA86A`, accent *sky* `#7FB7D9`, warning *sand* `#E3C77A`, danger *redstone* `#D9645B`. Provide matching **light** tokens. All colors as CSS variables in `styles/tokens.css`.
- **Type:** pixel font for page titles and stat numbers only; Inter for everything else (readability).
- **Motion:** 150–250 ms ease-out, gentle fades/slides, skeleton loaders; respect `prefers-reduced-motion`.
- **Mobile-first:** bottom tab bar on phones, sidebar on desktop; touch targets ≥ 44 px; works one-handed.
- **PWA:** installable, offline app shell + "Server unreachable" state, app icons in all sizes.
- **Accessibility:** WCAG AA contrast, keyboard navigation, focus rings, labelled controls.
- **Legal:** original art only — no Mojang logos, textures, or trademarks; footer note "Not affiliated with Mojang or Microsoft."

---

## 12. Security requirements

- Passwords: **argon2id**; min length 12; never logged.
- Sessions: httpOnly, Secure, SameSite=Strict cookies; server-side session table; 7-day expiry; logout invalidates; CSRF token on all state-changing requests.
- Login rate limiting + temporary lockout; generic error messages.
- First-run setup code: random, single-use, printed once to logs, expires after use.
- Role checks in API dependencies (never only in the UI).
- Security headers (CSP, X-Frame-Options, Referrer-Policy); CORS off by default.
- **Uploads:** size limit (configurable, default 512 MB), allowed extensions only (`.mcaddon .mcpack .mcworld .zip`), **safe extraction**: reject absolute paths, `..`, symlinks; cap entry count and total uncompressed size (zip-bomb protection); extract to temp dir then move.
- All filesystem paths resolved and confirmed inside allowed roots.
- Docker access only through the socket proxy, with only the endpoints needed; the app only ever targets the configured Bedrock container name.
- Containers run as non-root; read-only root filesystem for the app where possible.
- Audit log for every admin action and every operation.
- Intended to sit behind a reverse proxy with HTTPS; document optional Cloudflare Access / LAN-only exposure.

---

## 13. Hosting resources inside the app

**Help guides (in-app, markdown rendered):**
- Connecting from phone and PC (Servers → Add Server, address, port 19132).
- Port forwarding for NetherNet: **TCP 19132 + UDP 19140–19155** to the host.
- DNS: the game record must be **DNS-only** (not proxied by Cloudflare); proxies only carry HTTP.
- Version matching: server and clients must be on the same version; how to pin.
- Mobile carriers: some (IPv6-only / strict CGNAT) can't reach home servers — Wi-Fi works; options explained.
- Add-ons: BP + RP halves, Marketplace limits, experiments.
- Console basics: `list`, `give`, `tp`, `gamerule`, `op` (player must be online).

**Network panel:** shows current public IP, configured `server-udp-ports`, a "re-detect public IP" action (rewrites `server-udp-ports` and restarts), and a checklist of required forwards.

---

## 14. Bedrock gotchas (must be handled — learned the hard way)

1. **NetherNet transport:** `transport=nethernet`, signaling on **TCP** `server-port` (19132), game traffic on a **UDP range**. For internet players `server-udp-ports` must advertise the **public IP**: `<PUBLIC_IP>:19140-19155:19140-19155`. Docker must publish `19132/tcp` and `19140-19155/udp`.
2. **The itzg image rewrites `server.properties` from env vars on every start.** Only set `EULA`, `VERSION`, `UID`, `GID`, `TZ`, `TRANSPORT`, `SERVER_PORT`, `SERVER_UDP_PORTS` via env. **Do not set `LEVEL_NAME`, `GAMEMODE`, `DIFFICULTY`, etc. via env** — MineForge owns those keys in `server.properties`, otherwise switches get silently overwritten.
3. `SERVER_UDP_PORTS` supports the `<public_ip>` placeholder resolved at container start; the app should also detect and display the resolved IP.
4. **Version pinning:** `VERSION=LATEST` updates on every restart and can leave phones behind. Pin by default; the UI shows server version and explains client matching.
5. **World-embedded packs:** imported worlds can carry packs in their own `behavior_packs/` and `resource_packs/` folders. When writing a world's pack JSONs, **merge** embedded packs with the enabled profile — never overwrite them away.
6. **Marketplace / encrypted packs** cannot load on a dedicated server. Detect and flag them on upload or world import, and explain why.
7. **RP-only uploads:** if a pack has only the resource half, flag "missing behavior pack."
8. **Experiments (e.g. Beta APIs)** live in `level.dat` and can't be toggled from the server; flag packs that need beta script modules and tell the user to enable experiments in-game before importing the world.
9. **Player data doesn't transfer** from single-player to server (local player vs. per-account keys). Warn on world import.
10. **`op`/`give` need the player online.** Console UI should show online players to pick from.
11. **Gamertags** may have suffixes; allowlist must match exactly.
12. **Permissions:** Bedrock container runs as UID/GID from env; the app must preserve ownership on files it writes in `/data`.
13. **Large packs** (100+ MB) slow phone joins; show pack sizes and a total "download size" per world.
14. Some add-on dialogs don't render buttons on certain PC clients — not fixable server-side; mention in Help.

---

## 15. GitHub & data safety (non-negotiable)

**`.gitignore` must include at least:**
```
.env
.env.*
!.env.example
*.db
*.sqlite*
/data/
/app-data/
/backups/
*.tar.zst
*.tgz
*.mcworld
*.mcaddon
*.mcpack
server.properties
allowlist.json
permissions.json
bedrock_server*
*.log
node_modules/
dist/
__pycache__/
.venv/
.DS_Store
```

**Rules:**
- Commit only `.env.example` with placeholder values (`CHANGE_ME`, `example.com`, `203.0.113.10`). Never real IPs, domains, gamertags, xuids, passwords, or tokens — not in code, tests, docs, screenshots, or commit messages.
- **Never commit Minecraft server binaries, worlds, or add-ons** (Mojang EULA + creators' licenses + personal data).
- No default credentials anywhere; the admin is created at first run.
- Install **pre-commit with gitleaks**; CI also runs gitleaks and fails on any finding.
- Enable **GitHub secret scanning + push protection** and **Dependabot**.
- Test fixtures use obviously fake data (`player_one`, `TestWorld`).
- Screenshots for README must be scrubbed of IPs, gamertags, and domains.
- If a secret is ever committed: rotate it first, then purge history — deleting the file is not enough.

---

## 16. Docker & configuration

**Containers:** `mineforge` (app), `bedrock` (`itzg/minecraft-bedrock-server`), `socket-proxy` (e.g. `tecnativa/docker-socket-proxy`, internal network only, only container/attach/logs/stats endpoints enabled).

**Volumes:** `bedrock-data` → `/data` (both containers), `mineforge-data` → `/app-data` (app only).

**Ports:** app `8080` (behind your reverse proxy); bedrock `19132/tcp`, `19140-19155/udp`.

**`.env.example` (placeholders):**
```
MINEFORGE_PUBLIC_URL=https://mineforge.example.com
MINEFORGE_SECRET_KEY=CHANGE_ME_LONG_RANDOM
MINEFORGE_BEDROCK_CONTAINER=bedrock
MINEFORGE_BACKUP_RETENTION_DAYS=7
MINEFORGE_UPLOAD_MAX_MB=512
TZ=America/Los_Angeles
BEDROCK_VERSION=CHANGE_ME_PINNED_VERSION
BEDROCK_UID=1000
BEDROCK_GID=1000
SERVER_UDP_PORTS=<public_ip>:19140-19155:19140-19155
```

**Migration from an existing setup:** a documented import path for an existing itzg data folder (worlds, packs, allowlist) without data loss.

---

## 17. Build phases

Each phase includes its backend, its UI pages, tests, and doc updates. Stop after each phase with a summary.

**Phase 0 — Repo & guardrails**
Project structure (Section 5), `.gitignore`, `.dockerignore`, pre-commit (gitleaks, ruff, black, eslint, prettier), CI workflow, Dependabot, `.cursor/rules`, README skeleton, `SECURITY.md`, `.env.example`.
✅ `pre-commit run --all-files` and CI pass on an empty skeleton; gitleaks blocks a fake secret.

**Phase 1 — Foundation, auth & users**
Config, DB + migrations, models, first-run setup with log-printed code, login/logout, sessions + CSRF, rate limiting, roles, users CRUD, change own password, audit log. Frontend: app shell, theme tokens, fonts, Setup, Login, Account, Users pages.
✅ Fresh install requires the setup code; second setup attempt is rejected; player cannot reach admin APIs (tested).

**Phase 2 — Server control & console**
`docker_client` via socket proxy, status/start/stop/restart, console via attach (send + live stream), log watcher (started, joins/leaves → PlayerSession), `server.properties` safe editor, allowlist & ops. Frontend: Dashboard (status), Server page, Console.
✅ Console `list` returns online players; joins/leaves recorded; editing a whitelisted property survives restart.

**Phase 3 — Operations engine & backups**
Operation lock + state machine + SSE progress, live backup with `save hold/query/resume`, verification, retention, scheduler, restore with pre-restore backup and automatic swap-back. Frontend: Backups page, live operation progress drawer.
✅ Backup taken while a player is online restores cleanly; a forced failure mid-restore rolls back automatically (tested).

**Phase 4 — Worlds & safe switching**
World library, create/import (`.mcworld`, safe extraction, warnings)/export/rename/clone/delete, active world, full switch flow (Section 8) with player rules and rollback. Frontend: Worlds page, switch dialog with countdown and live progress.
✅ Switch A→B works; a deliberately broken world B triggers rollback to A with a clear reason.

**Phase 5 — Add-on manager**
Upload, parse manifests, BP/RP pairing, flags (missing half, encrypted/Marketplace, beta APIs), library, per-world profiles, merge with world-embedded packs, apply, test with keep/auto-revert, `texturepack-required` toggle, pack size totals. Frontend: Add-ons page + per-world tab.
✅ Uploading an RP-only pack shows the warning; test mode auto-reverts when not confirmed; embedded world packs are preserved (tested).

**Phase 6 — UI polish & PWA**
Full theme (dark/light), motion, mobile bottom nav, skeletons, empty states, toasts, accessibility pass, PWA install + offline shell, icons.
✅ Lighthouse PWA installable; usable at 360 px width; keyboard-only navigation works; reduced-motion respected.

**Phase 7 — Metrics**
Docker stats sampling, session aggregation, charts, retention. Frontend: Metrics page + dashboard widgets.
✅ Charts render with real data; sampling doesn't noticeably load the server.

**Phase 8 — Hosting tools & Help**
Network panel (public IP detect, NetherNet ports, re-detect + restart), version info and pinning guidance, Help guides (Section 13).
✅ Changing public IP updates `server-udp-ports` and the server restarts healthy.

**Phase 9 — Hardening & release**
Security review against Section 12, test coverage on services ≥ 80%, restore drill documented, docs complete, multi-arch image build (optional publish to GHCR), migration guide from an existing itzg setup.
✅ Clean install from README on a fresh VM works end to end.

**Later (backlog)**
In-game telemetry pack; off-site backups (rclone to NAS/cloud, optional encryption); notifications (Discord/webhook) for crashes, switches, backups; multiple simultaneous Bedrock servers; scheduled world rotation.

---

## 18. Out of scope

- Java Edition servers / plugins (Multiverse, Paper, Geyser).
- Marketplace content on the server (not technically possible).
- Editing player inventories / world data in the database.
