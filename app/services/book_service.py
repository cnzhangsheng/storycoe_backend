"""Book service using SQLAlchemy."""
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.schemas import (
    BookCreate,
    BookUpdate,
    BookResponse,
    BookListResponse,
    ShelfListResponse,
    GenerateBookRequest,
    GenerateBookResponse,
    SentenceUpdate,
    SentenceCreateRequest,
)
from app.models.db_models import Book, BookPage, Sentence, Bookshelf, ReadingProgress, User
from app.services.translation_service import translation_service


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
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> ShelfListResponse:
        """获取绘本架分类列表。

        Args:
            user_id: 用户 ID
            page: 页码（暂未使用）
            page_size: 每页数量（暂未使用）

        Returns:
            分类书籍响应（我的绘本架 + 喜欢的绘本）
        """
        # 1. 我的绘本架：查询用户创作的所有绘本（不区分状态）
        my_books = self.db.query(Book).filter(Book.user_id == user_id).order_by(Book.created_at.desc()).all()
        total_my = len(my_books)

        # 2. 喜欢的绘本：查询用户收藏的绘本（书架中其他人的公开书籍）
        liked_books = (
            self.db.query(Book)
            .join(Bookshelf, Book.id == Bookshelf.book_id)
            .filter(
                Bookshelf.user_id == user_id,
                Book.user_id != user_id,
                Book.share_type == "public",
            )
            .order_by(Bookshelf.created_at.desc())
            .all()
        )
        total_liked = len(liked_books)

        logger.debug(f"获取绘本架: user_id={user_id}, my_books={total_my}, liked_books={total_liked}")

        def to_book_response(book: Book) -> BookResponse:
            return BookResponse(
                id=book.id,
                user_id=book.user_id,
                title=book.title,
                level=book.level,
                progress=book.progress,
                cover_image=book.cover_image,
                is_new=book.is_new,
                has_audio=book.has_audio,
                status=book.status,
                share_type=book.share_type,
                created_at=book.created_at,
                updated_at=book.updated_at,
            )

        return ShelfListResponse(
            my_books=[to_book_response(book) for book in my_books],
            liked_books=[to_book_response(book) for book in liked_books],
            total_my=total_my,
            total_liked=total_liked,
        )

    def list_public_books(
        self,
        page: int = 1,
        page_size: int = 20,
        level: Optional[int] = None,
    ) -> BookListResponse:
        """获取公开绘本列表。"""
        query = self.db.query(Book).filter(
            Book.share_type == "public",
            Book.status == "completed",
        )

        if level:
            query = query.filter(Book.level == level)

        total = query.count()
        books = query.order_by(Book.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        logger.debug(f"获取公开绘本列表: page={page}, total={total}, level={level}")

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
                    share_type=book.share_type,
                    created_at=book.created_at,
                    updated_at=book.updated_at,
                )
                for book in books
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    def create_book(self, user_id: int, book_data: BookCreate) -> dict:
        """创建书籍。"""
        book = Book(
            user_id=user_id,
            title=book_data.title,
            level=book_data.level,
            cover_image=book_data.cover_image,
            share_type=book_data.share_type,
            is_new=True,
            status="draft",
        )
        self.db.add(book)

        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.books_created += 1

        self.db.commit()
        self.db.refresh(book)

        logger.info(f"创建书籍: book_id={book.id}, user_id={user_id}, title={book_data.title}")

        return {
            "id": book.id,
            "user_id": book.user_id,
            "title": book.title,
            "level": book.level,
            "progress": book.progress,
            "cover_image": book.cover_image,
            "is_new": book.is_new,
            "has_audio": book.has_audio,
            "status": book.status,
            "share_type": book.share_type,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
        }

    def get_book(self, book_id: int, user_id: int) -> dict:
        """获取书籍详情（包含页面列表）。"""
        book = self.db.query(Book).filter(Book.id == book_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        # 权限检查
        if book.user_id != user_id and book.share_type != "public":
            raise NotFoundException(message="书籍未找到")

        pages = self.db.query(BookPage).filter(BookPage.book_id == book_id).order_by(BookPage.page_number).all()

        pages_data = []
        for page in pages:
            sentences = self.db.query(Sentence).filter(Sentence.page_id == page.id).order_by(Sentence.sentence_order).all()
            pages_data.append({
                "id": page.id,
                "book_id": page.book_id,
                "page_number": page.page_number,
                "image_url": page.image_url,
                "status": page.status,
                "created_at": page.created_at,
                "sentences": [
                    {
                        "id": s.id,
                        "page_id": s.page_id,
                        "sentence_order": s.sentence_order,
                        "en": s.en,
                        "zh": s.zh,
                        "audio_url": s.audio_url,
                        "created_at": s.created_at,
                    }
                    for s in sentences
                ],
            })

        return {
            "id": book.id,
            "user_id": book.user_id,
            "title": book.title,
            "level": book.level,
            "progress": book.progress,
            "cover_image": book.cover_image,
            "is_new": book.is_new,
            "has_audio": book.has_audio,
            "status": book.status,
            "share_type": book.share_type,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
            "pages": pages_data,
        }

    def update_book(self, book_id: int, user_id: int, book_data: BookUpdate) -> dict:
        """更新书籍。"""
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        update_dict = book_data.model_dump(exclude_unset=True)
        if not update_dict:
            return self.get_book(book_id, user_id)

        for key, value in update_dict.items():
            setattr(book, key, value)

        self.db.commit()
        self.db.refresh(book)
        logger.info(f"更新书籍: book_id={book_id}, fields={list(update_dict.keys())}")

        return self.get_book(book_id, user_id)

    def delete_book(self, book_id: int, user_id: int) -> None:
        """删除书籍及其所有关联数据。"""
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        # 删除书架关联
        self.db.query(Bookshelf).filter(Bookshelf.book_id == book_id).delete()

        # 删除阅读进度
        self.db.query(ReadingProgress).filter(ReadingProgress.book_id == book_id).delete()

        # 获取页面 ID 并删除句子
        page_ids = [p.id for p in self.db.query(BookPage.id).filter(BookPage.book_id == book_id).all()]
        if page_ids:
            self.db.query(Sentence).filter(Sentence.page_id.in_(page_ids)).delete(synchronize_session=False)

        # 删除页面
        self.db.query(BookPage).filter(BookPage.book_id == book_id).delete()

        # 删除书籍
        self.db.delete(book)

        # 更新用户创作数
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.books_created > 0:
            user.books_created -= 1

        self.db.commit()
        logger.info(f"删除书籍完成: book_id={book_id}, user_id={user_id}")

    def get_book_page(self, book_id: int, user_id: int, page_number: int) -> dict:
        """获取书籍页面详情。"""
        book = self.db.query(Book).filter(Book.id == book_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        if book.user_id != user_id and book.share_type != "public":
            raise NotFoundException(message="书籍未找到")

        page = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number == page_number,
        ).first()

        if not page:
            raise NotFoundException(message="页面未找到")

        sentences = self.db.query(Sentence).filter(Sentence.page_id == page.id).order_by(Sentence.sentence_order).all()

        return {
            "id": page.id,
            "book_id": page.book_id,
            "page_number": page.page_number,
            "image_url": page.image_url,
            "status": page.status,
            "created_at": page.created_at,
            "sentences": [
                {
                    "id": s.id,
                    "page_id": s.page_id,
                    "sentence_order": s.sentence_order,
                    "en": s.en,
                    "zh": s.zh,
                    "audio_url": s.audio_url,
                    "created_at": s.created_at,
                }
                for s in sentences
            ],
        }

    def generate_book(self, user_id: int, request: GenerateBookRequest) -> GenerateBookResponse:
        """生成书籍（从已上传的图片URL）。"""
        title = request.title or "我的绘本"

        book = Book(
            user_id=user_id,
            title=title,
            level=request.level,
            status="generating",
            is_new=True,
            share_type=request.share_type,
            cover_image=request.cover_image,
        )
        self.db.add(book)
        self.db.flush()

        for i, image_url in enumerate(request.images):
            page = BookPage(
                book_id=book.id,
                page_number=i + 1,
                image_url=image_url,
                status="pending",
            )
            self.db.add(page)

        self.db.commit()
        self.db.refresh(book)

        logger.info(f"创建生成任务: book_id={book.id}, user_id={user_id}, pages={len(request.images)}")

        return GenerateBookResponse(
            book_id=book.id,
            status="generating",
            message="绘本创建成功，正在后台处理文字识别",
            total_pages=len(request.images),
        )

    async def update_sentence(self, book_id: int, user_id: int, sentence_id: int, sentence_data: SentenceUpdate) -> dict:
        """更新句子。"""
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        sentence = self.db.query(Sentence).filter(Sentence.id == sentence_id).first()

        if not sentence:
            raise NotFoundException(message="句子未找到")

        page = self.db.query(BookPage).filter(BookPage.id == sentence.page_id).first()
        if not page or page.book_id != book_id:
            raise NotFoundException(message="句子不属于该书籍")

        new_en = sentence_data.en
        old_en = sentence.en

        if new_en is not None:
            sentence.en = new_en

        update_dict = sentence_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if key != 'en':
                setattr(sentence, key, value)

        self.db.commit()
        self.db.refresh(sentence)

        result = {
            "id": sentence.id,
            "page_id": sentence.page_id,
            "sentence_order": sentence.sentence_order,
            "en": sentence.en,
            "zh": sentence.zh,
            "audio_url": sentence.audio_url,
            "created_at": sentence.created_at,
            "translating": False,
        }

        if new_en is not None and new_en != old_en:
            result["translating"] = True

        return result

    def create_sentence(self, book_id: int, user_id: int, page_number: int, sentence_data: SentenceCreateRequest) -> dict:
        """创建句子。"""
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        page = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number == page_number,
        ).first()

        if not page:
            raise NotFoundException(message="页面未找到")

        max_order = self.db.query(Sentence).filter(Sentence.page_id == page.id).count()
        new_order = max_order + 1

        sentence = Sentence(
            page_id=page.id,
            sentence_order=new_order,
            en=sentence_data.en,
            zh=sentence_data.zh or "",
        )
        self.db.add(sentence)
        self.db.commit()
        self.db.refresh(sentence)

        logger.info(f"创建句子: sentence_id={sentence.id}, page_id={page.id}")

        return {
            "id": sentence.id,
            "page_id": sentence.page_id,
            "sentence_order": sentence.sentence_order,
            "en": sentence.en,
            "zh": sentence.zh,
            "audio_url": sentence.audio_url,
            "created_at": sentence.created_at,
        }

    def reorder_sentences(self, book_id: int, user_id: int, page_number: int, sentence_ids: list[int]) -> None:
        """重新排序句子。"""
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        page = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number == page_number,
        ).first()

        if not page:
            raise NotFoundException(message="页面未找到")

        for index, sentence_id in enumerate(sentence_ids):
            sentence = self.db.query(Sentence).filter(
                Sentence.id == sentence_id,
                Sentence.page_id == page.id,
            ).first()
            if sentence:
                sentence.sentence_order = index + 1

        self.db.commit()
        logger.info(f"句子排序已更新: book_id={book_id}, page={page_number}")

    def delete_sentence(self, book_id: int, user_id: int, sentence_id: int) -> None:
        """删除句子。"""
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        sentence = self.db.query(Sentence).filter(Sentence.id == sentence_id).first()

        if not sentence:
            raise NotFoundException(message="句子未找到")

        page = self.db.query(BookPage).filter(BookPage.id == sentence.page_id).first()
        if not page or page.book_id != book_id:
            raise NotFoundException(message="句子不属于该书籍")

        self.db.delete(sentence)
        self.db.commit()

        remaining = self.db.query(Sentence).filter(Sentence.page_id == page.id).order_by(Sentence.sentence_order).all()
        for index, s in enumerate(remaining):
            s.sentence_order = index + 1

        self.db.commit()
        logger.info(f"删除句子: sentence_id={sentence_id}")

    # ========================================
    # 书架相关方法
    # ========================================

    def add_to_shelf(self, user_id: int, book_id: int) -> None:
        """将绘本加入书架。"""
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise NotFoundException(message="书籍未找到")

        if book.user_id == user_id:
            return

        existing = self.db.query(Bookshelf).filter(
            Bookshelf.user_id == user_id,
            Bookshelf.book_id == book_id,
        ).first()

        if existing:
            return

        shelf_item = Bookshelf(user_id=user_id, book_id=book_id)
        self.db.add(shelf_item)
        book.shelf_count += 1

        self.db.commit()
        logger.info(f"加入书架: user_id={user_id}, book_id={book_id}")

    def remove_from_shelf(self, user_id: int, book_id: int) -> None:
        """从书架移除绘本。"""
        shelf_item = self.db.query(Bookshelf).filter(
            Bookshelf.user_id == user_id,
            Bookshelf.book_id == book_id,
        ).first()

        if shelf_item:
            self.db.delete(shelf_item)
            book = self.db.query(Book).filter(Book.id == book_id).first()
            if book and book.shelf_count > 0:
                book.shelf_count -= 1
            self.db.commit()
            logger.info(f"移出书架: user_id={user_id}, book_id={book_id}")

    def is_in_shelf(self, user_id: int, book_id: int) -> bool:
        """检查绘本是否在书架中。"""
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if book and book.user_id == user_id:
            return True

        shelf_item = self.db.query(Bookshelf).filter(
            Bookshelf.user_id == user_id,
            Bookshelf.book_id == book_id,
        ).first()

        return shelf_item is not None

    def create_page(
        self,
        book_id: int,
        user_id: int,
        image_data: bytes,
        page_number: int | None = None,
        run_ocr: bool = True,
    ) -> dict:
        """创建新页面。"""
        from app.services.file_storage_service import file_storage

        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()
        if not book:
            raise NotFoundException(message="书籍未找到")

        max_page = self.db.query(BookPage).filter(BookPage.book_id == book_id).count()

        if page_number is None or page_number > max_page + 1:
            page_number = max_page + 1
        elif page_number < 1:
            page_number = 1

        if page_number <= max_page:
            pages_to_shift = self.db.query(BookPage).filter(
                BookPage.book_id == book_id,
                BookPage.page_number >= page_number,
            ).all()
            for p in pages_to_shift:
                p.page_number += 1

        relative_path = file_storage.save_page_image(
            book_id=book_id,
            page_number=page_number,
            image_data=image_data,
        )
        image_url = f"/static/{relative_path}"

        page = BookPage(
            book_id=book_id,
            page_number=page_number,
            image_url=image_url,
            status="processing" if run_ocr else "completed",
        )
        self.db.add(page)
        self.db.commit()
        self.db.refresh(page)

        logger.info(f"创建页面: book_id={book_id}, page_number={page_number}")

        return {
            "id": page.id,
            "book_id": page.book_id,
            "page_number": page.page_number,
            "image_url": page.image_url,
            "status": page.status,
            "created_at": page.created_at,
        }

    def delete_page(self, book_id: int, user_id: int, page_number: int) -> None:
        """删除页面。"""
        book = self.db.query(Book).filter(Book.id == book_id, Book.user_id == user_id).first()
        if not book:
            raise NotFoundException(message="书籍未找到")

        page = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number == page_number,
        ).first()

        if not page:
            raise NotFoundException(message="页面未找到")

        self.db.delete(page)
        self.db.commit()

        pages_to_shift = self.db.query(BookPage).filter(
            BookPage.book_id == book_id,
            BookPage.page_number > page_number,
        ).order_by(BookPage.page_number).all()

        for p in pages_to_shift:
            p.page_number -= 1

        self.db.commit()
        logger.info(f"删除页面: book_id={book_id}, page_number={page_number}")