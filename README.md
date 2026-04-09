# Backend

> I'm helping a friend moving lots of books.
> I built a system to quickly catalog books using QR codes and a mobile app.
> Claude (and others) are helping me helping my friend. 🙂
> This repo is the codebase for that project.

This repository contains the FastAPI backend for the main Shelfscan project:
https://github.com/cavenditti/invenioScan

The backend is a standalone FastAPI application with SQLite persistence (via SQLModel), a web UI (Jinja2 + HTMX + Pico CSS), and a JSON API for the mobile app.

### API endpoints

- `GET  /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login` (OAuth2 password flow)
- `GET  /api/v1/auth/me`
- `GET|POST|PUT|DELETE /api/v1/books`
- `GET|POST|PUT|DELETE /api/v1/shelves`
- `GET|POST|PUT|DELETE /api/v1/books/{id}/copies`, `/api/v1/copies/{id}`
- `GET|POST /api/v1/admin/users`, `/api/v1/admin/users/{id}/approve|deny`
- `POST /api/v1/ingest`, `/api/v1/ingest/upload`
- `POST /api/v1/qr/shelf`, `GET /api/v1/qr/shelf.png`, `POST /api/v1/qr/sheet`

### Web UI pages

- `/` — Dashboard (book/shelf/copy counts, recent books)
- `/books` — Searchable book list (HTMX live search)
- `/books/{id}` — Book detail with copies
- `/shelves`, `/shelves/{id}` — Shelf list and detail
- `/admin/users` — User management (approve/deny)
- `/login`, `/register`, `/logout`

### Environment variables

All variables are prefixed with `INVSCAN_`.

- `INVSCAN_DATABASE_URL` — SQLAlchemy URL (default: `sqlite+aiosqlite:///./invenioscan.db`)
- `INVSCAN_CORS_ALLOWED_ORIGINS` — JSON array of allowed browser origins (default includes `http://localhost:8081` and `http://127.0.0.1:8081` for the web app)
- `INVSCAN_JWT_SECRET_KEY`
- `INVSCAN_BOOTSTRAP_ADMIN_USERNAME` / `_PASSWORD` / `_EMAIL`
- `INVSCAN_REGISTRATION_EXPIRY_DAYS` — Auto-deny pending users after N days (default: 7)
- `INVSCAN_UPLOAD_DIR`

### Local run

Install dependencies and run:

```bash
uv run python main.py
```

Or run with Uvicorn directly:

```bash
uv run uvicorn invenioscan.app:app --reload
```

### Running tests

```bash
uv run pytest tests/ -v
```
