"""Global pytest configuration — sets required environment variables before any module import."""

import os

# Must be set before `invenioscan.settings` is imported so Pydantic validation passes.
os.environ.setdefault("INVSCAN_JWT_SECRET_KEY", "test-secret-key-only-for-pytest-do-not-use-in-production")
# Disable secure-only cookie flag so httpx (HTTP) test client can send/receive cookies.
os.environ.setdefault("INVSCAN_COOKIE_SECURE", "false")
