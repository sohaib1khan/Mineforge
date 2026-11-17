# User guide

## First run

1. Start MineForge (`./deploy/mf up`) and open the web UI.
2. If no admin exists yet, you land on **First-time setup** — create the admin username and password (12+ characters). No setup code required.
3. Sign in with that admin account.

## Account

- Change your own password under **Account**.
- Toggle dark/light theme (stored in the browser) from Account or the shell controls.
- On phones, use the bottom nav; on desktop, use the sidebar.

## Metrics

- Open **Metrics** for players-online, CPU, memory, joins-per-day, playtime leaderboard, and disk usage.
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

## Worlds

- Browse worlds discovered under the Bedrock data directory.
- **Switch** to another world: MineForge warns in-game, backs up the current world, stops the server, changes `level-name`, starts, and health-checks.
- If the new world fails to come up, MineForge rolls back to the previous world automatically.
- While other players are online, either everyone approves a switch request (2 minutes) or an admin **Force switch**.
- Admins can create, import `.mcworld`, export, rename, clone, and delete (not the active world).

## Backups

- Any signed-in user can tap **Backup now** for the active world.
- Live backups work while players are online.
- Admins can **Restore**, **Download**, or **Delete** backups.
- Restore takes a safety backup first and rolls back automatically if startup fails.
- Watch live progress in the operation drawer.

## Server & console (admin)

- Start/stop/restart the Bedrock container, edit safe `server.properties` keys, manage allowlist/ops.
- Live console send + stream.

## Add-ons (admin manage; everyone can view)

- Upload `.mcaddon` / `.mcpack` into the library.
- Flags warn about missing BP/RP halves, Marketplace/encrypted packs, and Beta APIs.
- Per-world tab: enable packs, **Save profile**, then **Apply** or **Test**.
- Test mode auto-reverts after the configured minutes unless you tap **Keep test**.
- World-embedded packs from imports are always kept when applying profiles.
