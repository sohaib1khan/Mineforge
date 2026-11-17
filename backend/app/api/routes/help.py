"""In-app Help guides."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AuthDep, SettingsDep
from app.schemas.help import HelpGuideListItem, HelpGuideListResponse, HelpGuideResponse
from app.services import help_guides

router = APIRouter(prefix="/api/help", tags=["help"])


@router.get("", response_model=HelpGuideListResponse)
def list_help_guides(settings: SettingsDep, _auth: AuthDep) -> HelpGuideListResponse:
    """List available Help guides (any authenticated user)."""

    items = help_guides.list_guides(settings)
    return HelpGuideListResponse(
        guides=[HelpGuideListItem.model_validate(item) for item in items]
    )


@router.get("/{slug}", response_model=HelpGuideResponse)
def get_help_guide(
    slug: str, settings: SettingsDep, _auth: AuthDep
) -> HelpGuideResponse:
    """Return one guide as markdown (any authenticated user)."""

    return HelpGuideResponse.model_validate(help_guides.get_guide(slug, settings))
