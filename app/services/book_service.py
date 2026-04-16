"""Book service using SQLAlchemy."""
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundException
from app.models.schemas import (
    BookCreate,
    BookUpdate,
    BookResponse,
    BookListResponse,
    ShelfListResponse,
    BookPageDetailResponse,
    GenerateBookRequest,
    GenerateBookResponse,
    SentenceUpdate,
    SentenceCreateRequest,
)
from app.models.db_models import Book, BookPage, Sentence, Bookshelf, ReadingProgress
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
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> ShelfListResponse:
        """获取绘本架分类列表。

        Args:
            user_id: 用户 ID
            page: 页码
            page_size: 每页数量
            status: 状态筛选

        Returns:
            分类书籍响应（我的绘本 + 喜欢的绘本）
        """
        # 1. 查询用户自己的所有绘本（不区分 private/public）
        my_books_query = self.db.query(Book).filter(Book.user_id == UUID(user_id))
        if status:
            my_books_query = my_books_query.filter(Book.status == status)
        my_books = my_books_query.order_by(Book.created_at.desc()).all()
        total_my = len(my_books)

        # 2. 查询喜欢的绘本（书架中其他人的 public 书籍）
        liked_books_query = (
            self.db.query(Book)
            .join(Bookshelf, Book.id == Bookshelf.book_id)
            .filter(
                Bookshelf.user_id == UUID(user_id),
                Book.user_id != UUID(user_id),  # 排除自己的书
                Book.share_type == "public",  # 只有公开书籍
            )
        )
        if status:
            liked_books_query = liked_books_query.filter(Book.status == status)
        liked_books = liked_books_query.order_by(Book.created_at.desc()).all()
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
        """获取公开绘本列表。

        Args:
            page: 页码
            page_size: 每页数量
            level: 级别筛选

        Returns:
            书籍列表响应
        """
        query = self.db.query(Book).filter(
            Book.share_type == "public",
            Book.status == "completed",
        )

        if level:
            query = query.filter(Book.level == level)

        # 获取总数
        total = query.count()

        # 分页查询
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

    def create_book(self, user_id: str, book_data: BookCreate) -> dict:
        """创建书籍。

        Args:
            user_id: 用户 ID
            book_data: 书籍创建数据

        Returns:
            创建的书籍数据
        """
        book = Book(
            user_id=UUID(user_id),
            title=book_data.title,
            level=book_data.level,
            cover_image=book_data.cover_image,
            share_type=book_data.share_type,
            is_new=True,
            status="draft",
        )
        self.db.add(book)

        # 更新用户创作绘本数（排行榜统计）
        user = self.db.query(User).filter(User.id == UUID(user_id)).first()
        if user:
            user.books_created += 1
            logger.debug(f"更新用户创作数: user_id={user_id}, books_created={user.books_created}")

        self.db.commit()
        self.db.refresh(book)

        logger.info(f"创建书籍: book_id={book.id}, user_id={user_id}, title={book_data.title}, share_type={book.share_type}")

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
            "share_type": book.share_type,
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
        # 先查询书籍（不限制用户）
        book = self.db.query(Book).filter(Book.id == UUID(book_id)).first()

        if not book:
            logger.warning(f"书籍不存在: book_id={book_id}")
            raise NotFoundException(message="书籍未找到")

        # 权限检查：用户是所有者，或者书籍是公开的
        # 注意：book.user_id 是 UUID 类型，需要转换为字符串比较
        if str(book.user_id) != user_id and book.share_type != "public":
            logger.warning(f"无权限访问书籍: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 获取书籍的所有页面
        pages = self.db.query(BookPage).filter(BookPage.book_id == book_id).order_by(BookPage.page_number).all()

        # 构建页面列表（包含句子）
        pages_data = []
        for page in pages:
            # 获取该页面的所有句子
            sentences = self.db.query(Sentence).filter(Sentence.page_id == page.id).order_by(Sentence.sentence_order).all()

            pages_data.append({
                "id": str(page.id),
                "book_id": str(page.book_id),
                "page_number": page.page_number,
                "image_url": page.image_url,
                "status": page.status,
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
            "share_type": book.share_type,
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
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()

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
        """删除书籍及其所有关联数据。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID

        Raises:
            NotFoundException: 书籍不存在
        """
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        book_uuid = UUID(book_id)

        # 1. 删除所有书架关联记录（其他人收藏的）
        self.db.query(Bookshelf).filter(Bookshelf.book_id == book_uuid).delete()
        logger.info(f"删除书架关联: book_id={book_id}")

        # 2. 删除所有阅读进度记录
        self.db.query(ReadingProgress).filter(ReadingProgress.book_id == book_uuid).delete()
        logger.info(f"删除阅读进度: book_id={book_id}")

        # 3. 获取所有页面 ID
        page_ids = [p.id for p in self.db.query(BookPage.id).filter(BookPage.book_id == book_uuid).all()]

        # 4. 删除所有句子
        if page_ids:
            self.db.query(Sentence).filter(Sentence.page_id.in_(page_ids)).delete(synchronize_session=False)
            logger.info(f"删除句子: book_id={book_id}, pages={len(page_ids)}")

        # 5. 删除所有页面
        self.db.query(BookPage).filter(BookPage.book_id == book_uuid).delete()
        logger.info(f"删除页面: book_id={book_id}")

        # 6. 删除书籍本身
        self.db.delete(book)

        # 7. 更新用户创作绘本数（排行榜统计）
        user = self.db.query(User).filter(User.id == UUID(user_id)).first()
        if user and user.books_created > 0:
            user.books_created -= 1
            logger.debug(f"更新用户创作数: user_id={user_id}, books_created={user.books_created}")

        self.db.commit()
        logger.info(f"删除书籍完成: book_id={book_id}, user_id={user_id}")

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
        # 校验书籍权限（用户是所有者，或者书籍是公开的）
        book = self.db.query(Book).filter(Book.id == UUID(book_id)).first()

        if not book:
            raise NotFoundException(message="书籍未找到")

        if str(book.user_id) != user_id and book.share_type != "public":
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
            "status": page.status,
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
        """生成书籍（从已上传的图片URL）。

        Args:
            user_id: 用户 ID
            request: 生成请求（包含图片 URL）

        Returns:
            生成响应
        """
        title = request.title or "我的绘本"

        # 创建书籍记录
        book = Book(
            user_id=UUID(user_id),
            title=title,
            level=request.level,
            status="generating",
            is_new=True,
            share_type=request.share_type,
            cover_image=request.cover_image,
        )
        self.db.add(book)
        self.db.flush()

        # 创建页面记录（从图片 URL）
        for i, image_url in enumerate(request.images):
            page = BookPage(
                book_id=book.id,
                page_number=i + 1,
                image_url=image_url,
                status="pending",  # 等待 OCR 处理
            )
            self.db.add(page)

        self.db.commit()
        self.db.refresh(book)

        logger.info(f"创建生成任务: book_id={book.id}, user_id={user_id}, pages={len(request.images)}, share_type={request.share_type}")

        # TODO: 触发异步 OCR 任务处理每个页面

        return GenerateBookResponse(
            book_id=book.id,
            status="generating",
            message="绘本创建成功，正在后台处理文字识别",
            total_pages=len(request.images),
        )

    async def update_sentence(self, book_id: str, user_id: str, sentence_id: str, sentence_data: SentenceUpdate) -> dict:
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
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()

        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 查找句子
        sentence = self.db.query(Sentence).filter(Sentence.id == UUID(sentence_id)).first()

        if not sentence:
            raise NotFoundException(message="句子未找到")

        # 校验句子所属页面是否属于该书籍
        page = self.db.query(BookPage).filter(BookPage.id == sentence.page_id).first()
        if not page or str(page.book_id) != str(book_id):
            logger.warning(f"句子不属于该书籍: sentence_id={sentence_id}, page_book_id={page.book_id if page else None}, request_book_id={book_id}")
            raise NotFoundException(message="句子不属于该书籍")

        # 检查英文是否有变化
        new_en = sentence_data.en
        old_en = sentence.en

        # 立即更新英文（不等待翻译）
        if new_en is not None:
            sentence.en = new_en

        # 更新其他字段
        update_dict = sentence_data.model_dump(exclude_unset=True)
        if update_dict:
            for key, value in update_dict.items():
                if key != 'en':  # 英文已经单独处理
                    setattr(sentence, key, value)

        self.db.commit()
        self.db.refresh(sentence)
        logger.info(f"句子已更新: sentence_id={sentence_id}")

        # 返回结果，包含是否需要翻译的标记
        result = {
            "id": str(sentence.id),
            "page_id": str(sentence.page_id),
            "sentence_order": sentence.sentence_order,
            "en": sentence.en,
            "zh": sentence.zh,
            "audio_url": sentence.audio_url,
            "created_at": sentence.created_at,
            "translating": False,  # 标记是否正在翻译
        }

        # 如果英文有变化，启动异步翻译
        if new_en is not None and new_en != old_en:
            result["translating"] = True
            logger.info(f"英文句子有变化，将异步翻译: '{old_en}' -> '{new_en}'")

        return result

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
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()

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

        # 直接使用传入的中文翻译，不再自动翻译
        zh = sentence_data.zh if sentence_data.zh else ""

        # 创建新句子（序号为当前最大+1）
        new_order = max_order + 1
        sentence = Sentence(
            page_id=page.id,
            sentence_order=new_order,
            en=sentence_data.en,
            zh=zh,
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
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()

        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 获取页面
        page = self.db.query(BookPage).filter(
            BookPage.book_id == UUID(book_id),
            BookPage.page_number == page_number,
        ).first()

        if not page:
            logger.warning(f"页面不存在: book_id={book_id}, page_number={page_number}")
            raise NotFoundException(message="页面未找到")

        # 更新句子排序
        for index, sentence_id in enumerate(sentence_ids):
            sentence = self.db.query(Sentence).filter(
                Sentence.id == UUID(sentence_id),
                Sentence.page_id == page.id,
            ).first()

            if sentence:
                sentence.sentence_order = index + 1

        self.db.commit()
        logger.info(f"句子排序已更新: book_id={book_id}, page={page_number}, order={sentence_ids}")

    def delete_sentence(self, book_id: str, user_id: str, sentence_id: str) -> None:
        """删除句子。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID
            sentence_id: 句子 ID

        Raises:
            NotFoundException: 书籍或句子不存在
        """
        # 校验书籍权限
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()

        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 查找句子
        sentence = self.db.query(Sentence).filter(Sentence.id == UUID(sentence_id)).first()

        if not sentence:
            logger.warning(f"句子不存在: sentence_id={sentence_id}")
            raise NotFoundException(message="句子未找到")

        # 校验句子所属页面是否属于该书籍
        page = self.db.query(BookPage).filter(BookPage.id == sentence.page_id).first()
        if not page or str(page.book_id) != str(book_id):
            logger.warning(f"句子不属于该书籍: sentence_id={sentence_id}")
            raise NotFoundException(message="句子不属于该书籍")

        # 删除句子
        self.db.delete(sentence)
        self.db.commit()

        # 重新排序剩余句子
        remaining_sentences = self.db.query(Sentence).filter(
            Sentence.page_id == page.id
        ).order_by(Sentence.sentence_order).all()

        for index, s in enumerate(remaining_sentences):
            s.sentence_order = index + 1

        self.db.commit()
        logger.info(f"删除句子: sentence_id={sentence_id}, book_id={book_id}")

    # ========================================
    # 书架相关方法
    # ========================================

    def add_to_shelf(self, user_id: str, book_id: str) -> None:
        """将绘本加入书架。

        Args:
            user_id: 用户 ID
            book_id: 书籍 ID

        Raises:
            NotFoundException: 书籍不存在或不公开
        """
        # 检查书籍是否存在且公开
        book = self.db.query(Book).filter(Book.id == UUID(book_id)).first()
        if not book:
            raise NotFoundException(message="书籍未找到")

        # 不能把自己的书加入书架
        if str(book.user_id) == str(user_id):
            return  # 静默返回，自己的书已经在列表中了

        # 检查是否已在书架中
        existing = self.db.query(Bookshelf).filter(
            Bookshelf.user_id == UUID(user_id),
            Bookshelf.book_id == UUID(book_id),
        ).first()

        if existing:
            return  # 已在书架中，静默返回

        # 添加到书架
        shelf_item = Bookshelf(user_id=UUID(user_id), book_id=UUID(book_id))
        self.db.add(shelf_item)

        # 更新绘本收藏数（排行榜统计）
        book.shelf_count += 1
        logger.debug(f"更新绘本收藏数: book_id={book_id}, shelf_count={book.shelf_count}")

        self.db.commit()
        logger.info(f"加入书架: user_id={user_id}, book_id={book_id}")

    def remove_from_shelf(self, user_id: str, book_id: str) -> None:
        """从书架移除绘本。

        Args:
            user_id: 用户 ID
            book_id: 书籍 ID
        """
        shelf_item = self.db.query(Bookshelf).filter(
            Bookshelf.user_id == UUID(user_id),
            Bookshelf.book_id == UUID(book_id),
        ).first()

        if shelf_item:
            self.db.delete(shelf_item)

            # 更新绘本收藏数（排行榜统计）
            book = self.db.query(Book).filter(Book.id == UUID(book_id)).first()
            if book and book.shelf_count > 0:
                book.shelf_count -= 1
                logger.debug(f"更新绘本收藏数: book_id={book_id}, shelf_count={book.shelf_count}")

            self.db.commit()
            logger.info(f"移出书架: user_id={user_id}, book_id={book_id}")

    def is_in_shelf(self, user_id: str, book_id: str) -> bool:
        """检查绘本是否在书架中。

        Args:
            user_id: 用户 ID
            book_id: 书籍 ID

        Returns:
            是否在书架中
        """
        # 如果是自己的书，返回 True
        book = self.db.query(Book).filter(Book.id == UUID(book_id)).first()
        if book and str(book.user_id) == str(user_id):
            return True

        # 检查书架
        shelf_item = self.db.query(Bookshelf).filter(
            Bookshelf.user_id == UUID(user_id),
            Bookshelf.book_id == UUID(book_id),
        ).first()

        return shelf_item is not None

    def create_page(
        self,
        book_id: str,
        user_id: str,
        image_data: bytes,
        page_number: int | None = None,
        run_ocr: bool = True,
    ) -> dict:
        """创建新页面。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID（用于权限校验）
            image_data: 图片数据
            page_number: 页码（可选，默认添加到最后）
            run_ocr: 是否运行 OCR 识别（默认 True）

        Returns:
            创建的页面数据

        Raises:
            NotFoundException: 书籍不存在或无权限
        """
        from app.services.file_storage_service import file_storage

        # 校验书籍权限
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()
        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 获取当前最大页码
        max_page = self.db.query(BookPage).filter(BookPage.book_id == UUID(book_id)).count()

        # 确定新页面页码
        if page_number is None or page_number > max_page + 1:
            page_number = max_page + 1
        elif page_number < 1:
            page_number = 1

        # 如果插入中间位置，需要移动后续页面
        if page_number <= max_page:
            pages_to_shift = self.db.query(BookPage).filter(
                BookPage.book_id == UUID(book_id),
                BookPage.page_number >= page_number,
            ).all()
            for p in pages_to_shift:
                p.page_number += 1
            logger.info(f"移动页面: book_id={book_id}, 从第{page_number}页开始向后移动")

        # 保存图片
        relative_path = file_storage.save_page_image(
            book_id=book_id,
            page_number=page_number,
            image_data=image_data,
        )
        image_url = f"/static/{relative_path}"

        # 创建页面记录
        page = BookPage(
            book_id=UUID(book_id),
            page_number=page_number,
            image_url=image_url,
            status="processing" if run_ocr else "completed",
        )
        self.db.add(page)
        self.db.commit()
        self.db.refresh(page)

        logger.info(f"创建页面: book_id={book_id}, page_number={page_number}, run_ocr={run_ocr}")

        return {
            "id": str(page.id),
            "book_id": str(page.book_id),
            "page_number": page.page_number,
            "image_url": page.image_url,
            "status": page.status,
            "created_at": page.created_at,
        }

    def delete_page(self, book_id: str, user_id: str, page_number: int) -> None:
        """删除页面。

        Args:
            book_id: 书籍 ID
            user_id: 用户 ID（用于权限校验）
            page_number: 页码

        Raises:
            NotFoundException: 书籍或页面不存在
        """
        # 校验书籍权限
        book = self.db.query(Book).filter(Book.id == UUID(book_id), Book.user_id == UUID(user_id)).first()
        if not book:
            logger.warning(f"书籍不存在或无权限: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 查找页面
        page = self.db.query(BookPage).filter(
            BookPage.book_id == UUID(book_id),
            BookPage.page_number == page_number,
        ).first()

        if not page:
            logger.warning(f"页面不存在: book_id={book_id}, page_number={page_number}")
            raise NotFoundException(message="页面未找到")

        # 删除页面（关联的句子会级联删除）
        self.db.delete(page)
        self.db.commit()

        # 重新排序后续页面
        pages_to_shift = self.db.query(BookPage).filter(
            BookPage.book_id == UUID(book_id),
            BookPage.page_number > page_number,
        ).order_by(BookPage.page_number).all()

        for p in pages_to_shift:
            p.page_number -= 1

        self.db.commit()
        logger.info(f"删除页面: book_id={book_id}, page_number={page_number}, 移动{len(pages_to_shift)}个后续页面")