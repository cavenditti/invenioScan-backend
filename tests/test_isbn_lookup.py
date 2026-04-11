"""Unit tests for the ISBN lookup module."""

import pytest

from invenioscan.isbn_lookup import _extract_year, _parse_response, lookup_isbn
from invenioscan.settings import Settings


# ── Year extraction ───────────────────────────────────────

@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("2009", 2009),
        ("March 2009", 2009),
        ("2009-03-15", 2009),
        ("January 1, 1925", 1925),
        ("c1998", 1998),
        ("", None),
        (None, None),
        ("no year here", None),
    ],
)
def test_extract_year(input_str, expected):
    assert _extract_year(input_str) == expected


# ── Response parsing ──────────────────────────────────────

SAMPLE_OL_DATA = {
    "title": "Fantastic Mr. Fox",
    "authors": [{"name": "Roald Dahl", "url": "https://openlibrary.org/authors/OL34184A"}],
    "publish_date": "October 1, 1988",
    "cover": {
        "small": "https://covers.openlibrary.org/b/id/9259131-S.jpg",
        "medium": "https://covers.openlibrary.org/b/id/9259131-M.jpg",
        "large": "https://covers.openlibrary.org/b/id/9259131-L.jpg",
    },
    "number_of_pages": 96,
    "publishers": [{"name": "Puffin Books"}],
    "subjects": [
        {"name": "Animals", "url": "https://openlibrary.org/subjects/animals"},
        {"name": "Children's fiction", "url": "https://openlibrary.org/subjects/children's_fiction"},
    ],
    "identifiers": {
        "isbn_10": ["0140328726"],
        "isbn_13": ["9780140328721"],
        "goodreads": ["6689"],
    },
}


def test_parse_response_full():
    result = _parse_response(SAMPLE_OL_DATA)
    assert result["title"] == "Fantastic Mr. Fox"
    assert result["author"] == "Roald Dahl"
    assert result["publication_year"] == 1988
    assert result["cover_image_url"] == "https://covers.openlibrary.org/b/id/9259131-M.jpg"
    assert result["number_of_pages"] == 96
    assert result["publishers"] == ["Puffin Books"]
    assert "Animals" in result["subjects"]
    assert result["identifiers"]["isbn_13"] == ["9780140328721"]
    assert result["publish_date_raw"] == "October 1, 1988"


def test_parse_response_minimal():
    result = _parse_response({"title": "Unknown Book"})
    assert result["title"] == "Unknown Book"
    assert result["author"] is None
    assert result["publication_year"] is None
    assert result["cover_image_url"] is None
    assert result["publishers"] == []
    assert result["subjects"] == []


def test_parse_response_multiple_authors():
    data = {
        "title": "Good Omens",
        "authors": [
            {"name": "Terry Pratchett"},
            {"name": "Neil Gaiman"},
        ],
    }
    result = _parse_response(data)
    assert result["author"] == "Terry Pratchett, Neil Gaiman"


# ── lookup_isbn integration (mocked HTTP) ─────────────────

@pytest.fixture
def settings():
    return Settings(
        isbn_lookup_enabled=True,
        isbn_lookup_timeout_seconds=2.0,
        jwt_secret_key="test-secret-key",
    )


@pytest.fixture
def disabled_settings():
    return Settings(
        isbn_lookup_enabled=False,
        jwt_secret_key="test-secret-key",
    )


async def test_lookup_isbn_disabled(disabled_settings):
    result = await lookup_isbn("9780140328721", disabled_settings)
    assert result is None


async def test_lookup_isbn_success(settings, monkeypatch):
    api_response = {"ISBN:9780140328721": SAMPLE_OL_DATA}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return api_response

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse()

    import invenioscan.isbn_lookup as mod
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())

    result = await lookup_isbn("9780140328721", settings)
    assert result is not None
    assert result["title"] == "Fantastic Mr. Fox"
    assert result["author"] == "Roald Dahl"
    assert result["publication_year"] == 1988


async def test_lookup_isbn_not_found(settings, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())

    result = await lookup_isbn("0000000000000", settings)
    assert result is None


async def test_lookup_isbn_timeout(settings, monkeypatch):
    import httpx

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())

    result = await lookup_isbn("9780140328721", settings)
    assert result is None


async def test_lookup_isbn_http_error(settings, monkeypatch):
    import httpx

    class FakeResponse:
        status_code = 500

        def raise_for_status(self):
            raise httpx.HTTPStatusError("Server Error", request=None, response=self)

        def json(self):
            return {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())

    result = await lookup_isbn("9780140328721", settings)
    assert result is None
