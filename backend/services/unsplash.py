from __future__ import annotations

from urllib.parse import quote_plus


def build_unsplash_url(
    query: str,
    *,
    width: int = 1080,
    height: int = 1920,
    quality: int = 80,
    fit: str = "crop",
) -> str:
    clean_query = ",".join(
        part.strip().replace(" ", "-")
        for part in query.split(",")
        if part.strip()
    ) or "premium-editorial"
    return (
        f"https://source.unsplash.com/featured/{width}x{height}/?"
        f"{quote_plus(clean_query)}&q={quality}&fit={fit}"
    )
