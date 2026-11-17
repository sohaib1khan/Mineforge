# Port forwarding for NetherNet

Forward these to the machine running Docker:

- **TCP 19132** — NetherNet signaling (`server-port`)
- **UDP 19140–19155** — game traffic (`server-udp-ports`)

Docker Compose publishes `19132/tcp` and `19140-19155/udp` on the host. Your router must forward those from the WAN to that host.

On the Server → Network panel, **Re-detect public IP** writes the concrete `server-udp-ports` value (`PUBLIC_IP:19140-19155:19140-19155`) and restarts Bedrock so clients learn the right address.
