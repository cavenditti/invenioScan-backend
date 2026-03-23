"""Web UI routes — serves Jinja2 templates with cookie-backed JWT auth."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Cookie, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.auth import create_access_token, hash_password, verify_password
from invenioscan.database import get_session
from invenioscan.models import Book, BookCopy, Shelf, User, UserStatus
from invenioscan.settings import Settings, get_settings

router = APIRouter(tags=["web"], include_in_schema=False)


def _templates(request: Request):
    from invenioscan.app import templates
    return templates


def _get_token_payload(request: Request, settings: Settings) -> dict | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return pyjwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except pyjwt.PyJWTError:
        return None


async def _get_web_user(request: Request, settings: Settings, session: AsyncSession) -> User | None:
    payload = _get_token_payload(request, settings)
    if not payload:
        return None
    user = await session.get(User, int(payload["sub"]))
    if user and user.is_active:
        return user
    return None


# ── Public pages ───────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    book_count = (await session.exec(select(func.count(Book.id)))).one()
    shelf_count = (await session.exec(select(func.count(Shelf.id)))).one()
    copy_count = (await session.exec(select(func.count(BookCopy.id)))).one()

    recent_books = list(
        (await session.exec(select(Book).order_by(Book.created_at.desc()).limit(10))).all()
    )

    return tpl.TemplateResponse(request, "index.html", {
        "user": user,
        "book_count": book_count,
        "shelf_count": shelf_count,
        "copy_count": copy_count,
        "recent_books": recent_books,
    })


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    tpl = _templates(request)
    return tpl.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    result = await session.exec(select(User).where(User.username == username))
    user = result.first()

    if not user or not verify_password(password, user.hashed_password):
        return tpl.TemplateResponse(request, "login.html", {"error": "Invalid credentials"})

    if user.status == UserStatus.PENDING:
        created = user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=UTC)
        expiry = created + timedelta(days=settings.registration_expiry_days)
        if datetime.now(UTC) > expiry:
            user.status = UserStatus.DENIED
            user.status_changed_at = datetime.now(UTC)
            session.add(user)
            await session.commit()

    if user.status != UserStatus.APPROVED:
        msg = "Account pending approval" if user.status == UserStatus.PENDING else "Account denied"
        return tpl.TemplateResponse(request, "login.html", {"error": msg})

    token, _ = create_access_token(user.id, user.username, user.is_admin, settings)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=settings.jwt_access_token_exp_minutes * 60)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    tpl = _templates(request)
    return tpl.TemplateResponse(request, "register.html", {"error": None})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    existing = await session.exec(
        select(User).where((User.username == username) | (User.email == email))
    )
    if existing.first():
        return tpl.TemplateResponse(request, "register.html", {"error": "Username or email already taken"})

    user = User(username=username, email=email, hashed_password=hash_password(password))
    session.add(user)
    await session.commit()
    return tpl.TemplateResponse(request, "register.html", {
        "error": None,
        "success": "Registration submitted! An admin must approve your account before you can log in.",
    })


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ── Books ──────────────────────────────────────

@router.get("/books", response_class=HTMLResponse)
async def books_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = None,
    page: int = Query(default=1, ge=1),
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    per_page = 50
    stmt = select(Book)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Book.title.ilike(like)) | (Book.author.ilike(like)) | (Book.isbn.ilike(like)))
    total = (await session.exec(select(func.count()).select_from(stmt.subquery()))).one()
    books = list((await session.exec(stmt.order_by(Book.created_at.desc()).offset((page - 1) * per_page).limit(per_page))).all())

    ctx = {"user": user, "books": books, "q": q or "", "page": page, "per_page": per_page, "total": total}

    if request.headers.get("HX-Request"):
        return tpl.TemplateResponse(request, "partials/book_rows.html", ctx)
    return tpl.TemplateResponse(request, "books.html", ctx)


@router.get("/books/{book_id}", response_class=HTMLResponse)
async def book_detail_page(
    request: Request,
    book_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    book = await session.get(Book, book_id)
    if not book:
        return RedirectResponse("/books", status_code=302)

    copies = list((await session.exec(select(BookCopy).where(BookCopy.book_id == book_id))).all())
    shelves = {}
    for c in copies:
        if c.shelf_id not in shelves:
            shelves[c.shelf_id] = await session.get(Shelf, c.shelf_id)

    return tpl.TemplateResponse(request, "book_detail.html", {
        "user": user, "book": book, "copies": copies, "shelves": shelves,
    })


# ── Shelves ────────────────────────────────────

@router.get("/shelves", response_class=HTMLResponse)
async def shelves_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    shelves_list = list((await session.exec(select(Shelf).order_by(Shelf.shelf_id))).all())

    # Count copies per shelf
    shelf_copy_counts = {}
    for s in shelves_list:
        count = (await session.exec(select(func.count(BookCopy.id)).where(BookCopy.shelf_id == s.id))).one()
        shelf_copy_counts[s.id] = count

    return tpl.TemplateResponse(request, "shelves.html", {
        "user": user, "shelves": shelves_list, "shelf_copy_counts": shelf_copy_counts,
    })


@router.get("/shelves/{shelf_db_id}", response_class=HTMLResponse)
async def shelf_detail_page(
    request: Request,
    shelf_db_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    shelf = await session.get(Shelf, shelf_db_id)
    if not shelf:
        return RedirectResponse("/shelves", status_code=302)

    copies = list((await session.exec(select(BookCopy).where(BookCopy.shelf_id == shelf_db_id).order_by(BookCopy.row, BookCopy.position))).all())
    books = {}
    for c in copies:
        if c.book_id not in books:
            books[c.book_id] = await session.get(Book, c.book_id)

    return tpl.TemplateResponse(request, "shelf_detail.html", {
        "user": user, "shelf": shelf, "copies": copies, "books": books,
    })


# ── Admin ──────────────────────────────────────

@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = Query(default=None, alias="status"),
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user or not user.is_admin:
        return RedirectResponse("/login", status_code=302)

    stmt = select(User)
    if status_filter:
        stmt = stmt.where(User.status == status_filter)
    stmt = stmt.order_by(User.created_at.desc())
    users = list((await session.exec(stmt)).all())

    return tpl.TemplateResponse(request, "admin_users.html", {
        "user": user, "users": users, "status_filter": status_filter or "",
    })
