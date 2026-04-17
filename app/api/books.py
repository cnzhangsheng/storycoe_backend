"""API routes for books."""
import asyncio
import traceback
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from loguru import logger

from app.api.auth import get_current_user
from app.models.db_models import Sentence
from app.models.schemas import (
    BookCreate,
    BookUpdate,
    BookResponse,
    BookDetailResponse,
    BookListResponse,
    ShelfListResponse,
    BookPageDetailResponse,
    BookPageResponse,
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


@router.post("/generate", response_model=GenerateBookResponse)
async def generate_book(
    request: GenerateBookRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Generate a book from images (async task)."""
    result = book_service.generate_book(current_user["id"], request)

    # 启动后台 OCR 任务（下载图片并识别）
    background_tasks.add_task(
        process_generate_ocr_task,
        result.book_id,
        request.images,
    )

    return result


async def process_generate_ocr_task(book_id: int, image_urls: list[str]):
    """后台 OCR 处理任务（从 URL 下载图片）。

    Args:
        book_id: 书籍 ID
        image_urls: 图片 URL 列表
    """
    import httpx
    from app.core.database import SessionLocal
    from app.models.db_models import Book, BookPage
    from app.services.ocr_service import ocr_service

    db = SessionLocal()
    try:
        logger.info(f"[GenerateOCR] 开始后台任务: book_id={book_id}, pages={len(image_urls)}")

        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            logger.error(f"[GenerateOCR] 书籍不存在: book_id={book_id}")
            return

        book.status = "processing"
        db.commit()

        # 下载所有图片
        page_data_list = []
        pages = db.query(BookPage).filter(BookPage.book_id == book_id).order_by(BookPage.page_number).all()

        async with httpx.AsyncClient(timeout=60.0) as client:
            for page, url in zip(pages, image_urls):
                try:
                    # 处理相对 URL
                    if url.startswith("/static/"):
                        # 本地文件，直接读取
                        from app.core.config import settings
                        file_path = url.replace("/static/", settings.upload_dir + "/")
                        with open(file_path, "rb") as f:
                            image_data = f.read()
                    else:
                        # 远程 URL，下载
                        resp = await client.get(url)
                        image_data = resp.content

                    page_data_list.append((page.id, image_data))
                    logger.debug(f"[GenerateOCR] 下载图片成功: page_id={page.id}, size={len(image_data)}")
                except Exception as e:
                    logger.warning(f"[GenerateOCR] 下载图片失败: url={url}, error={e}")

        if not page_data_list:
            book.status = "error"
            db.commit()
            logger.error(f"[GenerateOCR] 没有有效图片")
            return

        # 并行 OCR 识别
        ocr_tasks = [
            ocr_service.recognize_image(image_data)
            for _, image_data in page_data_list
        ]
        ocr_results = await asyncio.gather(*ocr_tasks)

        # 保存句子
        for page_id, sentences in zip([p[0] for p in page_data_list], ocr_results):
            for j, sentence in enumerate(sentences):
                sentence_record = Sentence(
                    page_id=page_id,
                    sentence_order=j + 1,
                    en=sentence.en,
                    zh=sentence.zh,
                )
                db.add(sentence_record)

        db.commit()

        book.status = "completed"
        book.has_audio = True
        db.commit()

        logger.info(f"[GenerateOCR] 后台任务完成: book_id={book_id}")

    except Exception as e:
        logger.error(f"[GenerateOCR] 后台任务失败: book_id={book_id}, error={e}\n{traceback.format_exc()}")
        try:
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                book.status = "error"
                db.commit()
        except:
            pass
    finally:
        db.close()


@router.get("", response_model=ShelfListResponse)
async def list_books(
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """获取绘本架分类列表（我的绘本架 + 喜欢的绘本）."""
    return book_service.list_books(user_id=current_user["id"])


@router.get("/public", response_model=BookListResponse)
async def list_public_books(
    page: int = 1,
    page_size: int = 20,
    level: int | None = None,
    book_service: Annotated[BookService, Depends(get_book_service)] = None,
):
    """List public books (no authentication required)."""
    return book_service.list_public_books(
        page=page,
        page_size=page_size,
        level=level,
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
    book_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Get a specific book by ID with pages."""
    book = book_service.get_book(book_id, current_user["id"])
    return BookDetailResponse(**book)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: int,
    book_data: BookUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Update a book."""
    book = book_service.update_book(book_id, current_user["id"], book_data)
    return BookResponse(**book)


@router.delete("/{book_id}")
async def delete_book(
    book_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Delete a book and all its pages."""
    book_service.delete_book(book_id, current_user["id"])
    return MessageResponse(message="书籍已删除", success=True)


@router.get("/{book_id}/pages/{page_number}", response_model=BookPageDetailResponse)
async def get_book_page(
    book_id: int,
    page_number: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Get a specific page of a book with sentences."""
    page = book_service.get_book_page(book_id, current_user["id"], page_number)
    return BookPageDetailResponse(**page)


@router.post("/{book_id}/pages/{page_number}/sentences", response_model=SentenceResponse)
async def create_sentence(
    book_id: int,
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
    book_id: int,
    sentence_id: int,
    sentence_data: SentenceUpdate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """更新句子。

    当英文句子有变化时，会在后台异步翻译成中文。
    返回结果中 translating=True 表示正在翻译中。
    """
    sentence = await book_service.update_sentence(book_id, current_user["id"], sentence_id, sentence_data)

    # 如果需要翻译，启动后台任务
    if sentence.pop("translating", False):
        from app.core.database import SessionLocal
        from app.services.translation_service import translation_service
        from app.models.db_models import Sentence

        async def do_translate():
            """后台翻译任务"""
            db = SessionLocal()
            try:
                sentence_obj = db.query(Sentence).filter(Sentence.id == sentence_id).first()
                if sentence_obj and sentence_obj.en:
                    new_zh = await translation_service.translate_sentence(sentence_obj.en)
                    if new_zh:
                        sentence_obj.zh = new_zh
                        db.commit()
            except Exception as e:
                print(f"翻译失败: {e}")
            finally:
                db.close()

        background_tasks.add_task(do_translate)

    return SentenceResponse(**sentence)


@router.put("/{book_id}/pages/{page_number}/sentences/reorder")
async def reorder_sentences(
    book_id: int,
    page_number: int,
    request: SentenceReorderRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Reorder sentences in a book page."""
    book_service.reorder_sentences(book_id, current_user["id"], page_number, request.sentence_ids)
    return MessageResponse(message="句子排序已更新", success=True)


@router.delete("/{book_id}/sentences/{sentence_id}")
async def delete_sentence(
    book_id: int,
    sentence_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """Delete a sentence from a book."""
    book_service.delete_sentence(book_id, current_user["id"], sentence_id)
    return MessageResponse(message="句子已删除", success=True)


# ========================================
# 书架相关 API
# ========================================


@router.post("/{book_id}/shelf", response_model=MessageResponse)
async def add_to_shelf(
    book_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """将绘本加入书架."""
    book_service.add_to_shelf(current_user["id"], book_id)
    return MessageResponse(message="已加入书架", success=True)


@router.delete("/{book_id}/shelf", response_model=MessageResponse)
async def remove_from_shelf(
    book_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """从书架移除绘本."""
    book_service.remove_from_shelf(current_user["id"], book_id)
    return MessageResponse(message="已移出书架", success=True)


@router.get("/{book_id}/shelf-status")
async def check_shelf_status(
    book_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """检查绘本是否在书架中."""
    in_shelf = book_service.is_in_shelf(current_user["id"], book_id)
    return {"in_shelf": in_shelf}


# ========================================
# 页面管理 API（仅作者可操作）
# ========================================


@router.post("/{book_id}/pages", response_model=BookPageResponse)
async def create_page(
    book_id: int,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    page_number: int | None = None,
    run_ocr: bool = True,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
    book_service: Annotated[BookService, Depends(get_book_service)] = None,
):
    """创建新页面（仅作者可操作）。

    Args:
        book_id: 书籍 ID
        image: 页面图片
        page_number: 页码（可选，默认添加到最后）
        run_ocr: 是否运行 OCR 识别（默认 True）

    Returns:
        创建的页面信息
    """
    image_data = await image.read()
    page = book_service.create_page(
        book_id=book_id,
        user_id=current_user["id"],
        image_data=image_data,
        page_number=page_number,
        run_ocr=run_ocr,
    )

    # 如果需要 OCR，启动后台任务
    if run_ocr:
        from app.api.generate import process_single_page_ocr
        background_tasks.add_task(
            process_single_page_ocr,
            page_id=page["id"],
            image_data=image_data,
        )

    return BookPageResponse(**page)


@router.delete("/{book_id}/pages/{page_number}", response_model=MessageResponse)
async def delete_page(
    book_id: int,
    page_number: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """删除页面（仅作者可操作）。

    删除后会自动重新排序后续页面。

    Args:
        book_id: 书籍 ID
        page_number: 页码
    """
    book_service.delete_page(book_id, current_user["id"], page_number)
    return MessageResponse(message="页面已删除", success=True)