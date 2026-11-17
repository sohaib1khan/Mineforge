# Version matching and pinning

Bedrock clients and the dedicated server must be on a **compatible build**.

- In `deploy/.env`, set `BEDROCK_VERSION` to a **pinned** version (not `LATEST`).
- Recreate the Bedrock service after changing it: `./deploy/mf up bedrock`.
- `VERSION=LATEST` updates on restart and can leave older phones unable to join.

The Server page shows the container image and the `VERSION` env MineForge reads from Docker, plus pinning guidance.
