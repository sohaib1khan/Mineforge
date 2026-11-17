# Attaching MineForge to an existing Bedrock server

MineForge can manage an already-running Bedrock container **and** show its worlds, allowlist, properties, and custom packs. That requires mounting the **same** host data directory Bedrock uses as `/data`.

## Quick path (auto-detect)

With Bedrock already running on the same Docker host:

```bash
cd Mineforge
./deploy/mf attach    # or: ./deploy/mf up
```

`mf` inspects the container named `MINEFORGE_BEDROCK_CONTAINER` (default `bedrock`), reads the host path mounted at `/data`, writes `BEDROCK_DATA_HOST_PATH` into `deploy/.env`, and recreates the app container with that bind.

You should see something like:

```text
==> Auto-detected Bedrock /data from container 'bedrock': /home/mcvm/minecraft/data
==> Found N world folder(s) under /data/worlds
```

Verify:

```bash
docker exec mineforge-mineforge-1 ls /data/worlds
```

Then open **Worlds**, **Add-ons**, and **Server** in the UI.

## Manual path

In `deploy/.env`:

```bash
MINEFORGE_BEDROCK_CONTAINER=bedrock
BEDROCK_DATA_HOST_PATH=/home/mcvm/minecraft/data
```

Then:

```bash
./deploy/mf up
```

Do **not** run `./deploy/mf up bedrock` while your existing Bedrock compose is already running.

Also set `BEDROCK_UID` / `BEDROCK_GID` (and/or `MINEFORGE_RUNTIME_UID` / `MINEFORGE_RUNTIME_GID`) to the owner of that data folder — usually `1000`. Otherwise allowlist / `server.properties` saves return Internal Server Error (permission denied).

## What gets picked up

| From shared `/data` | Where it shows |
|---|---|
| `worlds/` | **Worlds** |
| `server.properties` | **Server** properties / network |
| `allowlist.json`, `permissions.json` | **Server** allowlist / ops |
| Custom packs under `behavior_packs`, `resource_packs`, `development_*` | **Add-ons** library (stock Vanilla packs skipped) |
| `world_*_packs.json` | Linked on each world’s add-on profile |

MineForge’s own DB/backups/pack copies live under `/app-data` (separate volume). Your `~/minecraft/uploads` folder is **not** auto-imported — packs already installed under `/data` are.

## When you next recreate Bedrock

Remove gameplay env overrides so itzg does not overwrite `server.properties`:

- Keep: `EULA`, `VERSION` (pinned), `UID`, `GID`, `TZ`, `TRANSPORT`, `SERVER_PORT`, `SERVER_UDP_PORTS`
- Remove: `LEVEL_NAME`, `GAMEMODE`, `DIFFICULTY`, and similar gameplay keys

## Rollback

Keep your previous compose. Point Bedrock at the same data path if you leave MineForge temporarily. See [restore-drill.md](./restore-drill.md).
