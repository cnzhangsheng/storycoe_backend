"""Pydantic models for API request/response schemas."""
from datetime import datetime, date
from typing import Optional

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
    id: int
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
    user_id: int
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
    id: int
    user_id: int
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
    share_type: str = Field(default="private", pattern="^(public|private)$")


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
    share_type: Optional[str] = Field(None, pattern="^(public|private)$")


class BookResponse(BookBase):
    """Book response model."""
    id: int
    user_id: int
    progress: int = 0
    cover_image: Optional[str] = None
    is_new: bool = False
    has_audio: bool = False
    status: str = "draft"
    share_type: str = "private"
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


class ShelfListResponse(BaseModel):
    """绘本架分类响应."""
    my_books: list[BookResponse]  # 用户自己的所有绘本
    liked_books: list[BookResponse]  # 喜欢的他人公开绘本
    total_my: int
    total_liked: int


# ============================================
# Book Page Models
# ============================================

class BookPageBase(BaseModel):
    """Base book page model."""
    page_number: int = Field(..., ge=1)
    image_url: Optional[str] = None
    status: str = Field(default="completed", pattern="^(processing|completed|error)$")


class BookPageCreate(BookPageBase):
    """Book page creation model."""
    image_data: Optional[bytes] = None


class BookPageResponse(BookPageBase):
    """Book page response model."""
    id: int
    book_id: int
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
    sentence_ids: list[int] = Field(..., min_length=1)


class SentenceResponse(SentenceBase):
    """Sentence response model."""
    id: int
    page_id: int
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
    id: int
    user_id: int
    book_id: int
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
    cover_image: Optional[str] = Field(None, description="封面图片URL（可选）")
    images: list[str] = Field(..., min_length=1, max_length=50, description="内容图片URL列表")
    level: int = Field(default=1, ge=1, le=10)
    share_type: str = Field(default="private", description="分享类型: public 或 private")


class GenerateBookResponse(BaseModel):
    """Response for book generation."""
    book_id: int
    status: str
    message: str
    total_pages: Optional[int] = None


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
    id: int
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


class AdminSentenceResponse(BaseModel):
    """Sentence response for admin."""
    id: int
    sentence_order: int
    en: str
    zh: str
    audio_url: Optional[str] = None


class AdminBookPageResponse(BaseModel):
    """Book page response for admin."""
    id: int
    page_number: int
    image_url: Optional[str] = None
    sentences: list[AdminSentenceResponse] = []


class AdminBookDetailResponse(BaseModel):
    """Admin book detail response."""
    id: int
    title: str
    user_id: int
    user_name: Optional[str] = None
    status: str
    progress: int
    level: int
    has_audio: bool
    cover_image: Optional[str] = None
    created_at: datetime
    pages: list[AdminBookPageResponse] = []


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


# ============================================
# Gamification Models (游戏化系统)
# ============================================

class AchievementResponse(BaseModel):
    """成就响应模型。"""
    id: int
    code: str
    name: str
    description: str
    icon: str
    requirement_type: str
    requirement_value: int
    reward_stars: int
    unlocked: bool = False  # 是否已解锁
    unlocked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AchievementListResponse(BaseModel):
    """成就列表响应。"""
    achievements: list[AchievementResponse]
    total_unlocked: int
    total: int


class DailyTaskResponse(BaseModel):
    """每日任务响应模型。"""
    id: int
    task_date: date
    read_books: int
    target_books: int = 3  # 目标绘本数
    completed: bool
    reward_claimed: bool
    reward_stars: int = 20  # 完成奖励
    progress_percent: float  # 进度百分比

    class Config:
        from_attributes = True


class DailyTaskClaimResponse(BaseModel):
    """领取每日任务奖励响应。"""
    success: bool
    reward_stars: int
    message: str


class GamificationStatsResponse(BaseModel):
    """游戏化统计响应。"""
    level: int
    level_name: str
    stars: int
    streak: int
    books_read: int
    total_sentences_read: int
    next_level_stars: int  # 下一等级需要星星
    current_level_progress: float  # 当前等级进度百分比
    title: str  # 身份标签


class StarRewardResponse(BaseModel):
    """星星奖励响应 - 用于记录星星获取。"""
    stars_added: int
    reason: str
    total_stars: int
    level_up: bool = False
    new_level: Optional[int] = None
    achievements_unlocked: list[AchievementResponse] = []


class StreakUpdateResponse(BaseModel):
    """连续天数更新响应。"""
    streak: int
    streak_started: bool = False
    streak_continued: bool = False
    streak_reset: bool = False
    stars_added: int  # 连续打卡奖励星星


# ============================================
# Leaderboard Models (排行榜)
# ============================================

class LeaderboardBookResponse(BaseModel):
    """排行榜绘本响应模型。"""
    id: int
    title: str
    cover_image: Optional[str] = None
    level: int
    read_count: int
    shelf_count: int
    author_id: int
    author_name: str
    author_avatar: Optional[str] = None
    rank: int

    class Config:
        from_attributes = True


class LeaderboardAuthorResponse(BaseModel):
    """排行榜作者响应模型。"""
    id: int
    name: str
    avatar: Optional[str] = None
    level: int
    books_created: int  # 创作绘本数
    total_shelf_count: int  # 作品被收藏总数
    rank: int

    class Config:
        from_attributes = True


class LeaderboardBookListResponse(BaseModel):
    """排行榜绘本列表响应。"""
    leaderboard_type: str  # hot / new
    books: list[LeaderboardBookResponse]
    total: int


class LeaderboardAuthorListResponse(BaseModel):
    """排行榜作者列表响应。"""
    authors: list[LeaderboardAuthorResponse]
    total: int