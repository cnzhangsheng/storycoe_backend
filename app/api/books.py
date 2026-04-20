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
    from app.models.db_models import Book, BookPage, Sentence
    from app.services.ocr_service import ocr_service, OcrSentence
    from app.services.tts_service import tts_service

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

        if len(pages) != len(image_urls):
            logger.warning(f"[GenerateOCR] 页面数不匹配: pages={len(pages)}, urls={len(image_urls)}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i, url in enumerate(image_urls):
                try:
                    # 处理相对 URL
                    if url.startswith("/static/"):
                        # 本地文件，直接读取
                        from app.core.config import settings
                        import os
                        file_path = os.path.join(settings.upload_dir, url.replace("/static/", ""))
                        with open(file_path, "rb") as f:
                            image_data = f.read()
                    else:
                        # 远程 URL，下载
                        resp = await client.get(url)
                        image_data = resp.content

                    if i < len(pages):
                        page_data_list.append((pages[i].id, image_data))
                        logger.info(f"[GenerateOCR] 下载图片成功: page_id={pages[i].id}, size={len(image_data)}")
                    else:
                        logger.warning(f"[GenerateOCR] 跳过超出范围的图片: i={i}")
                except Exception as e:
                    logger.error(f"[GenerateOCR] 下载图片失败: url={url}, error={e}")

        if not page_data_list:
            book.status = "error"
            db.commit()
            logger.error(f"[GenerateOCR] 没有有效图片")
            return

        # 并行 OCR 识别
        logger.info(f"[GenerateOCR] 开始 OCR 识别: {len(page_data_list)} 张图片")
        ocr_tasks = [
            ocr_service.recognize_image(image_data)
            for _, image_data in page_data_list
        ]
        ocr_results: list[list[OcrSentence]] = await asyncio.gather(*ocr_tasks, return_exceptions=True)

        # 保存句子并更新页面状态
        total_sentences = 0
        sentence_records = []  # 收集句子记录用于后续 TTS

        for idx, (page_id, _) in enumerate(page_data_list):
            result = ocr_results[idx]

            # 处理 OCR 异常
            if isinstance(result, Exception):
                logger.error(f"[GenerateOCR] OCR 失败: page_id={page_id}, error={result}")
                continue

            sentences = result
            logger.info(f"[GenerateOCR] OCR 结果: page_id={page_id}, sentences={len(sentences)}")

            # 更新页面状态
            page = db.query(BookPage).filter(BookPage.id == page_id).first()
            if page:
                page.status = "completed"

            # 保存句子
            for j, sentence in enumerate(sentences):
                if not sentence.en.strip():
                    continue
                sentence_record = Sentence(
                    page_id=page_id,
                    sentence_order=j + 1,
                    en=sentence.en.strip(),
                    zh=sentence.zh.strip() if sentence.zh else "",
                    status="pending",  # OCR 后需要生成 TTS
                )
                db.add(sentence_record)
                db.flush()  # 获取 sentence_id
                sentence_records.append(sentence_record)
                total_sentences += 1

        db.commit()
        logger.info(f"[GenerateOCR] 保存句子: {total_sentences} 个")

        # 并行生成所有句子的 TTS 音频
        if sentence_records:
            logger.info(f"[TTS] 开始生成音频: {len(sentence_records)} 个句子")

            # 更新所有句子状态为 generating_tts
            for sr in sentence_records:
                sr.status = "generating_tts"
            db.commit()

            tts_tasks = [
                tts_service.generate_all_accents(
                    text=sr.en,
                    book_id=book_id,
                    sentence_id=sr.id,
                )
                for sr in sentence_records
            ]
            tts_results = await asyncio.gather(*tts_tasks, return_exceptions=True)

            # 更新句子的音频 URL 和状态
            for sr, result in zip(sentence_records, tts_results):
                if isinstance(result, Exception):
                    logger.error(f"[TTS] 音频生成失败: sentence_id={sr.id}, error={result}")
                    sr.status = "error"
                    continue
                if result:
                    sr.audio_us_normal = result.get("us_normal")
                    sr.audio_us_slow = result.get("us_slow")
                    sr.audio_gb_normal = result.get("gb_normal")
                    sr.audio_gb_slow = result.get("gb_slow")
                    sr.status = "completed"
                else:
                    sr.status = "error"

            db.commit()
            logger.info(f"[TTS] 音频生成完成: {len(sentence_records)} 个句子")

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


@router.post("/{book_id}/sentences/{sentence_id}/translate")
async def translate_sentence(
    book_id: int,
    sentence_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """翻译句子。

    调用大模型翻译英文句子为中文，返回翻译结果。
    """
    from app.services.translation_service import translation_service

    # 验证权限
    book = book_service.get_book(book_id, current_user["id"])
    if not book:
        raise HTTPException(status_code=404, detail="书籍未找到")

    # 获取句子
    sentence = book_service.db.query(Sentence).filter(Sentence.id == sentence_id).first()
    if not sentence:
        raise HTTPException(status_code=404, detail="句子未找到")

    if not sentence.en:
        raise HTTPException(status_code=400, detail="句子没有英文内容")

    # 调用翻译服务
    logger.info(f"[Translate] 开始翻译: sentence_id={sentence_id}, en={sentence.en}")
    zh = await translation_service.translate_sentence(sentence.en)

    if zh:
        # 更新数据库
        sentence.zh = zh
        book_service.db.commit()
        logger.info(f"[Translate] 翻译完成: sentence_id={sentence_id}, zh={zh}")

        return {
            "success": True,
            "sentence_id": sentence_id,
            "zh": zh,
        }
    else:
        return {
            "success": False,
            "sentence_id": sentence_id,
            "zh": "",
            "message": "翻译失败",
        }


@router.post("/{book_id}/pages/{page_number}/sentences", response_model=SentenceResponse)
async def create_sentence(
    book_id: int,
    page_number: int,
    sentence_data: SentenceCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
    book_service: Annotated[BookService, Depends(get_book_service)],
):
    """创建句子。

    创建后会在后台异步翻译中文（如果没有提供）并生成 TTS 音频。
    返回结果中 status=pending 表示正在后台处理。
    """
    sentence = book_service.create_sentence(book_id, current_user["id"], page_number, sentence_data)

    # 如果需要后台处理，启动任务
    if sentence["status"] == "pending" and sentence["en"]:
        async def do_regenerate():
            """后台任务：翻译 + 生成 TTS"""
            from app.core.database import SessionLocal
            from app.models.db_models import Sentence, Book, BookPage
            from app.services.translation_service import translation_service
            from app.services.tts_service import tts_service

            db = SessionLocal()
            try:
                sentence_id = sentence["id"]
                sentence_obj = db.query(Sentence).filter(Sentence.id == sentence_id).first()
                if not sentence_obj:
                    return

                # 获取 book_id
                page = db.query(BookPage).filter(BookPage.id == sentence_obj.page_id).first()
                book = db.query(Book).filter(Book.id == page.book_id).first() if page else None
                if not book:
                    return

                # 翻译（如果没有中文或中文为空）- 不改变 status
                if not sentence_obj.zh and sentence_obj.en:
                    logger.info(f"[Regenerate] 开始翻译: sentence_id={sentence_id}")
                    new_zh = await translation_service.translate_sentence(sentence_obj.en)
                    if new_zh:
                        sentence_obj.zh = new_zh
                        db.commit()
                        logger.info(f"[Regenerate] 翻译完成: sentence_id={sentence_id}")

                # 生成 TTS 音频 - 更新 status
                if sentence_obj.en:
                    sentence_obj.status = "generating_tts"
                    db.commit()
                    logger.info(f"[Regenerate] 开始生成 TTS: sentence_id={sentence_id}")
                    tts_result = await tts_service.generate_all_accents(
                        text=sentence_obj.en,
                        book_id=book.id,
                        sentence_id=sentence_obj.id,
                    )
                    if tts_result:
                        sentence_obj.audio_us_normal = tts_result.get("us_normal")
                        sentence_obj.audio_us_slow = tts_result.get("us_slow")
                        sentence_obj.audio_gb_normal = tts_result.get("gb_normal")
                        sentence_obj.audio_gb_slow = tts_result.get("gb_slow")
                        sentence_obj.status = "completed"
                        db.commit()
                        logger.info(f"[Regenerate] TTS 生成完成: sentence_id={sentence_id}")
                    else:
                        sentence_obj.status = "error"
                        db.commit()

            except Exception as e:
                logger.error(f"[Regenerate] 后台任务失败: {e}")
                try:
                    sentence_obj = db.query(Sentence).filter(Sentence.id == sentence_id).first()
                    if sentence_obj:
                        sentence_obj.status = "error"
                        db.commit()
                except:
                    pass
            finally:
                db.close()

        background_tasks.add_task(do_regenerate)

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

    当英文句子有变化时，会在后台异步翻译成中文并重新生成 TTS 音频。
    返回结果中 status=pending 表示正在后台处理。
    """
    sentence = await book_service.update_sentence(book_id, current_user["id"], sentence_id, sentence_data)

    # 如果状态为 pending，启动后台任务（只生成 TTS）
    if sentence["status"] == "pending" and sentence["en"]:
        async def do_regenerate():
            """后台任务：翻译 + 生成 TTS"""
            from app.core.database import SessionLocal
            from app.models.db_models import Sentence, Book, BookPage
            from app.services.translation_service import translation_service
            from app.services.tts_service import tts_service

            db = SessionLocal()
            try:
                sentence_obj = db.query(Sentence).filter(Sentence.id == sentence_id).first()
                if not sentence_obj:
                    return

                # 获取 book_id
                page = db.query(BookPage).filter(BookPage.id == sentence_obj.page_id).first()
                book = db.query(Book).filter(Book.id == page.book_id).first() if page else None
                if not book:
                    return

                # 翻译（如果没有中文）- 不改变 status
                if not sentence_obj.zh and sentence_obj.en:
                    logger.info(f"[Regenerate] 开始翻译: sentence_id={sentence_id}")
                    new_zh = await translation_service.translate_sentence(sentence_obj.en)
                    if new_zh:
                        sentence_obj.zh = new_zh
                        db.commit()
                        logger.info(f"[Regenerate] 翻译完成: sentence_id={sentence_id}")

                # 生成 TTS 音频 - 更新 status
                sentence_obj.status = "generating_tts"
                db.commit()
                logger.info(f"[Regenerate] 开始生成 TTS: sentence_id={sentence_id}")
                tts_result = await tts_service.generate_all_accents(
                    text=sentence_obj.en,
                    book_id=book.id,
                    sentence_id=sentence_obj.id,
                )
                if tts_result:
                    sentence_obj.audio_us_normal = tts_result.get("us_normal")
                    sentence_obj.audio_us_slow = tts_result.get("us_slow")
                    sentence_obj.audio_gb_normal = tts_result.get("gb_normal")
                    sentence_obj.audio_gb_slow = tts_result.get("gb_slow")
                    sentence_obj.status = "completed"
                    db.commit()
                    logger.info(f"[Regenerate] TTS 生成完成: sentence_id={sentence_id}")
                else:
                    sentence_obj.status = "error"
                    db.commit()

            except Exception as e:
                logger.error(f"[Regenerate] 后台任务失败: {e}")
                try:
                    sentence_obj = db.query(Sentence).filter(Sentence.id == sentence_id).first()
                    if sentence_obj:
                        sentence_obj.status = "error"
                        db.commit()
                except:
                    pass
            finally:
                db.close()

        background_tasks.add_task(do_regenerate)

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