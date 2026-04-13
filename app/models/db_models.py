"""SQLAlchemy database models."""
from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Date, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """用户表。"""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="小读者")
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    books_read: Mapped[int] = mapped_column(Integer, default=0)  # 已读绘本数
    books_created: Mapped[int] = mapped_column(Integer, default=0)  # 创作绘本数（排行榜）
    stars: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_read_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # 最后阅读日期
    total_sentences_read: Mapped[int] = mapped_column(Integer, default=0)  # 累计阅读句子数
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    settings: Mapped["UserSettings"] = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    books: Mapped[list["Book"]] = relationship("Book", back_populates="user", cascade="all, delete-orphan")
    reading_progress: Mapped[list["ReadingProgress"]] = relationship("ReadingProgress", back_populates="user", cascade="all, delete-orphan")
    achievements: Mapped[list["UserAchievement"]] = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    daily_tasks: Mapped[list["DailyTask"]] = relationship("DailyTask", back_populates="user", cascade="all, delete-orphan")


class UserSettings(Base):
    """用户设置表。"""
    __tablename__ = "user_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    speed_label: Mapped[str] = mapped_column(String(10), default="中")
    accent: Mapped[str] = mapped_column(String(10), default="US")
    loop_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="settings")


class VerificationCode(Base):
    """验证码表。"""
    __tablename__ = "verification_codes"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(6))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Book(Base):
    """书籍表。"""
    __tablename__ = "books"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer, default=1)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, generating, completed, error
    share_type: Mapped[str] = mapped_column(String(10), default="private")  # public, private
    # 排行榜统计字段
    read_count: Mapped[int] = mapped_column(Integer, default=0)  # 阅读次数
    shelf_count: Mapped[int] = mapped_column(Integer, default=0)  # 被收藏次数
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="books")
    pages: Mapped[list["BookPage"]] = relationship("BookPage", back_populates="book", cascade="all, delete-orphan")
    reading_progress: Mapped[list["ReadingProgress"]] = relationship("ReadingProgress", back_populates="book", cascade="all, delete-orphan")


class BookPage(Base):
    """书籍页面表。"""
    __tablename__ = "book_pages"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    book_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")  # processing, completed, error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    book: Mapped["Book"] = relationship("Book", back_populates="pages")
    sentences: Mapped[list["Sentence"]] = relationship("Sentence", back_populates="page", cascade="all, delete-orphan")


class Sentence(Base):
    """句子表。"""
    __tablename__ = "sentences"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    page_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_pages.id", ondelete="CASCADE"), index=True)
    sentence_order: Mapped[int] = mapped_column(Integer)
    en: Mapped[str] = mapped_column(Text)
    zh: Mapped[str] = mapped_column(Text)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    page: Mapped["BookPage"] = relationship("BookPage", back_populates="sentences")


class ReadingProgress(Base):
    """阅读进度表。"""
    __tablename__ = "reading_progress"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True)
    current_page: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="reading_progress")
    book: Mapped["Book"] = relationship("Book", back_populates="reading_progress")


class Bookshelf(Base):
    """书架表 - 存储用户加入书架的绘本。"""
    __tablename__ = "bookshelf"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_bookshelf_user_book"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemConfig(Base):
    """系统配置表。"""
    __tablename__ = "system_configs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ========================================
# 游戏化系统相关模型
# ========================================


class Achievement(Base):
    """成就/徽章表。"""
    __tablename__ = "achievements"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # 成就代码 (first_book, streak_7 等)
    name: Mapped[str] = mapped_column(String(100))  # 成就名称
    description: Mapped[str] = mapped_column(String(500))  # 成就描述
    icon: Mapped[str] = mapped_column(String(100), default="trophy")  # 图标名称
    requirement_type: Mapped[str] = mapped_column(String(20))  # 要求类型 (books_read, streak, stars, level)
    requirement_value: Mapped[int] = mapped_column(Integer)  # 要求数值
    reward_stars: Mapped[int] = mapped_column(Integer, default=0)  # 完成奖励星星
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user_achievements: Mapped[list["UserAchievement"]] = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """用户成就关联表 - 记录用户已解锁的成就。"""
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    achievement_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("achievements.id", ondelete="CASCADE"))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="achievements")
    achievement: Mapped["Achievement"] = relationship("Achievement", back_populates="user_achievements")


