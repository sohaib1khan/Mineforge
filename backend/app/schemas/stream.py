"""Stream API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StreamStatusResponse(BaseModel):
    live: bool
    enabled: bool
    title: str
    description: str
    started_at: str | None = None
    viewers: int = 0
    bitrate_kbps: float | None = None
    video_codec: str | None = None
    resolution: str | None = None
    last_ended_at: str | None = None
    hls_path: str | None = None


class StreamSettingsResponse(BaseModel):
    title: str
    description: str
    enabled: bool
    key_configured: bool
    key_rotated_at: str | None = None
    rtmp_server: str
    rtmp_host: str = ""
    rtmp_port: int = 1935
    rtmp_stream_key_hint: str
    obs_notes: list[str] = Field(default_factory=list)


class StreamSettingsUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    enabled: bool | None = None


class StreamKeyRotateResponse(BaseModel):
    stream_key: str
    obs_stream_key: str
    rtmp_server: str
    rtmp_url_example: str
    key_rotated_at: str
    warning: str = (
        "Copy the OBS Stream Key field now — it will not be shown again. "
        "In OBS use Service: Custom (not Twitch). Capture the game window only."
    )


class MediaMtxAuthRequest(BaseModel):
    """Payload MediaMTX POSTs to the HTTP auth endpoint.

    MediaMTX may send JSON null for optional fields (notably ``id`` on HLS
    reads). Coerce nulls to empty strings so auth does not 422.
    """

    model_config = ConfigDict(extra="ignore")

    user: str = ""
    password: str = ""
    token: str = ""
    ip: str = ""
    action: str = ""
    path: str = ""
    protocol: str = ""
    id: str = ""
    query: str = ""
    userAgent: str = ""

    @field_validator(
        "user",
        "password",
        "token",
        "ip",
        "action",
        "path",
        "protocol",
        "id",
        "query",
        "userAgent",
        mode="before",
    )
    @classmethod
    def _null_to_empty(cls, value: Any) -> Any:
        return "" if value is None else value
