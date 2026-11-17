# Migrating from an existing itzg Bedrock setup

Use this when you already run `itzg/minecraft-bedrock-server` and want MineForge to manage the same world data.

## What MineForge expects

| Path | Role |
|---|---|
| Docker volume or bind → `/data` | Bedrock data: `worlds/`, `server.properties`, packs, allowlist |
| Docker volume → `/app-data` | MineForge DB, backups, pack library |

The Bedrock container name must match `MINEFORGE_BEDROCK_CONTAINER` (default `bedrock`).

## Steps

1. **Stop** your current Bedrock container (keep the data volume).

2. **Copy or reuse the volume** as MineForge’s `bedrock-data` (or bind-mount your existing host directory to `/data` in both services).

3. **Sanitize env** on the Bedrock service (critical):
   - Keep: `EULA`, `VERSION` (prefer a **pinned** build), `UID`, `GID`, `TZ`, `TRANSPORT=nethernet`, `SERVER_PORT`, `SERVER_UDP_PORTS`
   - **Remove** `LEVEL_NAME`, `GAMEMODE`, `DIFFICULTY`, and other gameplay keys — MineForge owns them in `server.properties`. If you leave them in env, itzg will overwrite switches on every restart.

4. **Align ports** with NetherNet: publish `19132/tcp` and `19140-19155/udp`.

5. Start MineForge with Bedrock: `./deploy/mf up bedrock`.

6. Open the UI → create admin (first run) → **Worlds** should list folders under `/data/worlds`.

7. On **Server → Network**, detect/apply public IP so `server-udp-ports` advertises correctly.

8. Take a **Backup now** before the first switch or add-on apply.

## Player / allowlist notes

- Copy existing `allowlist.json` / `permissions.json` under `/data` — MineForge edits them in place.
- Gamertags must match exactly (including suffixes).

## Rollback

Keep your previous compose file until you have completed a [restore drill](./restore-drill.md). Point Bedrock back at the same `/data` volume if you need to leave MineForge temporarily.
