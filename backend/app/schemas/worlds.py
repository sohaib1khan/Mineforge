"""World library and switch API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.operations import OperationResponse


class WorldResponse(BaseModel):
    id: int
    display_name: str
    folder_name: str
    description: str | None = None
    gamemode: str | None = None
    difficulty: str | None = None
    seed: str | None = None
    size_bytes: int = 0
    is_active: bool = False
    created_at: str | None = None
    last_played_at: str | None = None
    needs_experiments: bool = False
    valid: bool = False
    on_disk: bool = False
    icon_present: bool = False
    warnings: list[str] = Field(default_factory=list)


class WorldListResponse(BaseModel):
    worlds: list[WorldResponse]


class WorldCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
    folder_name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    gamemode: str | None = Field(default=None, max_length=32)
    difficulty: str | None = Field(default=None, max_length=32)
    seed: str | None = Field(default=None, max_length=64)


class WorldRenameRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    folder_name: str | None = Field(default=None, max_length=128)


class WorldCloneRequest(BaseModel):
    folder_name: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)


class WorldImportResponse(BaseModel):
    world: WorldResponse
    warnings: list[str] = Field(default_factory=list)


class SwitchRequest(BaseModel):
    force: bool = False
    skip_countdown: bool = False
    consent_id: str | None = None


class SwitchStartResponse(BaseModel):
    operation: OperationResponse


class SwitchConsentResponse(BaseModel):
    id: str
    target_world_id: int
    target_folder: str
    requested_by: int
    required_count: int
    approval_count: int
    online_gamertags: list[str]
    expires_at: str
    satisfied: bool


class SwitchStatusResponse(BaseModel):
    players_online: int
    online_gamertags: list[str]
    cooldown_remaining_seconds: int
    countdown_seconds: int
    open_consent_requests: list[SwitchConsentResponse]
