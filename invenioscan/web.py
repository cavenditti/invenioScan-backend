"""Web UI routes — serves Jinja2 templates with cookie-backed JWT auth."""

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Cookie, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.auth import create_access_token, hash_password, verify_password
from invenioscan.database import get_session
from invenioscan.isbn_lookup import lookup_isbn
from invenioscan.models import Book, BookCopy, Shelf, User, UserStatus
from invenioscan.qr import build_shelf_label, build_shelf_payload, generate_qr_svg, render_printable_qr_sheet
from invenioscan.schemas import ShelfPosition
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


@router.get("/books/new", response_class=HTMLResponse)
async def book_create_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return tpl.TemplateResponse(request, "book_form.html", {"user": user, "book": None, "error": None})


@router.post("/books/new", response_class=HTMLResponse)
async def book_create_submit(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    title: Annotated[str, Form()],
    author: Annotated[str, Form()] = "",
    isbn: Annotated[str, Form()] = "",
    publication_year: Annotated[str, Form()] = "",
    document_type: Annotated[str, Form()] = "BOOK",
    language: Annotated[str, Form()] = "",
    cover_image_url: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    extra: Annotated[str, Form()] = "",
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    extra_dict = None
    if extra.strip():
        try:
            extra_dict = json.loads(extra)
            if not isinstance(extra_dict, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            return tpl.TemplateResponse(request, "book_form.html", {
                "user": user, "book": None, "error": "Extra metadata must be a valid JSON object.",
            })

    pub_year = int(publication_year) if publication_year.strip() else None

    book = Book(
        title=title.strip(),
        author=author.strip() or None,
        isbn=isbn.strip() or None,
        publication_year=pub_year,
        document_type=document_type,
        language=language.strip() or None,
        cover_image_url=cover_image_url.strip() or None,
        notes=notes.strip() or None,
        extra=extra_dict,
        created_by_id=user.id,
    )
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return RedirectResponse(f"/books/{book.id}", status_code=302)


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

    all_shelves = list((await session.exec(select(Shelf).order_by(Shelf.shelf_id))).all())

    return tpl.TemplateResponse(request, "book_detail.html", {
        "user": user, "book": book, "copies": copies, "shelves": shelves,
        "all_shelves": all_shelves,
    })


@router.get("/books/{book_id}/edit", response_class=HTMLResponse)
async def book_edit_page(
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
    return tpl.TemplateResponse(request, "book_form.html", {"user": user, "book": book, "error": None})


@router.post("/books/{book_id}/edit", response_class=HTMLResponse)
async def book_edit_submit(
    request: Request,
    book_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    title: Annotated[str, Form()],
    author: Annotated[str, Form()] = "",
    isbn: Annotated[str, Form()] = "",
    publication_year: Annotated[str, Form()] = "",
    document_type: Annotated[str, Form()] = "BOOK",
    language: Annotated[str, Form()] = "",
    cover_image_url: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    extra: Annotated[str, Form()] = "",
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    book = await session.get(Book, book_id)
    if not book:
        return RedirectResponse("/books", status_code=302)

    extra_dict = None
    if extra.strip():
        try:
            extra_dict = json.loads(extra)
            if not isinstance(extra_dict, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            return tpl.TemplateResponse(request, "book_form.html", {
                "user": user, "book": book, "error": "Extra metadata must be a valid JSON object.",
            })

    book.title = title.strip()
    book.author = author.strip() or None
    book.isbn = isbn.strip() or None
    book.publication_year = int(publication_year) if publication_year.strip() else None
    book.document_type = document_type
    book.language = language.strip() or None
    book.cover_image_url = cover_image_url.strip() or None
    book.notes = notes.strip() or None
    book.extra = extra_dict
    book.updated_at = datetime.now(UTC)

    session.add(book)
    await session.commit()
    return RedirectResponse(f"/books/{book.id}", status_code=302)


@router.post("/books/{book_id}/enrich")
async def book_enrich(
    request: Request,
    book_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    book = await session.get(Book, book_id)
    if not book or not book.isbn:
        return RedirectResponse(f"/books/{book_id}", status_code=302)

    lookup = await lookup_isbn(book.isbn, settings)
    if lookup:
        for field, key in [
            ("title", "title"),
            ("author", "author"),
            ("publication_year", "publication_year"),
            ("cover_image_url", "cover_image_url"),
        ]:
            value = lookup.get(key)
            if value is not None:
                setattr(book, field, value)

        extra = dict(book.extra) if book.extra else {}
        for key in ("publishers", "subjects", "identifiers", "number_of_pages", "publish_date_raw"):
            if lookup.get(key) is not None:
                extra[key] = lookup[key]
        if extra:
            book.extra = extra

        book.updated_at = datetime.now(UTC)
        session.add(book)
        await session.commit()

    return RedirectResponse(f"/books/{book_id}", status_code=302)


@router.post("/books/{book_id}/delete")
async def book_delete(
    request: Request,
    book_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    user = await _get_web_user(request, settings, session)
    if not user or not user.is_admin:
        return RedirectResponse("/login", status_code=302)
    book = await session.get(Book, book_id)
    if book:
        copies = list((await session.exec(select(BookCopy).where(BookCopy.book_id == book_id))).all())
        for c in copies:
            await session.delete(c)
        await session.delete(book)
        await session.commit()
    return RedirectResponse("/books", status_code=302)


@router.post("/books/{book_id}/copies")
async def copy_create(
    request: Request,
    book_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    shelf_id: Annotated[int, Form()],
    row: Annotated[str, Form()],
    position: Annotated[int, Form()],
    height: Annotated[int, Form()],
    notes: Annotated[str, Form()] = "",
):
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    book = await session.get(Book, book_id)
    if not book:
        return RedirectResponse("/books", status_code=302)

    copy = BookCopy(
        book_id=book_id,
        shelf_id=shelf_id,
        row=row.strip(),
        position=position,
        height=height,
        notes=notes.strip() or None,
    )
    session.add(copy)
    await session.commit()
    return RedirectResponse(f"/books/{book_id}", status_code=302)


@router.post("/copies/{copy_id}/delete")
async def copy_delete(
    request: Request,
    copy_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    copy = await session.get(BookCopy, copy_id)
    if copy:
        book_id = copy.book_id
        await session.delete(copy)
        await session.commit()
        return RedirectResponse(f"/books/{book_id}", status_code=302)
    return RedirectResponse("/books", status_code=302)


@router.post("/copies/{copy_id}/move")
async def copy_move(
    request: Request,
    copy_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    shelf_id: Annotated[int, Form()],
    row: Annotated[str, Form()],
    position: Annotated[int, Form()],
    height: Annotated[int, Form()],
):
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    copy = await session.get(BookCopy, copy_id)
    if not copy:
        return RedirectResponse("/books", status_code=302)
    copy.shelf_id = shelf_id
    copy.row = row.strip()
    copy.position = position
    copy.height = height
    copy.updated_at = datetime.now(UTC)
    session.add(copy)
    await session.commit()
    return RedirectResponse(f"/books/{copy.book_id}", status_code=302)


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

    shelf_copy_counts = {}
    for s in shelves_list:
        count = (await session.exec(select(func.count(BookCopy.id)).where(BookCopy.shelf_id == s.id))).one()
        shelf_copy_counts[s.id] = count

    return tpl.TemplateResponse(request, "shelves.html", {
        "user": user, "shelves": shelves_list, "shelf_copy_counts": shelf_copy_counts,
    })


@router.get("/shelves/new", response_class=HTMLResponse)
async def shelf_create_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return tpl.TemplateResponse(request, "shelf_form.html", {"user": user, "shelf": None, "error": None})


@router.post("/shelves/new", response_class=HTMLResponse)
async def shelf_create_submit(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    shelf_id: Annotated[str, Form()],
    label: Annotated[str, Form()] = "",
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    existing = (await session.exec(select(Shelf).where(Shelf.shelf_id == shelf_id.strip()))).first()
    if existing:
        return tpl.TemplateResponse(request, "shelf_form.html", {
            "user": user, "shelf": None, "error": f"A shelf with ID '{shelf_id.strip()}' already exists.",
        })

    shelf = Shelf(shelf_id=shelf_id.strip(), label=label.strip() or None)
    session.add(shelf)
    await session.commit()
    await session.refresh(shelf)
    return RedirectResponse(f"/shelves/{shelf.id}", status_code=302)


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


@router.get("/shelves/{shelf_db_id}/edit", response_class=HTMLResponse)
async def shelf_edit_page(
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
    return tpl.TemplateResponse(request, "shelf_form.html", {"user": user, "shelf": shelf, "error": None})


@router.post("/shelves/{shelf_db_id}/edit", response_class=HTMLResponse)
async def shelf_edit_submit(
    request: Request,
    shelf_db_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    shelf_id: Annotated[str, Form()],
    label: Annotated[str, Form()] = "",
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    shelf = await session.get(Shelf, shelf_db_id)
    if not shelf:
        return RedirectResponse("/shelves", status_code=302)

    shelf.label = label.strip() or None
    shelf.updated_at = datetime.now(UTC)
    session.add(shelf)
    await session.commit()
    return RedirectResponse(f"/shelves/{shelf.id}", status_code=302)


@router.post("/shelves/{shelf_db_id}/delete")
async def shelf_delete(
    request: Request,
    shelf_db_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    shelf = await session.get(Shelf, shelf_db_id)
    if not shelf:
        return RedirectResponse("/shelves", status_code=302)

    copy_count = (await session.exec(select(func.count(BookCopy.id)).where(BookCopy.shelf_id == shelf_db_id))).one()
    if copy_count > 0:
        return RedirectResponse(f"/shelves/{shelf_db_id}?error=Cannot+delete+shelf+with+copies", status_code=302)

    await session.delete(shelf)
    await session.commit()
    return RedirectResponse("/shelves", status_code=302)


@router.get("/qr", response_class=HTMLResponse)
async def qr_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tpl = _templates(request)
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return tpl.TemplateResponse(request, "qr.html", {"user": user})


@router.post("/qr", response_class=HTMLResponse)
async def qr_generate(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    shelf_id: Annotated[str, Form()],
    rows: Annotated[str, Form()],
    pos_from: Annotated[int, Form()],
    pos_to: Annotated[int, Form()],
    height: Annotated[int, Form()],
):
    user = await _get_web_user(request, settings, session)
    if not user:
        return RedirectResponse("/login", status_code=302)

    labels = []
    for row in [r.strip() for r in rows.split(",") if r.strip()]:
        for pos in range(pos_from, pos_to + 1):
            sp = ShelfPosition(shelf_id=shelf_id.strip(), row=row, position=pos, height=height)
            text = f"{shelf_id.strip()} · {build_shelf_label(row, pos, height)}"
            labels.append((sp, text))

    html = render_printable_qr_sheet(labels, settings)
    return HTMLResponse(content=html)


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
        "flash_success": request.query_params.get("success"),
        "flash_error": request.query_params.get("error"),
    })


# ── User management (web forms) ───────────────

@router.post("/admin/users/create")
async def admin_user_create(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    username: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    is_admin: Annotated[str, Form()] = "",
):
    user = await _get_web_user(request, settings, session)
    if not user or not user.is_admin:
        return RedirectResponse("/login", status_code=302)

    existing = (await session.exec(
        select(User).where((User.username == username.strip()) | (User.email == email.strip()))
    )).first()
    if existing:
        return RedirectResponse("/admin/users?error=Username+or+email+already+taken", status_code=302)

    new_user = User(
        username=username.strip(),
        email=email.strip(),
        hashed_password=hash_password(password),
        status=UserStatus.APPROVED,
        status_changed_at=datetime.now(UTC),
        approved_by_id=user.id,
        is_admin=bool(is_admin),
    )
    session.add(new_user)
    await session.commit()
    return RedirectResponse(f"/admin/users?success=User+{username.strip()}+created", status_code=302)


@router.post("/admin/users/{user_id}/delete")
async def admin_user_delete(
    request: Request,
    user_id: int,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    user = await _get_web_user(request, settings, session)
    if not user or not user.is_admin:
        return RedirectResponse("/login", status_code=302)

    if user_id == user.id:
        return RedirectResponse("/admin/users?error=Cannot+delete+yourself", status_code=302)

    target = await session.get(User, user_id)
    if target:
        await session.delete(target)
        await session.commit()
    return RedirectResponse("/admin/users?success=User+deleted", status_code=302)
