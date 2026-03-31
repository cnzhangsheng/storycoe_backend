"""Book service using SQLAlchemy."""
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundException
from app.models.schemas import (
    BookCreate,
    BookUpdate,
    BookResponse,
    BookListResponse,
    BookPageDetailResponse,
    GenerateBookRequest,
    GenerateBookResponse,
    SentenceUpdate,
    SentenceCreateRequest,
)
from app.models.db_models import Book, BookPage, Sentence


class BookService:
    """书籍服务类。

    封装所有书籍相关的业务逻辑和数据库操作。
    """

    def __init__(self, db: Session):
        """初始化服务。

        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db

    def list_books(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> BookListResponse:
        """获取用户书籍列表。

        Args:
            user_id: 用户 ID
            page: 页码
            page_size: 每页数量
            status: 状态筛选

        Returns:
            书籍列表响应
        """
        query = self.db.query(Book).filter(Book.user_id == user_id)

        if status:
            query = query.filter(Book.status == status)

        # 获取总数
        total = query.count()

        # 分页查询
        books = query.order_by(Book.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        logger.debug(f"获取书籍列表: user_id={user_id}, page={page}, total={total}")

        return BookListResponse(
            books=[
                BookResponse(
                    id=book.id,
                    user_id=book.user_id,
                    title=book.title,
                    level=book.level,
                    progress=book.progress,
                    cover_image=book.cover_image,
                    is_new=book.is_new,
                    has_audio=book.has_audio,
                    status=book.status,
                    created_at=book.created_at,
                    updated_at=book.updated_at,
                )
                for book in books
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    def create_book(self, user_id: str, book_data: BookCreate) -> dict:
        """创建书籍。

        Args:
            user_id: 用户 ID
            book_data: 书籍创建数据

        Returns:
            创建的书籍数据
        """
        book = Book(
            user_id=user_id,
            title=book_data.title,
            level=book_data.level,
            cover_image=book_data.cover_image,
            is_new=True,
            status="draft",
        )
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)

        logger.info(f"创建书籍: book_id={book.id}, user_id={user_id}, title={book_data.title}")

        return {
            "id": str(book.id),
            "user_id": str(book.user_id),
            "title": book.title,
            "level": book.level,
            "progress": book.progress,
            "cover_image": book.cover_image,
            "is_new": book.is_new,
            "has_audio": book.has_audio,
            "status": book.status,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
        }

    def get_book(self, book_id: str, user_id: str) -> dict:
        """获取书籍详情（包含页面列表）。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID（用于权限校验）

        Returns:
            书籍数据字典（包含 pages 列表）

        Raises:
            NotFoundException: 书籍不存在或不属于该用户
        """
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 获取书籍的所有页面
        pages = self.db.query(BookPage).filter(BookPage.book_id == book_id).order_by(BookPage.page_number).all()

        # 构建页面列表（不包含句子，句子通过单独API获取）
        pages_data = []
        for page in pages:
            pages_data.append({
                "id": str(page.id),
                "book_id": str(page.book_id),
                "page_number": page.page_number,
                "image_url": page.image_url,
                "created_at": page.created_at,
                "sentences": [],  # 句子通过 get_book_page 获取
            })

        return {
            "id": str(book.id),
            "user_id": str(book.user_id),
            "title": book.title,
            "level": book.level,
            "progress": book.progress,
            "cover_image": book.cover_image,
            "is_new": book.is_new,
            "has_audio": book.has_audio,
            "status": book.status,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
            "pages": pages_data,
        }

    def update_book(self, book_id: str, user_id: str, book_data: BookUpdate) -> dict:
        """更新书籍。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID
            book_data: 更新数据

        Returns:
            更新后的书籍数据

        Raises:
            NotFoundException: 书籍不存在
        """
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        update_dict = book_data.model_dump(exclude_unset=True)

        if not update_dict:
            logger.debug(f"无更新数据: book_id={book_id}")
            return self.get_book(book_id, user_id)

        for key, value in update_dict.items():
            setattr(book, key, value)

        self.db.commit()
        self.db.refresh(book)
        logger.info(f"更新书籍: book_id={book_id}, fields={list(update_dict.keys())}")

        return self.get_book(book_id, user_id)

    def delete_book(self, book_id: str, user_id: str) -> None:
        """删除书籍。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID

        Raises:
            NotFoundException: 书籍不存在
        """
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        self.db.delete(book)
        self.db.commit()
        logger.info(f"删除书籍: book_id={book_id}, user_id={user_id}")

    def get_book_page(self, book_id: str, user_id: str, page_number: int) -> dict:
        """获取书籍页面详情。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID
            page_number: 页码

        Returns:
            页面数据（包含句子列表）

        Raises:
            NotFoundException: 书籍或页面不存在
        """
        # 校验书籍权限
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        # 获取页面
        page = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number == page_number,
        ).first()

        if not page:
            logger.warning(f"页面不存在: book_id={book_id}, page_number={page_number}")
            raise NotFoundException(message="页面未找到")

        # 获取页面句子
        sentences = self.db.query(Sentence).filter(Sentence.page_id == page.id).order_by(Sentence.sentence_order).all()

        logger.debug(f"获取页面: book_id={book_id}, page={page_number}, sentences={len(sentences)}")

        return {
            "id": str(page.id),
            "book_id": str(page.book_id),
            "page_number": page.page_number,
            "image_url": page.image_url,
            "created_at": page.created_at,
            "sentences": [
                {
                    "id": str(s.id),
                    "page_id": str(s.page_id),
                    "sentence_order": s.sentence_order,
                    "en": s.en,
                    "zh": s.zh,
                    "audio_url": s.audio_url,
                    "created_at": s.created_at,
                }
                for s in sentences
            ],
        }

    def generate_book(self, user_id: str, request: GenerateBookRequest) -> GenerateBookResponse:
        """生成书籍（异步任务）。

        Args:
            user_id: 用户 ID
            request: 生成请求

        Returns:
            生成响应
        """
        title = request.title or "我的绘本"

        book = Book(
            user_id=user_id,
            title=title,
            level=request.level,
            status="generating",
            is_new=True,
        )
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)

        logger.info(f"创建生成任务: book_id={book.id}, user_id={user_id}, images={len(request.images)}")

        # TODO: 触发异步生成任务

        return GenerateBookResponse(
            book_id=book.id,
            status="generating",
            message="书籍生成已开始",
        )

    def update_sentence(self, book_id: str, user_id: str, sentence_id: str, sentence_data: SentenceUpdate) -> dict:
        """更新句子。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID
            sentence_id: 句子 ID
            sentence_data: 更新数据

        Returns:
            更新后的句子数据

        Raises:
            NotFoundException: 书籍或句子不存在
        """
        # 校验书籍权限
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 查找句子
        sentence = self.db.query(Sentence).filter(Sentence.id == sentence_id).first()

        if not sentence:
            raise NotFoundException(message="句子未找到")

        # 校验句子所属页面是否属于该书籍
        page = self.db.query(BookPage).filter(BookPage.id == sentence.page_id).first()
        if not page or str(page.book_id) != str(book_id):
            logger.warning(f"句子不属于该书籍: sentence_id={sentence_id}, page_book_id={page.book_id if page else None}, request_book_id={book_id}")
            raise NotFoundException(message="句子不属于该书籍")

        # 更新句子
        update_dict = sentence_data.model_dump(exclude_unset=True)

        if update_dict:
            for key, value in update_dict.items():
                setattr(sentence, key, value)
            self.db.commit()
            self.db.refresh(sentence)
            logger.info(f"更新句子: sentence_id={sentence_id}, fields={list(update_dict.keys())}")

        return {
            "id": str(sentence.id),
            "page_id": str(sentence.page_id),
            "sentence_order": sentence.sentence_order,
            "en": sentence.en,
            "zh": sentence.zh,
            "audio_url": sentence.audio_url,
            "created_at": sentence.created_at,
        }

    def create_sentence(self, book_id: str, user_id: str, page_number: int, sentence_data: SentenceCreateRequest) -> dict:
        """创建句子。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID
            page_number: 页码
            sentence_data: 句子创建数据

        Returns:
            创建的句子数据

        Raises:
            NotFoundException: 书籍或页面不存在
        """
        # 校验书籍权限
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 获取页面
        page = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number == page_number,
        ).first()

        if not page:
            logger.warning(f"页面不存在: book_id={book_id}, page_number={page_number}")
            raise NotFoundException(message="页面未找到")

        # 获取当前页面最大句子序号
        max_order = self.db.query(Sentence).filter(
            Sentence.page_id == page.id
        ).count()

        # 创建新句子（序号为当前最大+1）
        new_order = max_order + 1
        sentence = Sentence(
            page_id=page.id,
            sentence_order=new_order,
            en=sentence_data.en,
            zh=sentence_data.zh,
        )
        self.db.add(sentence)
        self.db.commit()
        self.db.refresh(sentence)

        logger.info(f"创建句子: sentence_id={sentence.id}, page_id={page.id}, order={new_order}")

        return {
            "id": str(sentence.id),
            "page_id": str(sentence.page_id),
            "sentence_order": sentence.sentence_order,
            "en": sentence.en,
            "zh": sentence.zh,
            "audio_url": sentence.audio_url,
            "created_at": sentence.created_at,
        }

    def reorder_sentences(self, book_id: str, user_id: str, page_number: int, sentence_ids: list[str]) -> None:
        """重新排序句子。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID
            page_number: 页码
            sentence_ids: 新顺序的句子 ID 列表

        Raises:
            NotFoundException: 书籍或页面不存在
        """
        # 校验书籍权限
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 获取页面
        page = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number == page_number,
        ).first()

        if not page:
            logger.warning(f"页面不存在: book_id={book_id}, page_number={page_number}")
            raise NotFoundException(message="页面未找到")

        # 更新句子排序
        for index, sentence_id in enumerate(sentence_ids):
            sentence = self.db.query(Sentence).filter(
                Sentence.id == sentence_id,
                Sentence.page_id == page.id,
            ).first()

            if sentence:
                sentence.sentence_order = index + 1

        self.db.commit()
        logger.info(f"句子排序已更新: book_id={book_id}, page={page_number}, order={sentence_ids}")