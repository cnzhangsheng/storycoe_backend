"""SQLAlchemy database models."""
from datetime import datetime, date

from sqlalchemy import Boolean, DateTime, Date, Integer, String, Text, BigInteger, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from app.core.database import Base
from app.utils.snowflake import snowflake_id


class User(Base):
    """用户表。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    wechat_open_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="小读者")
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    books_read: Mapped[int] = mapped_column(Integer, default=0)
    books_created: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_read_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_sentences_read: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系（无数据库外键约束，使用 foreign() 显式指定逻辑关联）
    settings: Mapped["UserSettings"] = relationship(
        "UserSettings", back_populates="user", uselist=False,
        primaryjoin="User.id == foreign(UserSettings.user_id)"
    )
    books: Mapped[list["Book"]] = relationship(
        "Book", back_populates="user",
        primaryjoin="User.id == foreign(Book.user_id)"
    )
    reading_progress: Mapped[list["ReadingProgress"]] = relationship(
        "ReadingProgress", back_populates="user",
        primaryjoin="User.id == foreign(ReadingProgress.user_id)"
    )
    achievements: Mapped[list["UserAchievement"]] = relationship(
        "UserAchievement", back_populates="user",
        primaryjoin="User.id == foreign(UserAchievement.user_id)"
    )
    daily_tasks: Mapped[list["DailyTask"]] = relationship(
        "DailyTask", back_populates="user",
        primaryjoin="User.id == foreign(DailyTask.user_id)"
    )


class UserSettings(Base):
    """用户设置表。"""
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    speed_label: Mapped[str] = mapped_column(String(10), default="中")
    accent: Mapped[str] = mapped_column(String(10), default="US")
    loop_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship(
        "User", back_populates="settings",
        primaryjoin="foreign(UserSettings.user_id) == User.id"
    )


class VerificationCode(Base):
    """验证码表。"""
    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(6))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Book(Base):
    """书籍表。"""
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer, default=1)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    share_type: Mapped[str] = mapped_column(String(10), default="private")
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    shelf_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship(
        "User", back_populates="books",
        primaryjoin="foreign(Book.user_id) == User.id"
    )
    pages: Mapped[list["BookPage"]] = relationship(
        "BookPage", back_populates="book",
        primaryjoin="Book.id == foreign(BookPage.book_id)"
    )
    reading_progress: Mapped[list["ReadingProgress"]] = relationship(
        "ReadingProgress", back_populates="book",
        primaryjoin="Book.id == foreign(ReadingProgress.book_id)"
    )


class BookPage(Base):
    """书籍页面表。"""
    __tablename__ = "book_pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    book_id: Mapped[int] = mapped_column(BigInteger, index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    book: Mapped["Book"] = relationship(
        "Book", back_populates="pages",
        primaryjoin="foreign(BookPage.book_id) == Book.id"
    )
    sentences: Mapped[list["Sentence"]] = relationship(
        "Sentence", back_populates="page",
        primaryjoin="BookPage.id == foreign(Sentence.page_id)"
    )


class Sentence(Base):
    """句子表。"""
    __tablename__ = "sentences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    page_id: Mapped[int] = mapped_column(BigInteger, index=True)
    sentence_order: Mapped[int] = mapped_column(Integer)
    en: Mapped[str] = mapped_column(Text)
    zh: Mapped[str] = mapped_column(Text)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    page: Mapped["BookPage"] = relationship(
        "BookPage", back_populates="sentences",
        primaryjoin="foreign(Sentence.page_id) == BookPage.id"
    )


class ReadingProgress(Base):
    """阅读进度表。"""
    __tablename__ = "reading_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    book_id: Mapped[int] = mapped_column(BigInteger, index=True)
    current_page: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship(
        "User", back_populates="reading_progress",
        primaryjoin="foreign(ReadingProgress.user_id) == User.id"
    )
    book: Mapped["Book"] = relationship(
        "Book", back_populates="reading_progress",
        primaryjoin="foreign(ReadingProgress.book_id) == Book.id"
    )


class Bookshelf(Base):
    """书架表。"""
    __tablename__ = "bookshelf"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_bookshelf_user_book"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    book_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemConfig(Base):
    """系统配置表。"""
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Achievement(Base):
    """成就表。"""
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    icon: Mapped[str] = mapped_column(String(100), default="trophy")
    requirement_type: Mapped[str] = mapped_column(String(20))
    requirement_value: Mapped[int] = mapped_column(Integer)
    reward_stars: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user_achievements: Mapped[list["UserAchievement"]] = relationship(
        "UserAchievement", back_populates="achievement",
        primaryjoin="Achievement.id == foreign(UserAchievement.achievement_id)"
    )


class UserAchievement(Base):
    """用户成就关联表。"""
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    achievement_id: Mapped[int] = mapped_column(BigInteger, index=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user: Mapped["User"] = relationship(
        "User", back_populates="achievements",
        primaryjoin="foreign(UserAchievement.user_id) == User.id"
    )
    achievement: Mapped["Achievement"] = relationship(
        "Achievement", back_populates="user_achievements",
        primaryjoin="foreign(UserAchievement.achievement_id) == Achievement.id"
    )


class DailyTask(Base):
    """每日任务表。"""
    __tablename__ = "daily_tasks"
    __table_args__ = (UniqueConstraint("user_id", "task_date", name="uq_user_daily_task"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowflake_id)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    task_date: Mapped[date] = mapped_column(Date, index=True)
    read_books: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship(
        "User", back_populates="daily_tasks",
        primaryjoin="foreign(DailyTask.user_id) == User.id"
    )


# 等级系统配置
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
    "complete_book": 10,
    "daily_first_read": 5,
    "streak_bonus_multiplier": 2,
    "read_sentence": 1,
    "daily_task_complete": 20,
}