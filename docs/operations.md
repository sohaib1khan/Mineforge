# Operations

MineForge runs entirely via Docker.

```bash
./deploy/mf test
./deploy/mf up              # app + socket-proxy
./deploy/mf up bedrock      # also start Bedrock
./deploy/mf setup-code
./deploy/mf smoke
./deploy/mf logs
./deploy/mf down
```

UI: http://localhost:18080 (`MINEFORGE_HOST_PORT`).

## Phase 2 notes

- Socket proxy is always started with the app.
- Bedrock is optional until you run `./deploy/mf up bedrock`.
- Do **not** set `LEVEL_NAME` / `GAMEMODE` / `DIFFICULTY` on the Bedrock service env — MineForge owns those in `server.properties`.
- Console commands use Docker attach stdin.

## Phase 3 notes

- **Backup now** (any signed-in user) backs up the active `level-name` world.
- Live backups work while players are online (save hold/query/resume).
- Restore is admin-only; a pre-restore backup is taken first; failures roll the world folder back.
- Retention: `MINEFORGE_BACKUP_RETENTION_DAYS` (default 7); newest backup per world is kept.
- Nightly backup runs at 05:15 UTC; retention at 06:00 UTC.
- Only one risky operation runs at a time (global lock).

## Phase 4 notes

- Worlds page lists folders under `/data/worlds` and syncs DB rows.
- Switch always takes a pre-switch backup of the current world when valid.
- `MINEFORGE_SWITCH_COUNTDOWN_SECONDS` (default 30), `MINEFORGE_SWITCH_COOLDOWN_MINUTES` (default 10).
- Admins can force switch / skip countdown while players are online.
- Do not set `LEVEL_NAME` via Bedrock env — MineForge writes `level-name` in `server.properties`.

## Phase 5 notes

- Pack library: `/app-data/packs`. Applied packs sync into `/data/behavior_packs` and `/data/resource_packs`.
- Pack-library backups: `/app-data/addon-backups` (`.tar.zst` + manifest). Restore takes a safety backup first.
- `MINEFORGE_ADDON_TEST_MINUTES` (default 10) controls test-mode auto-revert.
- Apply/test take a pre-addon backup and roll pack JSON files back on failure.
- Encrypted/Marketplace packs are flagged and skipped when writing pack stacks.

## Phase 6 notes

- Theme preference is stored in the browser (`mineforge-theme`); toggle from Account or the shell.
- PWA: install from the browser when served over HTTPS (or localhost). Offline shell caches static assets; `/api/*` is never cached.
- Offline / server-unreachable banner polls `/api/health` while online.
- Rebuild the app image after frontend changes so the service worker and icons ship (`./deploy/mf up` rebuilds).

## Phase 7 notes

- Metrics sampling: `MINEFORGE_METRICS_ENABLED` (default true), `MINEFORGE_METRICS_SAMPLE_SECONDS` (default 30), `MINEFORGE_METRICS_RETENTION_DAYS` (default 30).
- Samples store CPU %, memory, network counters, and players online; prune daily at 06:30 UTC.
- Charts need a few samples before they fill in — wait ~30s after start, or open Metrics after the server has been up.
- Sampling uses one-shot Docker stats (not a streaming attach) to keep load low.

## Phase 8 notes

- Network panel (Server, admin): Detect / Re-detect & apply writes `server-udp-ports` to `PUBLIC_IP:19140-19155:19140-19155` and restarts Bedrock.
- Public IP lookup URL: `MINEFORGE_PUBLIC_IP_LOOKUP_URL` (default `https://api.ipify.org`). The app container needs outbound HTTPS for detect/apply unless you enter an IP manually.
- Prefer `SERVER_UDP_PORTS='<public_ip>:19140-19155:19140-19155'` in compose so itzg can also re-resolve on start; MineForge still writes the concrete property value.
- Pin `BEDROCK_VERSION` (not `LATEST`) in `deploy/.env`; Server → Version shows pinning status.
- In-app Help is under **Help** in the nav (authenticated).

## Phase 9 notes

- App: `read_only`, `cap_drop: ALL`, `no-new-privileges`.
- Socket-proxy: API allow-list only (not `read_only` — tecnativa 0.3.0 must write `haproxy.cfg` in-place). `DISABLE_IPV6=1`, `ALLOW_RESTARTS`, internal network only.
- If Server page shows `Failed to resolve 'socket-proxy'`, the proxy is down. `./deploy/mf up` prints proxy logs when that happens.
- Backend tests enforce `--cov-fail-under=80` on `app/services`.
- Operator docs: [restore-drill.md](./restore-drill.md), [migrating-from-itzg.md](./migrating-from-itzg.md), [release-checklist.md](./release-checklist.md).
- Optional GHCR multi-arch: `./deploy/publish.sh <version>` or tag `v*` for `.github/workflows/publish.yml`.
- `MINEFORGE_TRUST_PROXY_HEADERS` for reverse-proxy client IP (off by default).

## Volumes

- `mineforge-data` → `/app-data` (DB + `/app-data/backups` + pack library)
- `/data` ← `BEDROCK_DATA_HOST_PATH` (bind) **or** named volume `bedrock-data`
