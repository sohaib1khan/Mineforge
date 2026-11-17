# DNS and Cloudflare

If you use a DNS name for the game server:

- The record must be **DNS-only** (grey cloud / not proxied).
- HTTP proxies (including Cloudflare orange-cloud) only carry web traffic — they will not pass Minecraft NetherNet.

Point an A/AAAA record at your public IP. Keep MineForge’s web UI behind HTTPS (reverse proxy) separately from the game ports.
