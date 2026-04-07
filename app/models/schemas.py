"""Pydantic models for API request/response schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# User Models
# ============================================

class UserBase(BaseModel):
    """Base user model."""
    name: str = Field(default="小读者", max_length=100)
    avatar: Optional[str] = None


class UserCreate(UserBase):
    """User creation model."""
    phone: Optional[str] = Field(None, max_length=20)


class UserUpdate(BaseModel):
    """User update model."""
    name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = None


class UserResponse(UserBase):
    """User response model."""
    id: UUID
    level: int = 1
    books_read: int = 0
    stars: int = 0
    streak: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    """User statistics response."""
    user_id: UUID
    name: str
    level: int
    stars: int
    streak: int
    books_read: int
    total_books: int
    completed_books: int


# ============================================
# User Settings Models
# ============================================

class UserSettingsBase(BaseModel):
    """Base user settings model."""
    speed_label: str = Field(default="中", max_length=10)
    accent: str = Field(default="US", max_length=10)
    loop_enabled: bool = False


class UserSettingsUpdate(BaseModel):
    """User settings update model."""
    speed_label: Optional[str] = Field(None, max_length=10)
    accent: Optional[str] = Field(None, max_length=10)
    loop_enabled: Optional[bool] = None


class UserSettingsResponse(UserSettingsBase):
    """User settings response model."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Book Models
# ============================================

class BookBase(BaseModel):
    """Base book model."""
    title: str = Field(..., max_length=255, min_length=1)
    level: int = Field(default=1, ge=1, le=10)


class BookCreate(BookBase):
    """Book creation model."""
    cover_image: Optional[str] = None


class BookUpdate(BaseModel):
    """Book update model."""
    title: Optional[str] = Field(None, max_length=255, min_length=1)
    level: Optional[int] = Field(None, ge=1, le=10)
    progress: Optional[int] = Field(None, ge=0, le=100)
    cover_image: Optional[str] = None
    is_new: Optional[bool] = None
    has_audio: Optional[bool] = None
    status: Optional[str] = Field(None, pattern="^(draft|generating|completed|error)$")


class BookResponse(BookBase):
    """Book response model."""
    id: UUID
    user_id: UUID
    progress: int = 0
    cover_image: Optional[str] = None
    is_new: bool = False
    has_audio: bool = False
    status: str = "draft"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookDetailResponse(BookResponse):
    """Book detail response model with pages."""
    pages: list["BookPageResponse"] = []


class BookListResponse(BaseModel):
    """Book list response with pagination."""
    books: list[BookResponse]
    total: int
    page: int
    page_size: int


# ============================================
# Book Page Models
# ============================================

class BookPageBase(BaseModel):
    """Base book page model."""
    page_number: int = Field(..., ge=1)
    image_url: Optional[str] = None


class BookPageCreate(BookPageBase):
    """Book page creation model."""
    image_data: Optional[bytes] = None


class BookPageResponse(BookPageBase):
    """Book page response model."""
    id: UUID
    book_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class BookPageDetailResponse(BookPageResponse):
    """Book page with sentences."""
    sentences: list["SentenceResponse"] = []


# ============================================
# Sentence Models
# ============================================

class SentenceBase(BaseModel):
    """Base sentence model."""
    en: str = Field(default="", min_length=0)
    zh: str = Field(default="", min_length=0)


class SentenceCreate(SentenceBase):
    """Sentence creation model."""
    sentence_order: int = Field(default=1, ge=1)


class SentenceUpdate(BaseModel):
    """Sentence update model."""
    en: Optional[str] = Field(None, min_length=0)
    zh: Optional[str] = Field(None, min_length=0)


class SentenceCreateRequest(BaseModel):
    """Request to create a new sentence."""
    en: str = Field(default="", min_length=0)
    zh: str = Field(default="", min_length=0)


class SentenceReorderRequest(BaseModel):
    """Request to reorder sentences."""
    sentence_ids: list[str] = Field(..., min_length=1)


class SentenceResponse(SentenceBase):
    """Sentence response model."""
    id: UUID
    page_id: UUID
    sentence_order: int
    audio_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Reading Progress Models
# ============================================

class ReadingProgressBase(BaseModel):
    """Base reading progress model."""
    current_page: int = Field(default=0, ge=0)
    total_pages: int = Field(default=0, ge=0)


class ReadingProgressUpdate(BaseModel):
    """Reading progress update model."""
    current_page: Optional[int] = Field(None, ge=0)
    completed: Optional[bool] = None


class ReadingProgressResponse(ReadingProgressBase):
    """Reading progress response model."""
    id: UUID
    user_id: UUID
    book_id: UUID
    completed: bool = False
    last_read_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Authentication Models
# ============================================

class SendCodeRequest(BaseModel):
    """Request to send verification code."""
    phone: str = Field(..., max_length=20, pattern=r"^\+?[1-9]\d{1,14}$")


class VerifyCodeRequest(BaseModel):
    """Request to verify code and login."""
    phone: str = Field(..., max_length=20)
    code: str = Field(..., min_length=4, max_length=6)


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ============================================
# Book Generation Models
# ============================================

class GenerateBookRequest(BaseModel):
    """Request to generate book from images."""
    title: Optional[str] = Field(None, max_length=255)
    images: list[str] = Field(..., min_length=1, max_length=50)
    level: int = Field(default=1, ge=1, le=10)


class GenerateBookResponse(BaseModel):
    """Response for book generation."""
    book_id: UUID
    status: str
    message: str


# ============================================
# Generic Response Models
# ============================================

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str
    error_code: Optional[str] = None


# ============================================
# Admin Models
# ============================================

class AdminLoginRequest(BaseModel):
    """Admin login request."""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AdminTokenResponse(BaseModel):
    """Admin token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminUserResponse(BaseModel):
    """Admin user response (for listing users)."""
    id: UUID
    name: str
    phone: Optional[str] = None
    avatar: Optional[str] = None
    level: int = 1
    books_read: int = 0
    stars: int = 0
    streak: int = 0
    is_active: bool = True
    is_banned: bool = False
    banned_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """Admin user list response with pagination."""
    total: int
    page: int
    page_size: int
    users: list[AdminUserResponse]


class AdminBookListResponse(BaseModel):
    """Admin book list response with pagination."""
    total: int
    page: int
    page_size: int
    books: list[dict]


class SentenceResponse(BaseModel):
    """Sentence response for admin."""
    id: str
    sentence_order: int
    en: str
    zh: str
    audio_url: Optional[str] = None


class BookPageResponse(BaseModel):
    """Book page response for admin."""
    id: str
    page_number: int
    image_url: Optional[str] = None
    sentences: list[SentenceResponse] = []


class AdminBookDetailResponse(BaseModel):
    """Admin book detail response."""
    id: str
    title: str
    user_id: str
    user_name: Optional[str] = None
    status: str
    progress: int
    level: int
    has_audio: bool
    cover_image: Optional[str] = None
    created_at: str
    pages: list[BookPageResponse] = []


class AdminStatsOverviewResponse(BaseModel):
    """Admin stats overview response."""
    total_users: int
    total_books: int
    new_users_today: int
    new_books_today: int
    readings_today: int


class AdminBanRequest(BaseModel):
    """Admin ban user request."""
    reason: str = Field(..., min_length=1, max_length=500)


class SystemConfigResponse(BaseModel):
    """System config response."""
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[str] = None


class SystemConfigUpdate(BaseModel):
    """System config update request."""
    value: str
    description: Optional[str] = None


# Update forward references
BookPageDetailResponse.model_rebuild()
BookDetailResponse.model_rebuild()