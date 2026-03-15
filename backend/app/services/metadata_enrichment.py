"""Enrich book metadata via OpenLibrary API."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)

OPENLIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPENLIBRARY_COVERS = "https://covers.openlibrary.org/b/olid/{}-L.jpg"


async def enrich_from_openlibrary(
    title: str,
    author: str | None = None,
) -> dict:
    """Search OpenLibrary for book metadata.

    Returns dict with optional keys:
    - description: str
    - subjects: list[str]
    - cover_url: str (high-res cover URL)
    - first_publish_year: int
    - number_of_pages: int
    - ol_key: str (OpenLibrary work key)
    """
    params: dict = {
        "q": title,
        "limit": 3,
        "fields": (
            "key,title,author_name,first_publish_year,"
            "cover_edition_key,subject,number_of_pages_median,edition_key"
        ),
    }
    if author:
        params["author"] = author

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(OPENLIBRARY_SEARCH, params=params)
            resp.raise_for_status()
            data = resp.json()

            docs = data.get("docs", [])
            if not docs:
                logger.info("openlibrary_no_results", title=title, author=author)
                return {}

            # Pick best match (first result)
            doc = docs[0]
            result: dict = {}

            # Cover image
            cover_key = doc.get("cover_edition_key")
            if cover_key:
                result["cover_url"] = OPENLIBRARY_COVERS.format(cover_key)

            # Subjects (top 10)
            subjects = doc.get("subject", [])
            if subjects:
                result["subjects"] = subjects[:10]

            # Pages
            pages = doc.get("number_of_pages_median")
            if pages:
                result["number_of_pages"] = pages

            # Year
            year = doc.get("first_publish_year")
            if year:
                result["first_publish_year"] = year

            # OpenLibrary key
            ol_key = doc.get("key")
            if ol_key:
                result["ol_key"] = ol_key

            # Fetch work details for description
            if ol_key:
                try:
                    work_resp = await client.get(
                        f"https://openlibrary.org{ol_key}.json",
                    )
                    if work_resp.status_code == 200:
                        work = work_resp.json()
                        desc = work.get("description")
                        if isinstance(desc, dict):
                            desc = desc.get("value", "")
                        if desc and isinstance(desc, str):
                            result["description"] = desc[:1000]
                except httpx.HTTPError:
                    pass  # Description is optional

        logger.info(
            "openlibrary_enriched",
            title=title,
            keys=list(result.keys()),
        )
        return result

    except httpx.HTTPError:
        logger.warning("openlibrary_fetch_failed", title=title, exc_info=True)
        return {}
