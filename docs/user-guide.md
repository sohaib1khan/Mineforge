# User guide

## First run

1. Start MineForge (`./deploy/mf up`) and open the web UI.
2. If no admin exists yet, you land on **First-time setup** — create the admin username (letters, numbers, `.` `_` `-`) and password (12+ characters). No setup code required.
3. Sign in with that admin account.

## Account

- Change your own password under **Account**.
- Toggle dark/light theme (stored in the browser) from Account or the shell controls.
- On phones, use the bottom nav; on desktop, use the sidebar (theme and sign out stay pinned at the bottom).

## Metrics

- Open **Metrics** for summary peaks, players-online, CPU, memory, network rates, joins-per-day, playtime leaderboard, and disk usage (including last played per world).
- The dashboard also shows the latest CPU/memory sample and weekly playtime.

## Network & Help

- Admins: **Server → Network** to detect public IP, update `server-udp-ports`, and restart.
- Forward **TCP 19132** and **UDP 19140–19155** to the host; keep game DNS DNS-only.
- **Help** has built-in guides (connecting, ports, DNS, versions, carriers, add-ons, console).

## Install as an app (PWA)

- On a supported browser (HTTPS or localhost), use **Install** / **Add to Home Screen**.
- Offline, the app shell still loads; server actions need the MineForge backend reachable.

## Users (admin)

- Create player or admin accounts.
- Reset passwords (user must change password on next login when created/reset).
- Deactivate or delete accounts.

## Worlds (switch here)

- Open **Worlds** in the nav (sidebar or phone bottom bar). Each world shows last played, size, mode, and seed when known.
- Long lists (add-ons, backups, metrics tables) scroll inside the page so the sidebar stays usable.
- The active world is labeled **Active**. On any other world, tap **Switch**.
- MineForge warns in-game, backs up the current world, stops Bedrock, changes `level-name`, starts, and health-checks.
- If the new world fails to come up, it rolls back automatically.
- While other players are online, either everyone approves (2 minutes) or an admin **Force switch**.
- Admins can create, import `.mcworld`, export, rename, clone, and delete (not the active world).

## Stream (OBS live)

- Open **Stream** to watch when the admin is live (logged-in users only).
- Admin panel: enable/disable, edit title/description, **Show OBS setup**, **Regenerate key** (OBS values shown once — use Copy).
- OBS → Settings → Stream:
  - Service: **Custom** (not Twitch / YouTube)
  - Server: `rtmp://<host>:1935/live` (must be `rtmp://`, not `https://`)
  - Stream Key: `stream?user=publish&pass=…` (from MineForge after regenerate — must start with `stream?`)
- For remote OBS (different network): forward **TCP 1935** to the MineForge host; set `MINEFORGE_STREAM_RTMP_HOST` and `MINEFORGE_INTERNAL_STREAM_SECRET` in `deploy/.env`.
- **Cloudflare:** HTTPS for the web UI can stay orange-cloud, but RTMP cannot. Add a **DNS-only (grey cloud)** record (e.g. `rtmp.yourdomain` → server public IP), set `MINEFORGE_STREAM_RTMP_HOST=rtmp.yourdomain`, and point OBS at `rtmp://rtmp.yourdomain:1935/live`.
- Recommended: 1280×720 or 1920×1080, 30 fps, CBR 2500–4500 kbps, keyframe interval **1 s**, AAC audio. Capture the **game window** only. Expect roughly **2–5 s** viewer delay (HLS), not true zero-latency.
- Viewers use MineForge HLS proxy; MediaMTX HLS/API ports stay internal. RTMP publish is authenticated with the stream key (RTMP itself is not encrypted).

## Backups

- Any signed-in user can tap **Backup now** for the active world.
- Live backups work while players are online.
- Admins can **Restore**, **Save to device**, or **Delete** backups (world and add-on library archives download to your browser).
- Restore takes a safety backup first and rolls back automatically if startup fails.
- Watch live progress in the operation drawer.

## Server & console (admin)

- Start/stop/restart the Bedrock container, edit safe `server.properties` keys, manage allowlist/ops.
- Live console send + stream.

## Add-ons (admin manage; everyone can view)

- Upload `.mcaddon` / `.mcpack` into the library.
- Admins can **Backup library** / **Restore** under Add-ons to snapshot every pack plus per-world assignments.
- Flags warn about missing BP/RP halves, Marketplace/encrypted packs, and Beta APIs.
- Per-world tab: enable packs, **Save profile**, then **Apply** or **Test**.
- Test mode auto-reverts after the configured minutes unless you tap **Keep test**.
- World-embedded packs from imports are always kept when applying profiles.
