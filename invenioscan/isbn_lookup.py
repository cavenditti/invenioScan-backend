"""Fetch book metadata from the Open Library Books API by ISBN."""

from __future__ import annotations

import logging
import re

import httpx

from invenioscan.settings import Settings

logger = logging.getLogger(__name__)

OPEN_LIBRARY_BOOKS_URL = "https://openlibrary.org/api/books"

_YEAR_RE = re.compile(r"(\d{4})")


def _extract_year(publish_date: str | None) -> int | None:
    """Pull the first 4-digit year out of a free-form publish_date string."""
    if not publish_date:
        return None
    m = _YEAR_RE.search(publish_date)
    return int(m.group(1)) if m else None


def _parse_response(data: dict) -> dict:
    """Normalise a single Open Library ``jscmd=data`` record into a flat dict."""
    authors_list = [a["name"] for a in data.get("authors", []) if a.get("name")]
    cover = data.get("cover") or {}

    return {
        "title": data.get("title"),
        "author": ", ".join(authors_list) if authors_list else None,
        "publication_year": _extract_year(data.get("publish_date")),
        "cover_image_url": cover.get("medium") or cover.get("large") or cover.get("small"),
        "number_of_pages": data.get("number_of_pages"),
        "publishers": [p["name"] for p in data.get("publishers", []) if p.get("name")],
        "subjects": [s["name"] for s in data.get("subjects", []) if s.get("name")],
        "identifiers": data.get("identifiers"),
        "publish_date_raw": data.get("publish_date"),
    }


async def lookup_isbn(isbn: str, settings: Settings) -> dict | None:
    """Look up an ISBN via the Open Library Books API.

    Returns a normalised metadata dict on success, or ``None`` when the
    lookup is disabled, the ISBN is not found, or any error occurs.
    """
    if not settings.isbn_lookup_enabled:
        return None

    bib_key = f"ISBN:{isbn}"
    params = {"bibkeys": bib_key, "jscmd": "data", "format": "json"}

    try:
        logger.info("ISBN lookup: querying Open Library for %s", isbn)
        async with httpx.AsyncClient(timeout=settings.isbn_lookup_timeout_seconds) as client:
            resp = await client.get(OPEN_LIBRARY_BOOKS_URL, params=params)
            resp.raise_for_status()

        payload = resp.json()
        if bib_key not in payload:
            logger.info("ISBN lookup: no results for %s", isbn)
            return None

        result = _parse_response(payload[bib_key])
        logger.info("ISBN lookup: found '%s' for %s", result.get("title"), isbn)
        return result

    except httpx.TimeoutException:
        logger.warning("ISBN lookup: timeout for %s", isbn)
        return None
    except Exception:
        logger.warning("ISBN lookup: error for %s", isbn, exc_info=True)
        return None
