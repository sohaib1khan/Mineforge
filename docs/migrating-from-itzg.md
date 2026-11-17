# Attaching MineForge to an existing Bedrock server

Use this when `itzg/minecraft-bedrock-server` (or compatible) is **already running** and you want the panel without replacing that container.

## What MineForge needs

| Piece | Role |
|---|---|
| Shared `/data` | Same host folder/volume Bedrock uses (`worlds/`, `server.properties`, packs, allowlist) |
| `/app-data` volume | MineForge DB, backups, pack library (separate from Bedrock) |
| Docker access via socket-proxy | Start/stop/restart, logs, console, stats for **one** container name |
| `MINEFORGE_BEDROCK_CONTAINER` | Exact Docker name (your `docker ps` Name column; often `bedrock`) |

MineForge does not auto-discover servers on the LAN. It attaches by container name + shared data dir.

## Sidecar deploy (keep Bedrock running)

1. On the same Docker host, clone MineForge and create `deploy/.env` from `.env.example`.
2. Set:
   ```bash
   MINEFORGE_BEDROCK_CONTAINER=bedrock   # must match `docker ps` name
   BEDROCK_UID=1000                      # match your Bedrock UID/GID
   BEDROCK_GID=1000
   ```
3. Bind-mount your existing data into the **mineforge** service (do **not** use a fresh named volume if you want the live worlds). In `deploy/docker-compose.yml`:
   ```yaml
   volumes:
     - mineforge-data:/app-data
     - /home/mcvm/minecraft/data:/data   # ← your real Bedrock /data path
   ```
4. Start **only** the panel (no Bedrock profile):
   ```bash
   ./deploy/mf up
   ```
   Do **not** run `./deploy/mf up bedrock` — that would start a second Bedrock.
5. Confirm the proxy is healthy:
   ```bash
   docker ps --filter name=mineforge-socket-proxy
   # STATUS should be Up (healthy), not Restarting
   ```
6. Open the UI → **Server** should show status for container `bedrock`. **Worlds** lists folders under your mounted `/data/worlds`.

### When you next recreate Bedrock

Remove gameplay env overrides so itzg does not overwrite `server.properties` on restart:

- Keep: `EULA`, `VERSION` (pinned), `UID`, `GID`, `TZ`, `TRANSPORT`, `SERVER_PORT`, `SERVER_UDP_PORTS`
- Remove: `LEVEL_NAME`, `GAMEMODE`, `DIFFICULTY`, and similar gameplay keys

## Full cutover (optional)

If you prefer MineForge’s compose to own Bedrock:

1. Stop your old Bedrock container (keep the data directory).
2. Point MineForge’s `bedrock` service at the same bind/volume.
3. `./deploy/mf up bedrock`

## Player / allowlist notes

- Existing `allowlist.json` / `permissions.json` under `/data` are edited in place.
- Gamertags must match exactly.

## Rollback

Keep your previous compose file. Point Bedrock at the same `/data` path if you leave MineForge temporarily. See [restore-drill.md](./restore-drill.md).
