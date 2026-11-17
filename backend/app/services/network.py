"""Public IP detection and NetherNet ``server-udp-ports`` management.

Updates ``server.properties`` then restarts Bedrock so clients advertise
the correct public address for UDP game traffic.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

import httpx
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services import server as server_service
from app.services import server_props
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

DEFAULT_UDP_RANGE = "19140-19155"
_IPV4_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)$"
)

# Injected in tests to avoid real network calls.
_ip_lookup_override: Callable[[Settings], str] | None = None


def set_ip_lookup_override(fn: Callable[[Settings], str] | None) -> None:
    """Replace public-IP lookup (tests)."""

    global _ip_lookup_override
    _ip_lookup_override = fn


def validate_ipv4(ip: str) -> str:
    """Return a stripped IPv4 address or raise AppError."""

    cleaned = ip.strip()
    if not _IPV4_RE.match(cleaned):
        raise AppError("Public IP must be a valid IPv4 address")
    if cleaned.startswith("127.") or cleaned.startswith("0."):
        raise AppError("Public IP must not be a loopback or unspecified address")
    return cleaned


def build_udp_ports(ip: str, udp_range: str = DEFAULT_UDP_RANGE) -> str:
    """Build ``server-udp-ports`` value: ``IP:19140-19155:19140-19155``."""

    address = validate_ipv4(ip)
    span = udp_range.strip() or DEFAULT_UDP_RANGE
    if not re.match(r"^\d{2,5}-\d{2,5}$", span):
        raise AppError("UDP port range must look like 19140-19155")
    return f"{address}:{span}:{span}"


def parse_advertised_ip(server_udp_ports: str | None) -> str | None:
    """Extract the leading IPv4 from a ``server-udp-ports`` value, if present."""

    if not server_udp_ports:
        return None
    raw = server_udp_ports.strip()
    if raw.startswith("<") and "public_ip" in raw:
        return None
    host = raw.split(":", 1)[0].strip()
    if _IPV4_RE.match(host):
        return host
    return None


def lookup_public_ip(settings: Settings | None = None) -> str:
    """Fetch the host's public IPv4 from the configured lookup URL.

    Raises:
        AppError: on network failure or invalid response.
    """

    cfg = settings or get_settings()
    if _ip_lookup_override is not None:
        return validate_ipv4(_ip_lookup_override(cfg))

    url = cfg.public_ip_lookup_url.strip()
    if not url:
        raise AppError("Public IP lookup URL is not configured")
    try:
        with httpx.Client(timeout=cfg.public_ip_lookup_timeout_seconds) as client:
            response = client.get(url)
            response.raise_for_status()
            text = response.text.strip()
            # ipify may return plain text or JSON {"ip":"..."}
            if text.startswith("{"):
                data = response.json()
                text = str(data.get("ip") or data.get("origin") or "")
    except httpx.HTTPError as exc:
        raise AppError(f"Public IP lookup failed: {exc}", status_code=502) from exc
    except ValueError as exc:
        raise AppError("Public IP lookup returned invalid JSON") from exc
    return validate_ipv4(text)


def forwarding_checklist(
    *,
    server_port: str | None,
    server_udp_ports: str | None,
) -> list[dict[str, str]]:
    """Static checklist of required port forwards for NetherNet."""

    tcp = server_port or "19132"
    udp = DEFAULT_UDP_RANGE
    if server_udp_ports and ":" in server_udp_ports:
        parts = server_udp_ports.split(":")
        if len(parts) >= 2 and "-" in parts[1]:
            udp = parts[1]
    return [
        {
            "id": "tcp_signal",
            "title": f"TCP {tcp}",
            "detail": "NetherNet signaling — forward to the MineForge host.",
        },
        {
            "id": "udp_game",
            "title": f"UDP {udp}",
            "detail": "Game traffic range — forward the whole range to the host.",
        },
        {
            "id": "dns_only",
            "title": "DNS-only (not proxied)",
            "detail": "Game DNS records must bypass HTTP proxies like Cloudflare orange-cloud.",
        },
        {
            "id": "version_match",
            "title": "Client version matches server",
            "detail": "Pin BEDROCK_VERSION so phones are not left behind after LATEST updates.",
        },
    ]


def network_status(settings: Settings) -> dict[str, Any]:
    """Read-only network panel payload (no external lookup)."""

    props: dict[str, str] = {}
    try:
        props = server_props.read_properties(settings)
    except Exception:
        props = {}
    udp = props.get("server-udp-ports")
    advertised = parse_advertised_ip(udp)
    return {
        "server_port": props.get("server-port") or "19132",
        "server_udp_ports": udp,
        "advertised_public_ip": advertised,
        "udp_range": DEFAULT_UDP_RANGE,
        "transport": "nethernet",
        "checklist": forwarding_checklist(
            server_port=props.get("server-port"),
            server_udp_ports=udp,
        ),
        "lookup_url": settings.public_ip_lookup_url,
        "note": (
            "If compose sets SERVER_UDP_PORTS with <public_ip>, a restart also "
            "re-resolves the placeholder. MineForge still writes the concrete "
            "value into server.properties."
        ),
    }


def detect_public_ip(settings: Settings) -> dict[str, Any]:
    """Lookup public IP and compare with the advertised value (no write)."""

    base = network_status(settings)
    detected = lookup_public_ip(settings)
    base["detected_public_ip"] = detected
    base["matches_advertised"] = (
        base["advertised_public_ip"] == detected
        if base["advertised_public_ip"]
        else False
    )
    base["proposed_server_udp_ports"] = build_udp_ports(detected)
    return base


def apply_public_ip(
    session: Session,
    settings: Settings,
    *,
    user_id: int,
    ip_address: str | None = None,
    restart: bool = True,
    client_ip: str | None = None,
) -> dict[str, Any]:
    """Write ``server-udp-ports`` for the given (or detected) IP and optionally restart.

    Raises:
        AppError: on invalid IP, properties write failure, or Docker errors.
    """

    detected = validate_ipv4(ip_address) if ip_address else lookup_public_ip(settings)
    value = build_udp_ports(detected)
    before = network_status(settings)
    server_props.write_managed(settings, {"server-udp-ports": value})
    record_audit(
        session,
        action="server.network_public_ip",
        user_id=user_id,
        details={
            "public_ip": detected,
            "server_udp_ports": value,
            "previous": before.get("server_udp_ports"),
            "restart": restart,
        },
        ip=client_ip,
    )
    session.commit()
    if restart:
        server_service.restart_server(session, settings, user_id=user_id, ip=client_ip)
    after = network_status(settings)
    after["detected_public_ip"] = detected
    after["proposed_server_udp_ports"] = value
    after["matches_advertised"] = after.get("advertised_public_ip") == detected
    after["restarted"] = restart
    return after
