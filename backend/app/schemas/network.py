"""Network panel and version schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChecklistItem(BaseModel):
    id: str
    title: str
    detail: str


class NetworkStatusResponse(BaseModel):
    server_port: str
    server_udp_ports: str | None = None
    advertised_public_ip: str | None = None
    detected_public_ip: str | None = None
    proposed_server_udp_ports: str | None = None
    matches_advertised: bool | None = None
    udp_range: str
    transport: str
    checklist: list[ChecklistItem] = Field(default_factory=list)
    lookup_url: str
    note: str
    restarted: bool | None = None


class ApplyPublicIpRequest(BaseModel):
    ip_address: str | None = Field(
        default=None,
        description="Optional IPv4; when omitted MineForge looks up the public IP.",
    )
    restart: bool = True


class VersionInfoResponse(BaseModel):
    image: str | None = None
    version_env: str | None = None
    pinned: bool
    guidance: str
