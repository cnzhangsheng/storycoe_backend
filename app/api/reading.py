"""API routes for reading progress."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.models.schemas import (
    ReadingProgressUpdate,
    ReadingProgressResponse,
    MessageResponse,
)
from app.services import get_reading_service
from app.services.reading_service import ReadingService

router = APIRouter(prefix="/reading", tags=["Reading Progress"])


@router.get("/{book_id}", response_model=ReadingProgressResponse)
async def get_reading_progress(
    book_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    reading_service: Annotated[ReadingService, Depends(get_reading_service)],
):
    """Get reading progress for a book."""
    return reading_service.get_reading_progress(current_user["id"], book_id)


@router.put("/{book_id}", response_model=ReadingProgressResponse)
async def update_reading_progress(
    book_id: int,
    update_data: ReadingProgressUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    reading_service: Annotated[ReadingService, Depends(get_reading_service)],
):
    """Update reading progress for a book."""
    return reading_service.update_reading_progress(
        user_id=current_user["id"],
        book_id=book_id,
        update_data=update_data,
        current_books_read=current_user["books_read"],
    )


@router.post("/{book_id}/complete", response_model=MessageResponse)
async def mark_book_completed(
    book_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    reading_service: Annotated[ReadingService, Depends(get_reading_service)],
):
    """Mark a book as completed."""
    return reading_service.mark_book_completed(
        user_id=current_user["id"],
        book_id=book_id,
        current_books_read=current_user["books_read"],
    )