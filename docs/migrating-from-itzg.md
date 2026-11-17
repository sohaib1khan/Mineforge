# Attaching MineForge to an existing Bedrock server

Yes — MineForge can manage an already-running Bedrock container **and** show its worlds, allowlist, packs on disk, and `server.properties`. That only works when the panel mounts the **same** host data directory Bedrock uses.

## What MineForge needs

| Piece | Role |
|---|---|
| Shared `/data` | Same host folder Bedrock uses (`worlds/`, `server.properties`, packs, allowlist) |
| `/app-data` volume | MineForge DB, backups, pack *library* (separate from Bedrock) |
| Docker via socket-proxy | Start/stop/restart, logs, console, stats for one container |
| `MINEFORGE_BEDROCK_CONTAINER` | Exact name from `docker ps` (often `bedrock`) |

Without the shared data mount you still get **container** status/logs, but **Worlds / allowlist / properties** will not match the live server (empty named volume).

## Sidecar deploy (keep Bedrock running)

1. Find the data path Bedrock already mounts, e.g. `/home/mcvm/minecraft/data`.
2. Clone MineForge, copy `deploy/.env.example` → `deploy/.env`, set:
   ```bash
   MINEFORGE_BEDROCK_CONTAINER=bedrock
   BEDROCK_DATA_HOST_PATH=/home/mcvm/minecraft/data
   BEDROCK_UID=1000
   BEDROCK_GID=1000
   ```
3. Start **only** the panel:
   ```bash
   ./deploy/mf up
   ```
   Do **not** run `./deploy/mf up bedrock` (that starts a second Bedrock).
4. Confirm:
   ```bash
   docker ps --filter name=mineforge-socket-proxy   # Up, not Restarting
   docker exec mineforge-mineforge-1 ls /data/worlds
   ```
   The `ls` should list your real world folders.
5. UI → **Worlds** should list those folders; **Server** allowlist/properties should match the live files.

### Pack library vs packs already on the server

- Packs already under `/data/behavior_packs` and `/data/resource_packs` stay on the server.
- MineForge’s **Add-ons** library lives in `/app-data/packs`. Upload there when you want the panel to manage apply/test/revert. Existing uploads on the host (e.g. `~/minecraft/uploads`) are not auto-imported.

### When you next recreate Bedrock

Remove gameplay env overrides so itzg does not overwrite `server.properties`:

- Keep: `EULA`, `VERSION` (pinned), `UID`, `GID`, `TZ`, `TRANSPORT`, `SERVER_PORT`, `SERVER_UDP_PORTS`
- Remove: `LEVEL_NAME`, `GAMEMODE`, `DIFFICULTY`, and similar gameplay keys

## Full cutover (optional)

Point MineForge’s `bedrock` profile at the same `BEDROCK_DATA_HOST_PATH`, stop your old compose Bedrock, then `./deploy/mf up bedrock`.

## Rollback

Keep your previous compose. Point Bedrock at the same data path if you leave MineForge temporarily. See [restore-drill.md](./restore-drill.md).
