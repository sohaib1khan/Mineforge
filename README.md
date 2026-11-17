# MineForge

A self-hosted panel for running a Minecraft Bedrock dedicated server. Start/stop the box, switch worlds without losing progress, take backups, manage allowlists and add-ons, watch the console, and keep an eye on resource use — from a phone or a desktop browser.

Built by [Sohaib Khan](https://github.com/sohaib1khan/Mineforge).

Not affiliated with Mojang or Microsoft.

## What you get

- Docker Compose deploy (app + locked-down Docker socket proxy; Bedrock optional)
- First-run admin setup in the UI (no setup code)
- World list + switch with pre-switch backup and countdown
- Live backups / restore, pack library, ops & allowlist editors
- Metrics charts, NetherNet public-IP helper, in-app help guides
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

Keep your existing itzg (or compatible) container. Deploy MineForge **without** the `bedrock` profile, point `MINEFORGE_BEDROCK_CONTAINER` at that container’s name, and bind-mount your current `/data` directory into the MineForge service.

Details: [docs/migrating-from-itzg.md](./docs/migrating-from-itzg.md).

## Config

Copy `deploy/.env.example` → `deploy/.env`. Never commit `.env`.

| Variable | Notes |
|---|---|
| `MINEFORGE_SECRET_KEY` | Required. Long random string. Changing it logs everyone out. |
| `MINEFORGE_HOST_PORT` | Host port for the UI (default `18080`) |
| `MINEFORGE_BEDROCK_CONTAINER` | Docker container name MineForge controls (default `bedrock`) |
| `BEDROCK_VERSION` | Pin a version when using the compose Bedrock profile |

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
