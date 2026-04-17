"""User service using SQLAlchemy."""
from typing import Optional

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.schemas import (
    UserResponse,
    UserUpdate,
    UserSettingsResponse,
    UserSettingsUpdate,
    UserStatsResponse,
)
from app.models.db_models import User, UserSettings, Book, ReadingProgress


class UserService:
    """用户服务类。

    封装所有用户相关的业务逻辑和数据库操作。
    """

    def __init__(self, db: Session):
        """初始化服务。

        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db

    def get_user(self, user_id: int) -> dict:
        """获取用户信息。

        Args:
            user_id: 用户 ID（整数）

        Returns:
            用户数据字典

        Raises:
            NotFoundException: 用户不存在
        """
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            logger.warning(f"用户不存在: user_id={user_id}")
            raise NotFoundException(message="用户未找到")

        return {
            "id": user.id,
            "name": user.name,
            "avatar": user.avatar,
            "phone": user.phone,
            "level": user.level,
            "books_read": user.books_read,
            "stars": user.stars,
            "streak": user.streak,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def update_user(self, user_id: int, update_data: UserUpdate) -> dict:
        """更新用户信息。

        Args:
            user_id: 用户 ID（整数）
            update_data: 更新数据

        Returns:
            更新后的用户数据
        """
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise NotFoundException(message="用户未找到")

        update_dict = update_data.model_dump(exclude_unset=True)

        if not update_dict:
            logger.debug(f"无更新数据: user_id={user_id}")
            return self.get_user(user_id)

        for key, value in update_dict.items():
            setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        logger.info(f"更新用户信息: user_id={user_id}, fields={list(update_dict.keys())}")

        return self.get_user(user_id)

    def get_user_settings(self, user_id: int) -> dict:
        """获取用户设置。

        Args:
            user_id: 用户 ID（整数）

        Returns:
            用户设置数据字典

        Raises:
            NotFoundException: 设置不存在
        """
        settings = self.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

        if not settings:
            logger.warning(f"用户设置不存在: user_id={user_id}")
            raise NotFoundException(message="用户设置未找到")

        return {
            "id": settings.id,
            "user_id": settings.user_id,
            "speed_label": settings.speed_label,
            "accent": settings.accent,
            "loop_enabled": settings.loop_enabled,
            "created_at": settings.created_at,
            "updated_at": settings.updated_at,
        }

    def update_user_settings(self, user_id: int, update_data: UserSettingsUpdate) -> dict:
        """更新用户设置。

        Args:
            user_id: 用户 ID（整数）
            update_data: 更新数据

        Returns:
            更新后的用户设置
        """
        settings = self.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

        if not settings:
            raise NotFoundException(message="用户设置未找到")

        update_dict = update_data.model_dump(exclude_unset=True)

        if not update_dict:
            logger.debug(f"无更新数据: user_id={user_id}")
            return self.get_user_settings(user_id)

        for key, value in update_dict.items():
            setattr(settings, key, value)

        self.db.commit()
        self.db.refresh(settings)
        logger.info(f"更新用户设置: user_id={user_id}, fields={list(update_dict.keys())}")

        return self.get_user_settings(user_id)

    def get_user_stats(self, user_id: int) -> UserStatsResponse:
        """获取用户统计数据。

        Args:
            user_id: 用户 ID（整数）

        Returns:
            用户统计数据
        """
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise NotFoundException(message="用户未找到")

        # 获取书籍总数
        total_books = self.db.query(func.count(Book.id)).filter(Book.user_id == user_id).scalar() or 0

        # 获取已完成书籍数
        completed_books = self.db.query(func.count(ReadingProgress.id)).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.completed == True,
        ).scalar() or 0

        logger.debug(f"获取用户统计: user_id={user_id}, total_books={total_books}, completed={completed_books}")

        return UserStatsResponse(
            user_id=user.id,
            name=user.name,
            level=user.level,
            stars=user.stars,
            streak=user.streak,
            books_read=user.books_read,
            total_books=total_books,
            completed_books=completed_books,
        )