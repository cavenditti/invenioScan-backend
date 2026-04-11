"""Integration tests for the new standalone backend (auth, books, shelves, ingest)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import invenioscan.database as db_module
from invenioscan.auth import hash_password
from invenioscan.models import User, UserStatus

# Use in-memory SQLite for tests
TEST_ENGINE = create_async_engine("sqlite+aiosqlite://", echo=False)


@pytest.fixture(autouse=True)
async def setup_db():
    """Create a fresh in-memory DB for each test, patching the module-level engine."""
    # Patch the engine used by the rest of the app
    original_engine = db_module.engine
    db_module.engine = TEST_ENGINE

    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed bootstrap admin
    async with AsyncSession(TEST_ENGINE) as session:
        admin = User(
            username="admin",
            email="admin@localhost",
            hashed_password=hash_password("admin"),
            is_admin=True,
            is_active=True,
            status=UserStatus.APPROVED,
        )
        session.add(admin)
        await session.commit()

    yield

    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    db_module.engine = original_engine


@pytest.fixture
async def client():
    # Re-import after patching: override the get_session dependency
    from invenioscan.app import create_app
    from invenioscan.database import get_session as original_get_session

    app = create_app()

    # Override the DB session dependency to use test engine
    async def _test_get_session():
        async with AsyncSession(TEST_ENGINE) as session:
            yield session

    app.dependency_overrides[original_get_session] = _test_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register_and_login(client: AsyncClient, username="testuser", password="testpass123", email="test@test.com"):
    """Helper: register a user, approve them via admin, return their token."""
    # Register
    resp = await client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "password": password,
    })
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Login as admin to approve
    admin_resp = await client.post("/api/v1/auth/login", data={
        "username": "admin", "password": "admin",
    })
    assert admin_resp.status_code == 200
    admin_token = admin_resp.json()["access_token"]

    # Approve
    approve_resp = await client.post(
        f"/api/v1/admin/users/{user_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve_resp.status_code == 200

    # Login as user
    login_resp = await client.post("/api/v1/auth/login", data={
        "username": username, "password": password,
    })
    assert login_resp.status_code == 200
    return login_resp.json()["access_token"]


async def test_health(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_cors_preflight_allows_local_web_app(client: AsyncClient):
    resp = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:8081"
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()
    assert "content-type" in resp.headers["access-control-allow-headers"].lower()


async def test_register_and_login_flow(client: AsyncClient):
    # Register
    resp = await client.post("/api/v1/auth/register", json={
        "username": "newuser", "email": "new@test.com", "password": "pass123456",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"

    # Cannot login while pending
    login_resp = await client.post("/api/v1/auth/login", data={
        "username": "newuser", "password": "pass123456",
    })
    assert login_resp.status_code == 403

    # Admin approves
    admin_resp = await client.post("/api/v1/auth/login", data={
        "username": "admin", "password": "admin",
    })
    admin_token = admin_resp.json()["access_token"]
    user_id = resp.json()["id"]

    approve_resp = await client.post(
        f"/api/v1/admin/users/{user_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # Now login works
    login_resp = await client.post("/api/v1/auth/login", data={
        "username": "newuser", "password": "pass123456",
    })
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


async def test_books_crud(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    resp = await client.post("/api/v1/books", json={
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "isbn": "9780743273565",
        "publication_year": 1925,
    }, headers=headers)
    assert resp.status_code == 201
    book = resp.json()
    assert book["title"] == "The Great Gatsby"
    book_id = book["id"]

    # Read
    resp = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["isbn"] == "9780743273565"

    # Update
    resp = await client.put(f"/api/v1/books/{book_id}", json={
        "notes": "Classic American novel",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Classic American novel"

    # List with search
    resp = await client.get("/api/v1/books?q=gatsby", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_shelves_crud(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    resp = await client.post("/api/v1/shelves", json={
        "shelf_id": "A1", "label": "Living room shelf",
    }, headers=headers)
    assert resp.status_code == 201
    shelf = resp.json()
    assert shelf["shelf_id"] == "A1"

    # Duplicate fails
    resp = await client.post("/api/v1/shelves", json={
        "shelf_id": "A1",
    }, headers=headers)
    assert resp.status_code == 409

    # List
    resp = await client.get("/api/v1/shelves", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_ingest_isbn(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/ingest", json={
        "shelf": {"shelf_id": "B2", "row": "1", "position": 3, "height": 2},
        "source_type": "isbn",
        "isbn": "9780140449136",
        "title": "War and Peace",
        "author": "Leo Tolstoy",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "created"
    assert data["book_id"] >= 1
    assert data["copy_id"] >= 1
    assert len(data["scan_id"]) > 0

    # Verify book was created
    resp = await client.get(f"/api/v1/books/{data['book_id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "War and Peace"
    assert len(resp.json()["copies"]) == 1

    # Second ingest with same ISBN reuses the book
    resp = await client.post("/api/v1/ingest", json={
        "shelf": {"shelf_id": "B2", "row": "2", "position": 1, "height": 2},
        "source_type": "isbn",
        "isbn": "9780140449136",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["book_id"] == data["book_id"]
    assert resp.json()["copy_id"] != data["copy_id"]


async def test_copies_crud(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create book and shelf first
    book_resp = await client.post("/api/v1/books", json={"title": "Test Book"}, headers=headers)
    book_id = book_resp.json()["id"]
    shelf_resp = await client.post("/api/v1/shelves", json={"shelf_id": "X1"}, headers=headers)
    shelf_id = shelf_resp.json()["id"]

    # Create copy
    resp = await client.post(f"/api/v1/books/{book_id}/copies", json={
        "shelf_id": shelf_id, "row": "A", "position": 1, "height": 3,
    }, headers=headers)
    assert resp.status_code == 201
    copy_id = resp.json()["id"]

    # Update copy
    resp = await client.put(f"/api/v1/copies/{copy_id}", json={
        "position": 5,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["position"] == 5

    # Delete copy
    resp = await client.delete(f"/api/v1/copies/{copy_id}", headers=headers)
    assert resp.status_code == 204


async def test_admin_required_for_delete(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create book
    resp = await client.post("/api/v1/books", json={"title": "To Delete"}, headers=headers)
    book_id = resp.json()["id"]

    # Non-admin cannot delete book
    resp = await client.delete(f"/api/v1/books/{book_id}", headers=headers)
    assert resp.status_code == 403

    # Admin can
    admin_resp = await client.post("/api/v1/auth/login", data={
        "username": "admin", "password": "admin",
    })
    admin_headers = {"Authorization": f"Bearer {admin_resp.json()['access_token']}"}
    resp = await client.delete(f"/api/v1/books/{book_id}", headers=admin_headers)
    assert resp.status_code == 204


# ── ISBN enrichment integration tests ─────────────────────

SAMPLE_OL_RESPONSE = {
    "ISBN:9780140328721": {
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
        "subjects": [{"name": "Animals", "url": "https://openlibrary.org/subjects/animals"}],
        "identifiers": {"isbn_13": ["9780140328721"], "isbn_10": ["0140328726"]},
    }
}


def _patch_isbn_lookup(monkeypatch, response_data):
    """Patch httpx.AsyncClient to return *response_data* for any GET."""
    import httpx

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return response_data

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())


async def test_ingest_isbn_enriched(client: AsyncClient, monkeypatch):
    """ISBN ingest with Open Library data fills title, author, cover, extra."""
    _patch_isbn_lookup(monkeypatch, SAMPLE_OL_RESPONSE)

    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/ingest", json={
        "shelf": {"shelf_id": "E1", "row": "1", "position": 1, "height": 2},
        "source_type": "isbn",
        "isbn": "9780140328721",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Fantastic Mr. Fox"
    assert data["author"] == "Roald Dahl"
    assert data["cover_image_url"] == "https://covers.openlibrary.org/b/id/9259131-M.jpg"
    assert data["enriched"] is True

    # Verify persisted book
    book_resp = await client.get(f"/api/v1/books/{data['book_id']}", headers=headers)
    book = book_resp.json()
    assert book["title"] == "Fantastic Mr. Fox"
    assert book["author"] == "Roald Dahl"
    assert book["publication_year"] == 1988
    assert book["extra"]["publishers"] == ["Puffin Books"]
    assert book["extra"]["number_of_pages"] == 96


async def test_ingest_isbn_user_metadata_wins(client: AsyncClient, monkeypatch):
    """User-provided title/author override Open Library data."""
    _patch_isbn_lookup(monkeypatch, SAMPLE_OL_RESPONSE)

    token = await _register_and_login(client, username="user2", email="user2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/ingest", json={
        "shelf": {"shelf_id": "E2", "row": "1", "position": 1, "height": 2},
        "source_type": "isbn",
        "isbn": "9780140328721",
        "title": "My Custom Title",
        "author": "Custom Author",
        "publication_year": 2000,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Custom Title"
    assert data["author"] == "Custom Author"
    # Cover still comes from lookup since user can't provide one via ISBN ingest
    assert data["cover_image_url"] == "https://covers.openlibrary.org/b/id/9259131-M.jpg"
    assert data["enriched"] is True

    book_resp = await client.get(f"/api/v1/books/{data['book_id']}", headers=headers)
    book = book_resp.json()
    assert book["publication_year"] == 2000


async def test_ingest_isbn_lookup_failure_graceful(client: AsyncClient, monkeypatch):
    """When Open Library is unreachable, ingest still succeeds with fallback data."""
    import httpx

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())

    token = await _register_and_login(client, username="user3", email="user3@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/ingest", json={
        "shelf": {"shelf_id": "E3", "row": "1", "position": 1, "height": 2},
        "source_type": "isbn",
        "isbn": "9780000000000",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    # Falls back to ISBN as title
    assert data["title"] == "9780000000000"
    assert data["enriched"] is False
