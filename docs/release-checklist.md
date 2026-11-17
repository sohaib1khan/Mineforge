# Release checklist

## Before tagging

- [ ] `./deploy/mf test` passes (backend `--cov-fail-under=80` on unit-testable services; `addons`/`backups`/`switch`/`worlds`/`docker_client`/`operations`/`logwatch`/`console` covered by integration tests and omitted from the gate)
- [ ] `./deploy/mf up` + `./deploy/mf smoke` on a clean machine
- [ ] First-run setup creates admin; login works; CSRF mutations work
- [ ] Spot-check: Backup now, Worlds list, Metrics sample, Help guide, Server Network (manual IP if no egress)
- [ ] `deploy/.env.example` has placeholders only (`CHANGE_ME`, `example.com`, `203.0.113.x`)
- [ ] No secrets in `git status` (`.env`, worlds, packs, binaries)
- [ ] README / docs match current first-run behavior (no obsolete setup-code steps)
- [ ] Pin `BEDROCK_VERSION` guidance still accurate

## Image build (local)

```bash
docker build -f Dockerfile --target runtime -t mineforge:0.9.0 .
```

## Optional multi-arch + GHCR

```bash
./deploy/publish.sh 0.9.0
```

Requires Docker Buildx and `docker login ghcr.io`. Set `GHCR_OWNER` (GitHub user/org). Skipped in default CI.

## After release

- [ ] Tag `v0.9.0` (or current version)
- [ ] Note any breaking changes (e.g. session HMAC keyed by `MINEFORGE_SECRET_KEY` — existing sessions invalidate when the key changes)
- [ ] Run a [restore drill](./restore-drill.md) on staging
