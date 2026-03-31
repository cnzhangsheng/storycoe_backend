"""File storage service for managing uploaded images."""
import os
import uuid
from pathlib import Path
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import Book, BookPage


class FileStorageService:
    """文件存储服务。

    目录结构:
    uploads/
    ├── avatars/
    │   └── {user_id}.jpg
    └── books/
        └── {book_id}/
            ├── cover.jpg
            └── pages/
                ├── page_001.jpg
                ├── page_002.jpg
                └── ...
    """

    def __init__(self):
        """初始化文件存储服务。"""
        self.base_dir = Path(settings.upload_dir)
        self.books_dir = self.base_dir / "books"
        self.avatars_dir = self.base_dir / "avatars"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保基础目录存在。"""
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.avatars_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"文件存储目录: {self.base_dir.absolute()}")

    def create_book_dir(self, book_id: str) -> Path:
        """创建书籍目录。

        Args:
            book_id: 书籍 ID

        Returns:
            书籍目录路径
        """
        book_dir = self.books_dir / str(book_id)
        pages_dir = book_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"创建书籍目录: {book_dir}")
        return book_dir

    def save_page_image(
        self,
        book_id: str,
        page_number: int,
        image_data: bytes,
        extension: str = "jpg",
    ) -> str:
        """保存页面图片。

        Args:
            book_id: 书籍 ID
            page_number: 页码
            image_data: 图片字节数据
            extension: 图片扩展名

        Returns:
            图片相对路径
        """
        book_dir = self.books_dir / str(book_id)
        pages_dir = book_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        filename = f"page_{page_number:03d}.{extension}"
        filepath = pages_dir / filename

        with open(filepath, "wb") as f:
            f.write(image_data)

        relative_path = f"books/{book_id}/pages/{filename}"
        logger.debug(f"保存页面图片: {relative_path}")
        return relative_path

    def save_cover_image(
        self,
        book_id: str,
        image_data: bytes,
        extension: str = "jpg",
    ) -> str:
        """保存封面图片。

        Args:
            book_id: 书籍 ID
            image_data: 图片字节数据
            extension: 图片扩展名

        Returns:
            图片相对路径
        """
        book_dir = self.books_dir / str(book_id)
        book_dir.mkdir(parents=True, exist_ok=True)

        filename = f"cover.{extension}"
        filepath = book_dir / filename

        with open(filepath, "wb") as f:
            f.write(image_data)

        relative_path = f"books/{book_id}/{filename}"
        logger.info(f"保存封面图片: {relative_path}")
        return relative_path

    def get_absolute_path(self, relative_path: str) -> Path:
        """获取绝对路径。

        Args:
            relative_path: 相对路径

        Returns:
            绝对路径
        """
        return self.base_dir / relative_path

    def get_page_url(self, book_id: str, page_number: int, extension: str = "jpg") -> str:
        """获取页面图片 URL。

        Args:
            book_id: 书籍 ID
            page_number: 页码
            extension: 图片扩展名

        Returns:
            图片 URL
        """
        return f"/static/books/{book_id}/pages/page_{page_number:03d}.{extension}"

    def delete_book_dir(self, book_id: str) -> bool:
        """删除书籍目录。

        Args:
            book_id: 书籍 ID

        Returns:
            是否成功
        """
        import shutil

        book_dir = self.books_dir / str(book_id)
        if book_dir.exists():
            shutil.rmtree(book_dir)
            logger.info(f"删除书籍目录: {book_dir}")
            return True
        return False

    def save_avatar(
        self,
        user_id: str,
        image_data: bytes,
        extension: str = "jpg",
    ) -> str:
        """保存用户头像。

        Args:
            user_id: 用户 ID
            image_data: 图片字节数据
            extension: 图片扩展名

        Returns:
            头像 URL
        """
        self.avatars_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{user_id}.{extension}"
        filepath = self.avatars_dir / filename

        with open(filepath, "wb") as f:
            f.write(image_data)

        avatar_url = f"/static/avatars/{filename}"
        logger.info(f"保存用户头像: {avatar_url}")
        return avatar_url


# 全局实例
file_storage = FileStorageService()