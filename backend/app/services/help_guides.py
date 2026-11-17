"""Load in-app Help guides from packaged markdown files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError

# Default guides shipped with the backend package.
_PACKAGE_GUIDES = Path(__file__).resolve().parent.parent / "help_guides"


@dataclass(frozen=True)
class HelpGuideMeta:
    slug: str
    title: str
    summary: str
    order: int


# Order and metadata for Section 13 guides.
GUIDE_INDEX: tuple[HelpGuideMeta, ...] = (
    HelpGuideMeta(
        "connecting",
        "Connecting from phone and PC",
        "Add the server in Minecraft Bedrock and join on TCP 19132.",
        10,
    ),
    HelpGuideMeta(
        "port-forwarding",
        "Port forwarding for NetherNet",
        "Forward TCP 19132 and UDP 19140–19155 to your host.",
        20,
    ),
    HelpGuideMeta(
        "dns",
        "DNS and Cloudflare",
        "Game DNS must be DNS-only — proxies only carry HTTP.",
        30,
    ),
    HelpGuideMeta(
        "version-matching",
        "Version matching and pinning",
        "Keep server and clients on the same Bedrock build.",
        40,
    ),
    HelpGuideMeta(
        "mobile-carriers",
        "Mobile carriers and CGNAT",
        "Some cellular networks cannot reach home servers.",
        50,
    ),
    HelpGuideMeta(
        "addons",
        "Add-ons on dedicated servers",
        "BP+RP pairs, Marketplace limits, and experiments.",
        60,
    ),
    HelpGuideMeta(
        "console-basics",
        "Console basics",
        "Common commands; op/give require an online player.",
        70,
    ),
)


def guides_dir(settings: Settings | None = None) -> Path:
    """Return the directory that holds guide markdown files."""

    cfg = settings or get_settings()
    if cfg.help_guides_dir is not None:
        return Path(cfg.help_guides_dir)
    return _PACKAGE_GUIDES


def list_guides(settings: Settings | None = None) -> list[dict[str, str | int]]:
    """Return guide metadata for the Help index (authenticated)."""

    root = guides_dir(settings)
    out: list[dict[str, str | int]] = []
    for meta in GUIDE_INDEX:
        path = root / f"{meta.slug}.md"
        if not path.is_file():
            continue
        out.append(
            {
                "slug": meta.slug,
                "title": meta.title,
                "summary": meta.summary,
                "order": meta.order,
            }
        )
    return out


def get_guide(slug: str, settings: Settings | None = None) -> dict[str, str]:
    """Return one guide's markdown body.

    Raises:
        NotFoundError: unknown slug or missing file.
        AppError-equivalent via NotFoundError for path escape attempts.
    """

    cleaned = slug.strip().lower()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise NotFoundError("Help guide not found")
    meta = next((g for g in GUIDE_INDEX if g.slug == cleaned), None)
    if meta is None:
        raise NotFoundError("Help guide not found")
    path = guides_dir(settings) / f"{meta.slug}.md"
    if not path.is_file():
        raise NotFoundError("Help guide not found")
    body = path.read_text(encoding="utf-8")
    return {
        "slug": meta.slug,
        "title": meta.title,
        "summary": meta.summary,
        "markdown": body,
    }
