## Backend

This backend is a FastAPI middleware layer in front of InvenioILS.

### Current endpoints

- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/ingest`
- `POST /api/v1/ingest/upload`
- `POST /api/v1/qr/shelf`
- `GET /api/v1/qr/shelf.png`
- `POST /api/v1/qr/sheet`

### Environment variables

All variables are prefixed with `INVSCAN_`.

- `INVSCAN_JWT_SECRET_KEY`
- `INVSCAN_BOOTSTRAP_USERNAME`
- `INVSCAN_BOOTSTRAP_PASSWORD`
- `INVSCAN_INVENIO_BASE_URL`
- `INVSCAN_INVENIO_API_TOKEN`
- `INVSCAN_INVENIO_DEFAULT_INTERNAL_LOCATION_PID`
- `INVSCAN_INVENIO_DEFAULT_LANGUAGE`
- `INVSCAN_INVENIO_DEFAULT_BOOK_DOCUMENT_TYPE`
- `INVSCAN_INVENIO_DEFAULT_IMAGE_DOCUMENT_TYPE`
- `INVSCAN_INVENIO_DEFAULT_ITEM_MEDIUM`
- `INVSCAN_INVENIO_DEFAULT_ITEM_STATUS`
- `INVSCAN_INVENIO_DEFAULT_ITEM_CIRCULATION_RESTRICTION`
- `INVSCAN_INVENIO_DEFAULT_EITEM_TYPE`
- `INVSCAN_PUBLIC_BASE_URL`
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

### Current status

The InvenioILS adapter now performs real HTTP calls against the document, item, and e-item APIs.

- Every ingest creates a document.
- ISBN ingests also create a physical item when `INVSCAN_INVENIO_DEFAULT_INTERNAL_LOCATION_PID` is configured.
- Image uploads are stored by this backend under `/uploads` and then submitted to InvenioILS as public image-reference URLs.
- The QR utility can render a printable HTML sheet of labels such as `A1-3`.

The adapter synthesizes minimal required document fields when the mobile payload does not provide them yet, and it stores invscan provenance in keywords and internal notes.
