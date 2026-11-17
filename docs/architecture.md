# Architecture

```
Browser / PWA
    │ HTTPS (reverse proxy) or http://localhost:18080
    ▼
docker compose
  ├── mineforge (FastAPI + React SPA)
  │     └── DOCKER_HOST=tcp://socket-proxy:2375
  ├── socket-proxy (tecnativa/docker-socket-proxy)
  │     └── /var/run/docker.sock (locked-down)
  ├── mediamtx (OBS RTMP ingest → LL-HLS; remux only)
  │     RTMP :1935 bound to LAN IP only; HLS/API internal
  └── bedrock (itzg) [profile: bedrock]
        TCP 19132 + UDP 19140–19155
```

- `/data` — Bedrock worlds, packs, `server.properties`, allowlist
- `/app-data` — SQLite, backups (`.tar.zst`), setup state

## Phase 2

- Docker control only through `services/docker_client.py` → socket proxy
- Console commands via Docker **attach** stdin (not itzg send-command)
- Log watcher parses joins/leaves → `player_sessions`
- Live console over SSE; commands via POST

## Phase 3

- Global operation lock + job state machine (`services/operations.py`)
- Live backup: `save hold` → poll `save query` until ready (comma-separated `path:size` list) → truncated copy → `save resume` → `.tar.zst` + sha256 verify
- Add-on library backup: stream `/app-data/packs` + manifest directly into `.tar.zst` (no full `/tmp` staging copy)
- Restore: pre-restore backup → stop → extract → atomic swap → start/health-check → auto swap-back on failure
- Nightly backup + retention via APScheduler
- SSE progress for operations; Backups UI + progress drawer

## Phase 4

- World library: scan `/data/worlds`, create/import/export/rename/clone/delete
- Safe switch A→B: preflight, countdown, pre-switch backup, stop, `level-name`, start, health-check
- Failure after properties change → restore previous `server.properties` and restart A
- Player switch rules: consent request (2 min) or admin force; cooldown for non-admins

## Phase 5

- Pack library under `/app-data/packs`; applied copies in `/data/behavior_packs` & `resource_packs`
- Upload `.mcaddon`/`.mcpack`, parse manifests, BP/RP pairing, flags (missing pair, encrypted, beta APIs)
- Per-world profiles; apply merges enabled packs with world-embedded packs
- Test mode with keep / auto-revert countdown

## Phase 6

- Dark/light theme tokens + `ThemeProvider`; CSS motion with `prefers-reduced-motion`
- Desktop sidebar + mobile bottom nav; skip-to-content; focus-visible; OfflineBanner
- Skeletons, empty states, toasts on key flows
- `vite-plugin-pwa`: installable manifest, offline app shell (API stays NetworkOnly)

## Phase 7

- `metric_samples` table; Docker `stats(stream=False)` every ~30s via APScheduler
- Session playtime leaderboard + joins-per-day from `player_sessions`
- Disk summary (world sizes + backup storage)
- `/api/metrics/overview` + `/api/metrics/dashboard`; Metrics page (Recharts) + Home widgets

## Phase 8

- `services/network.py`: public IP lookup (httpx), `server-udp-ports` write via `write_managed`, restart
- Version panel: Docker image + `VERSION` env + pinning guidance
- Help guides: packaged markdown under `app/help_guides/`, `/api/help`, Help page (`react-markdown`)
- Server page Network panel + forwarding checklist

## Phase 9

- Compose hardening (app read-only + cap drop; socket-proxy allow-list + LOGS/STATS)
- Session HMAC with `MINEFORGE_SECRET_KEY`; CSRF on logout; optional trusted proxy headers
- pytest-cov gate ≥ 80% on `app/services`; restore drill + itzg migration + release docs
- Optional multi-arch GHCR publish workflow / `deploy/publish.sh`

## Phase 10 (Stream)

- MediaMTX container: OBS publishes RTMP on `:1935` (public bind by default for remote OBS); HLS/API stay on the Docker network
- Publish auth via `POST /internal/stream/auth` (shared secret + private source IP); stream key argon2-hashed
- Viewers: logged-in session → `/api/stream/hls/*` httpx proxy (forwards `_HLS_*` query) → MediaMTX LL-HLS (`hls.js` / native Safari)
- Stream page + nav LIVE badge + dashboard “Live now — Watch” card; OBS Custom uses `?user=publish&pass=…` stream-key field
