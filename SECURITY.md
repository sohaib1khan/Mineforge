# Security Policy

## Reporting a vulnerability

Please report security issues privately. Do **not** open a public GitHub issue
for secrets, auth bypasses, or remote code execution.

Include:

- Affected version / commit
- Steps to reproduce
- Impact assessment

We will acknowledge reports and coordinate a fix before any public disclosure.

## Hardening expectations (MineForge)

- Passwords: argon2id, minimum length 12; never logged
- Sessions: httpOnly, Secure, SameSite=Strict cookies; server-side sessions; HMAC token hashing with `MINEFORGE_SECRET_KEY`; CSRF on mutations (including logout)
- First run: when no admin exists, the UI shows **First-time setup** (create admin). No setup code is required (hands-off Docker install). Protect the UI with LAN-only bind, reverse-proxy auth, or Cloudflare Access in production
- Role checks enforced in API dependencies
- Uploads: extension allowlist, size limits, safe archive extraction
- Docker access only via a locked-down socket proxy (no direct `docker.sock` on the app)
- App container: non-root, capability-dropped, read-only rootfs. Socket-proxy: API allow-list on an internal network (not read-only — HAProxy must write its generated config)
- No secrets, real IPs, domains, gamertags, or credentials in the repository

## Reverse proxy

Set `MINEFORGE_TRUST_PROXY_HEADERS=true` only when a trusted reverse proxy
overwrites `X-Forwarded-For` / `X-Real-IP`. Otherwise leave it false so clients
cannot spoof IPs used for lockout and audit.

## Secrets in git

If a secret is ever committed: **rotate it first**, then purge history.
Deleting the file from a later commit is not enough.
Changing `MINEFORGE_SECRET_KEY` invalidates all existing sessions.
