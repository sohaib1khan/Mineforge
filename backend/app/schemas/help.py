"""Help guide schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HelpGuideListItem(BaseModel):
    slug: str
    title: str
    summary: str
    order: int


class HelpGuideListResponse(BaseModel):
    guides: list[HelpGuideListItem]


class HelpGuideResponse(BaseModel):
    slug: str
    title: str
    summary: str
    markdown: str
