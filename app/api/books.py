"""API routes for books."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.models.schemas import (
    BookCreate,
    BookUpdate,
    BookResponse,
    BookDetailResponse,
    BookListResponse,
    BookPageDetailResponse,
    GenerateBookRequest,
    GenerateBookResponse,
    MessageResponse,
    SentenceUpdate,
    SentenceResponse,
    SentenceCreateRequest,
    SentenceReorderRequest,
)
from app.services import get_book_service
from app.services.book_service import BookService

router = APIRouter(prefix="/books", tags=["Books"])


@router.get("", response_model=BookListResponse)
async def list_books(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
    book_service: Annotated[BookService, Depends(get_book_service)] = None,
):
    """List user's books with pagination."""
    return book_service.list_books(
        user_id=current_user["id"],
        page=page,
        page_size=page_size,
        status=status,
    )


@router.post("", response_model=BookResponse)
async def create_book(
    book_data: BookCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Create a new book."""
    book = book_service.create_book(current_user["id"], book_data)
    return BookResponse(**book)


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Get a specific book by ID with pages."""
    book = book_service.get_book(book_id, current_user["id"])
    return BookDetailResponse(**book)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: str,
    book_data: BookUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Update a book."""
    book = book_service.update_book(book_id, current_user["id"], book_data)
    return BookResponse(**book)


@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Delete a book and all its pages."""
    book_service.delete_book(book_id, current_user["id"])
    return MessageResponse(message="书籍已删除", success=True)


@router.get("/{book_id}/pages/{page_number}", response_model=BookPageDetailResponse)
async def get_book_page(
    book_id: str,
    page_number: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Get a specific page of a book with sentences."""
    page = book_service.get_book_page(book_id, current_user["id"], page_number)
    return BookPageDetailResponse(**page)


@router.post("/{book_id}/pages/{page_number}/sentences", response_model=SentenceResponse)
async def create_sentence(
    book_id: str,
    page_number: int,
    sentence_data: SentenceCreateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Create a new sentence in a book page."""
    sentence = book_service.create_sentence(book_id, current_user["id"], page_number, sentence_data)
    return SentenceResponse(**sentence)


@router.put("/{book_id}/sentences/{sentence_id}", response_model=SentenceResponse)
async def update_sentence(
    book_id: str,
    sentence_id: str,
    sentence_data: SentenceUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Update a sentence in a book."""
    sentence = book_service.update_sentence(book_id, current_user["id"], sentence_id, sentence_data)
    return SentenceResponse(**sentence)


@router.put("/{book_id}/pages/{page_number}/sentences/reorder")
async def reorder_sentences(
    book_id: str,
    page_number: int,
    request: SentenceReorderRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Reorder sentences in a book page."""
    book_service.reorder_sentences(book_id, current_user["id"], page_number, request.sentence_ids)
    return MessageResponse(message="句子排序已更新", success=True)


@router.post("/generate", response_model=GenerateBookResponse)
async def generate_book(
    request: GenerateBookRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Generate a book from images (async task)."""
    return book_service.generate_book(current_user["id"], request)