class DailyTask(Base):
    """每日任务表 - 记录用户每日阅读任务进度。"""
    __tablename__ = "daily_tasks"
    __table_args__ = (UniqueConstraint("user_id", "task_date", name="uq_user_daily_task"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_date: Mapped[date] = mapped_column(Date, index=True)  # 任务日期
    read_books: Mapped[int] = mapped_column(Integer, default=0)  # 今日阅读绘本数
    completed: Mapped[bool] = mapped_column(Boolean, default=False)  # 任务是否完成
    reward_claimed: Mapped[bool] = mapped_column(Boolean, default=False)  # 奖励是否领取
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="daily_tasks")


# ========================================
# 等级系统配置（静态数据）
# ========================================

LEVEL_CONFIG = {
    1: {"name": "小读者", "stars_required": 0, "title": "森林探索者", "reward": 0},
    2: {"name": "书虫宝宝", "stars_required": 100, "title": "云朵漫步者", "reward": 20},
    3: {"name": "绘本达人", "stars_required": 300, "title": "星光收集者", "reward": 50},
    4: {"name": "故事精灵", "stars_required": 600, "title": "月亮旅行家", "reward": 100},
    5: {"name": "阅读大师", "stars_required": 1000, "title": "彩虹骑士", "reward": 200},
    6: {"name": "书海冒险家", "stars_required": 2000, "title": "梦境守护者", "reward": 300},
    7: {"name": "绘本作家", "stars_required": 3500, "title": "神秘探险家", "reward": 500},
    8: {"name": "故事魔法师", "stars_required": 5000, "title": "智慧使者", "reward": 800},
    9: {"name": "阅读巨星", "stars_required": 8000, "title": "传奇冒险家", "reward": 1000},
    10: {"name": "绘本之王", "stars_required": 12000, "title": "永恒守护者", "reward": 1500},
}


# 预设成就数据
DEFAULT_ACHIEVEMENTS = [
    {"code": "first_book", "name": "第一本绘本", "description": "完成阅读第一本绘本", "icon": "book-open", "requirement_type": "books_read", "requirement_value": 1, "reward_stars": 50},
    {"code": "book_reader_5", "name": "小小阅读家", "description": "完成阅读5本绘本", "icon": "books", "requirement_type": "books_read", "requirement_value": 5, "reward_stars": 80},
    {"code": "book_reader_10", "name": "阅读达人", "description": "完成阅读10本绘本", "icon": "library", "requirement_type": "books_read", "requirement_value": 10, "reward_stars": 100},
    {"code": "book_reader_30", "name": "绘本大师", "description": "完成阅读30本绘本", "icon": "award", "requirement_type": "books_read", "requirement_value": 30, "reward_stars": 300},
    {"code": "book_reader_50", "name": "阅读巨星", "description": "完成阅读50本绘本", "icon": "star", "requirement_type": "books_read", "requirement_value": 50, "reward_stars": 500},
    {"code": "streak_3", "name": "三日打卡", "description": "连续阅读3天", "icon": "flame", "requirement_type": "streak", "requirement_value": 3, "reward_stars": 30},
    {"code": "streak_7", "name": "一周打卡", "description": "连续阅读7天", "icon": "calendar", "requirement_type": "streak", "requirement_value": 7, "reward_stars": 100},
    {"code": "streak_14", "name": "两周打卡", "description": "连续阅读14天", "icon": "calendar-check", "requirement_type": "streak", "requirement_value": 14, "reward_stars": 200},
    {"code": "streak_30", "name": "月度达人", "description": "连续阅读30天", "icon": "medal", "requirement_type": "streak", "requirement_value": 30, "reward_stars": 500},
    {"code": "streak_100", "name": "百日挑战", "description": "连续阅读100天", "icon": "crown", "requirement_type": "streak", "requirement_value": 100, "reward_stars": 1000},
    {"code": "level_5", "name": "中级冒险家", "description": "达到Lv.5等级", "icon": "rocket", "requirement_type": "level", "requirement_value": 5, "reward_stars": 300},
    {"code": "level_10", "name": "传奇冒险家", "description": "达到Lv.10等级", "icon": "crown", "requirement_type": "level", "requirement_value": 10, "reward_stars": 1000},
]


# 星星奖励规则
STAR_REWARDS = {
    "complete_book": 10,      # 完成绘本阅读
    "daily_first_read": 5,    # 每日首次阅读
    "streak_bonus_multiplier": 2,  # 连续天数奖励倍数
    "read_sentence": 1,       # 每朗读一个句子
    "daily_task_complete": 20,  # 完成每日任务
}