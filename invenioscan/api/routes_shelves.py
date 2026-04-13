from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from invenioscan.database import get_session
from invenioscan.dependencies import get_current_user, require_admin
from invenioscan.models import BookCopy, Shelf, User
from invenioscan.schemas import ShelfCreate, ShelfPublic, ShelfUpdate

router = APIRouter(prefix="/shelves", tags=["shelves"])


@router.get("", response_model=list[ShelfPublic])
async def list_shelves(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Shelf]:
    result = await session.exec(select(Shelf).order_by(Shelf.shelf_id, Shelf.row, Shelf.position, Shelf.height))
    return list(result.all())


@router.get("/{shelf_db_id}", response_model=ShelfPublic)
async def get_shelf(
    shelf_db_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Shelf:
    shelf = await session.get(Shelf, shelf_db_id)
    if not shelf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shelf not found")
    return shelf


@router.post("", response_model=ShelfPublic, status_code=status.HTTP_201_CREATED)
async def create_shelf(
    payload: ShelfCreate,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Shelf:
    existing_shelf_id = await session.exec(select(Shelf).where(Shelf.shelf_id == payload.shelf_id))
    if existing_shelf_id.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shelf ID already exists")

    existing_coordinates = await session.exec(
        select(Shelf).where(
            Shelf.row == payload.row,
            Shelf.position == payload.position,
            Shelf.height == payload.height,
        )
    )
    if existing_coordinates.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shelf coordinates already exist")

    shelf = Shelf(**payload.model_dump())
    session.add(shelf)
    await session.commit()
    await session.refresh(shelf)
    return shelf


@router.put("/{shelf_db_id}", response_model=ShelfPublic)
async def update_shelf(
    shelf_db_id: int,
    payload: ShelfUpdate,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Shelf:
    shelf = await session.get(Shelf, shelf_db_id)
    if not shelf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shelf not found")

    new_row = payload.row if payload.row is not None else shelf.row
    new_position = payload.position if payload.position is not None else shelf.position
    new_height = payload.height if payload.height is not None else shelf.height

    existing_coordinates = await session.exec(
        select(Shelf).where(
            Shelf.id != shelf_db_id,
            Shelf.row == new_row,
            Shelf.position == new_position,
            Shelf.height == new_height,
        )
    )
    if existing_coordinates.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shelf coordinates already exist")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(shelf, key, value)
    shelf.updated_at = datetime.now(UTC)
    session.add(shelf)
    await session.commit()
    await session.refresh(shelf)
    return shelf


@router.delete("/{shelf_db_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shelf(
    shelf_db_id: int,
    _admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    shelf = await session.get(Shelf, shelf_db_id)
    if not shelf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shelf not found")
    copies = await session.exec(select(BookCopy).where(BookCopy.shelf_id == shelf_db_id))
    if copies.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete shelf with book copies. Remove copies first.",
        )
    await session.delete(shelf)
    await session.commit()
