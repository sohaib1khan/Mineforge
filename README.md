# MineForge

A self-hosted panel for running a Minecraft Bedrock dedicated server. Start/stop the box, switch worlds without losing progress, take backups, manage allowlists and add-ons, watch the console, and keep an eye on resource use — from a phone or a desktop browser.

Not affiliated with Mojang or Microsoft.

## What you get

- Docker Compose deploy (app + locked-down Docker socket proxy; Bedrock optional)
- First-run admin setup in the UI (no setup code)
- World list + switch with pre-switch backup and countdown
- Live world backups / restore, add-on library backup / restore, pack library, ops & allowlist editors
- Metrics charts, live Bedrock container panel (Docker health/CPU/RAM/ports/env), NetherNet public-IP helper, in-app help guides
- Dark/light theme, installable PWA

## Requirements

- Docker Engine + Compose plugin on the host
- For Bedrock: UDP/TCP ports for NetherNet (see docs)

No local Python or Node install needed for normal use — tests and the app run in containers.

## Quick start

```bash
git clone https://github.com/sohaib1khan/Mineforge.git
cd Mineforge
cp deploy/.env.example deploy/.env
# Set MINEFORGE_SECRET_KEY to a long random string before going live

./deploy/mf test          # backend + frontend tests (coverage gate on services)
./deploy/mf up            # panel + socket-proxy → http://localhost:18080
./deploy/mf up bedrock    # also start itzg Bedrock (skip if you already have one)
./deploy/mf smoke
```

Open the UI → create the admin account → Dashboard.

Useful extras:

```bash
./deploy/mf logs
./deploy/mf reset         # wipe app DB only → first-run setup again
./deploy/mf down
```

## Already running Bedrock?

On the same Docker host:

```bash
./deploy/mf attach    # auto-detects the Bedrock container's /data mount
# or: ./deploy/mf up  # same detection on start
```

That writes `BEDROCK_DATA_HOST_PATH` for you. Worlds, allowlist, properties, and custom packs come from that folder; start/stop/console talk to the container named `MINEFORGE_BEDROCK_CONTAINER` (default `bedrock`).

Details: [docs/migrating-from-itzg.md](./docs/migrating-from-itzg.md).

## Config

Copy `deploy/.env.example` → `deploy/.env`. Never commit `.env`.

| Variable | Notes |
|---|---|
| `MINEFORGE_SECRET_KEY` | Required. Long random string. Changing it logs everyone out. |
| `MINEFORGE_HOST_PORT` | Host port for the UI (default `18080`) |
| `MINEFORGE_BEDROCK_CONTAINER` | Docker container name MineForge controls (default `bedrock`) |
| `BEDROCK_VERSION` | Pin a version when using the compose Bedrock profile |

## Adding a world (keeps existing ones)

Worlds and add-ons are different. Your current worlds stay on disk; a new world is just another folder under Bedrock `/data/worlds`. Switching later is what changes which one is live.

### Create an empty world (admin)

1. Sign in as admin → **Worlds**.
2. Under **New world**, type a display name → **Create**.
3. The new world appears in the list beside your existing ones (it is **not** active yet).
4. Tap **Switch** on it when you want Bedrock to load that world. MineForge backs up the current world first, then walks the switch steps on screen.

To undo playtime on an imported world without deleting it: admin → **Worlds** → **Reset**. MineForge backs up current files, then restores the **original upload** baseline (same landscape you first imported), keeping name/add-on profile.

### Import a saved world (admin)

1. Get a **`.mcworld`** (or zip of a Bedrock world folder) — from your device export, a friend, or a *worlds* download (not a “mod”).
2. **Worlds** → **Import .mcworld** → pick the file.
3. It shows up next to your other worlds. Tap **Switch** when you want to play it.

### MCPEDL / “mods” (usually add-ons, not worlds)

Sites like [MCPEDL mods](https://mcpedl.com/category/mods/modpe/) are almost always **behavior/resource packs** (`.mcaddon` / `.mcpack`), not worlds.

| What you downloaded | Where in MineForge | What it does |
|---|---|---|
| `.mcworld` / world zip | **Worlds** → Import | Adds another world folder; switch to play it |
| `.mcaddon` / `.mcpack` | **Add-ons** → Upload | Pack library; enable on a world, then Apply |
| “ModPE” / script mods for old clients | Not supported | Dedicated Bedrock server uses packs, not ModPE |

Add-on flow (not the same as creating a world):

1. **Add-ons** → upload the `.mcaddon` / `.mcpack`.
2. Open the world profile → enable the packs → **Save profile**.
3. **Apply** (or **Test**) so Bedrock picks them up. Prefer applying while on that world, or switch to it after apply.

More detail: [User guide — Worlds](./docs/user-guide.md#worlds-switch-here) and [Add-ons](./docs/user-guide.md#add-ons-admin-manage-everyone-can-view).

## Docs

- [User guide](./docs/user-guide.md)
- [Operations](./docs/operations.md)
- [Attach / migrate from itzg](./docs/migrating-from-itzg.md)
- [Restore drill](./docs/restore-drill.md)
- [Architecture](./docs/architecture.md)
- [Security](./SECURITY.md)

## Stack

FastAPI + SQLModel/SQLite on the backend, React/Vite/TypeScript on the frontend, Compose for runtime. The app never mounts `docker.sock` directly — only the socket proxy does.

## Safety

This repo should stay free of real secrets, worlds, packs, and server binaries. Commit only `deploy/.env.example` with placeholders. See [.gitignore](./.gitignore) and [SECURITY.md](./SECURITY.md).

## License

Personal / project use for now — check with the author if you need something more formal.
