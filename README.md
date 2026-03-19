## Backend

This backend is a FastAPI middleware layer in front of InvenioILS.

### Current endpoints

- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/ingest`
- `POST /api/v1/qr/shelf`
- `GET /api/v1/qr/shelf.png`

### Environment variables

All variables are prefixed with `INVSCAN_`.

- `INVSCAN_JWT_SECRET_KEY`
- `INVSCAN_BOOTSTRAP_USERNAME`
- `INVSCAN_BOOTSTRAP_PASSWORD`
- `INVSCAN_INVENIO_BASE_URL`
- `INVSCAN_INVENIO_API_TOKEN`

### Local run

Install dependencies and run:

```bash
uv run python main.py
```

Or run with Uvicorn directly:

```bash
uv run uvicorn invenioscan.app:app --reload
```

### Current status

The InvenioILS adapter is still a stub that normalizes outbound metadata and includes shelf position information. Real remote persistence, queueing, and database-backed auditing are the next slice.
