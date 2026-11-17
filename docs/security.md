# Security notes

See also [SECURITY.md](../SECURITY.md) at the repository root.

## Intended deployment

MineForge is designed to sit behind a reverse proxy with HTTPS.
Optional: Cloudflare Access, or LAN-only exposure (`MINEFORGE_HOST_PORT` bound to LAN only via host firewall / compose publish address).

For local HTTP development set `MINEFORGE_COOKIE_SECURE=false`.

## Auth

- argon2id passwords; minimum length 12; never logged
- Server-side sessions; logout invalidates the session row (CSRF required)
- Session token hashes use HMAC with `MINEFORGE_SECRET_KEY`
- Login rate limiting (SlowAPI) + temporary lockout after repeated failures
- First-run: open setup UI when no admin exists — lock down network exposure in production
- Role checks in FastAPI dependencies
- Security headers: CSP, X-Frame-Options, Referrer-Policy, nosniff

## Proxy trust

- Default: client IP = direct TCP peer (`request.client.host`)
- `MINEFORGE_TRUST_PROXY_HEADERS=true`: use leftmost `X-Forwarded-For` or `X-Real-IP` for audit/lockout

## Trust boundaries

- The app container never mounts `/var/run/docker.sock` directly
- Docker control goes through tecnativa/docker-socket-proxy with a minimal ACL (containers/info/logs/stats + start/stop/restart)
- Uploads: size limit, extension allowlist, zip-bomb safe extraction (`archive_safety`)

## Repository hygiene

Gitleaks runs in pre-commit and CI. Dependabot is enabled for pip, npm, Actions, and Docker.
