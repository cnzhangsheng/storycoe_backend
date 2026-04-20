"""API routes for book generation."""
import asyncio
import base64
import traceback
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.schemas import MessageResponse
from app.services.file_storage_service import file_storage
from app.services.ocr_service import ocr_service, OcrSentence
from app.services.tts_service import tts_service
from app.models.db_models import Book, BookPage, Sentence

router = APIRouter(prefix="/generate", tags=["Book Generation"])


# ============================================
# 图片上传接口
# ============================================


@router.post("/upload/image")
async def upload_single_image(
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """上传单张图片，返回图片 URL。

    用于小程序创作页面，先上传图片获取 URL，再调用生成绘本接口。

    Args:
        image: 图片文件

    Returns:
        {
            "url": "/static/uploads/xxx.jpg",
            "filename": "xxx.jpg"
        }
    """
    user_id = current_user["id"]
    logger.info(f"上传单张图片: user_id={user_id}, filename={image.filename}")

    try:
        # 读取图片数据
        image_data = await image.read()
        if not image_data:
            raise HTTPException(status_code=400, detail="图片数据为空")

        # 保存到临时目录
        import uuid
        import os
        from app.core.config import settings

        # 生成文件名
        ext = os.path.splitext(image.filename)[1] or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        relative_path = f"temp/{filename}"

        # 确保目录存在
        temp_dir = os.path.join(settings.upload_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)

        # 保存文件
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "wb") as f:
            f.write(image_data)

        url = f"/static/{relative_path}"
        logger.info(f"图片上传成功: {url}")

        return {
            "url": url,
            "filename": filename,
            "size": len(image_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


async def process_ocr_task(book_id: int, page_data_list: List[tuple]):
    """后台 OCR 处理任务。

    Args:
        book_id: 书籍 ID
        page_data_list: [(page_id, image_data), ...]
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        logger.info(f"开始后台 OCR 任务: book_id={book_id}, pages={len(page_data_list)}")

        # 获取书籍
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            logger.error(f"书籍不存在: book_id={book_id}")
            return

        # 更新状态为处理中
        book.status = "processing"
        db.commit()

        # 并行 OCR 识别所有图片
        logger.info(f"[OCR] 开始识别: {len(page_data_list)} 张图片")
        ocr_tasks = [
            ocr_service.recognize_image(image_data)
            for _, image_data in page_data_list
        ]
        ocr_results: List[List[OcrSentence]] = await asyncio.gather(*ocr_tasks, return_exceptions=True)

        # 保存所有句子并更新页面状态
        total_sentences = 0
        sentence_records = []  # 收集句子记录用于后续 TTS

        for idx, (page_id, _) in enumerate(page_data_list):
            result = ocr_results[idx]

            # 处理 OCR 异常
            if isinstance(result, Exception):
                logger.error(f"[OCR] OCR 失败: page_id={page_id}, error={result}")
                continue

            sentences = result
            logger.info(f"[OCR] OCR 结果: page_id={page_id}, sentences={len(sentences)}")

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
        logger.info(f"[OCR] 保存句子: {total_sentences} 个")

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

        # 更新书籍状态为完成
        book.status = "completed"
        book.has_audio = True
        db.commit()

        logger.info(f"后台 OCR 任务完成: book_id={book_id}")

    except Exception as e:
        logger.error(f"后台 OCR 任务失败: book_id={book_id}, error={e}\n{traceback.format_exc()}")
        # 更新书籍状态为错误
        try:
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                book.status = "error"
                db.commit()
        except:
            pass
    finally:
        db.close()


async def process_single_page_ocr(page_id: int, image_data: bytes):
    """后台 OCR 处理单个页面。

    Args:
        page_id: 页面 ID
        image_data: 图片数据
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        logger.info(f"开始单页 OCR 任务: page_id={page_id}")

        # 获取页面
        page = db.query(BookPage).filter(BookPage.id == page_id).first()
        if not page:
            logger.error(f"页面不存在: page_id={page_id}")
            return

        # 运行 OCR
        sentences = await ocr_service.recognize_image(image_data)

        # 保存句子并收集用于 TTS
        sentence_records = []
        for j, sentence in enumerate(sentences):
            if not sentence.en.strip():
                continue
            sentence_record = Sentence(
                page_id=page.id,
                sentence_order=j + 1,
                en=sentence.en.strip(),
                zh=sentence.zh.strip() if sentence.zh else "",
                status="pending",  # OCR 后需要生成 TTS
            )
            db.add(sentence_record)
            db.flush()  # 获取 sentence_id
            sentence_records.append(sentence_record)

        db.commit()
        logger.info(f"单页 OCR 保存句子: {len(sentence_records)} 个")

        # 并行生成所有句子的 TTS 音频
        if sentence_records:
            # 获取 book_id
            book = db.query(Book).filter(Book.id == page.book_id).first()
            if book:
                logger.info(f"[TTS] 开始生成音频: {len(sentence_records)} 个句子")

                # 更新所有句子状态为 generating_tts
                for sr in sentence_records:
                    sr.status = "generating_tts"
                db.commit()

                tts_tasks = [
                    tts_service.generate_all_accents(
                        text=sr.en,
                        book_id=book.id,
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

        # 更新页面状态为完成
        page.status = "completed"
        db.commit()

        logger.info(f"单页 OCR 任务完成: page_id={page_id}, sentences={len(sentences)}")

    except Exception as e:
        logger.error(f"单页 OCR 任务失败: page_id={page_id}, error={e}\n{traceback.format_exc()}")
        # 更新页面状态为错误
        try:
            page = db.query(BookPage).filter(BookPage.id == page_id).first()
            if page:
                page.status = "error"
                db.commit()
        except:
            pass
    finally:
        db.close()


@router.post("/book")
async def generate_book(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    cover: UploadFile = File(None),
    images: List[UploadFile] = File(...),
    share_type: str = Form("private"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传绘本图片并启动后台生成任务。

    这个接口会立即返回，OCR 识别在后台异步进行。
    用户可以通过轮询 /books/{book_id} 获取生成状态。

    Args:
        title: 绘本标题
        cover: 封面图片（可选，单张）
        images: 上传的图片列表
        share_type: 分享类型，public 或 private，默认 private
        current_user: 当前用户
        db: 数据库会话

    Returns:
        {
            "book_id": "xxx",
            "title": "xxx",
            "status": "processing",
            "message": "上传成功，正在后台识别文字..."
        }
    """
    user_id = current_user["id"]
    logger.info(f"上传绘本: user_id={user_id}, title={title}, images_count={len(images)}, share_type={share_type}")

    try:
        # 步骤1: 创建书籍记录
        book = Book(
            user_id=user_id,
            title=title,
            level=1,
            status="uploading",
            is_new=True,
            share_type=share_type,
        )
        db.add(book)
        db.flush()
        book_id = book.id  # 保持整数类型
        logger.info(f"创建书籍记录: book_id={book_id}")

        # 步骤2: 创建书籍目录
        file_storage.create_book_dir(book_id)

        # 步骤3: 保存封面图片
        cover_url = None
        if cover and cover.filename:
            try:
                cover_data = await cover.read()
                cover_path = file_storage.save_cover_image(
                    book_id=book_id,
                    image_data=cover_data,
                )
                cover_url = f"/static/{cover_path}"
                book.cover_image = cover_url
                logger.info(f"保存封面成功: {cover_url}")
            except Exception as e:
                logger.warning(f"保存封面失败: {e}")

        # 步骤4: 保存所有图片
        page_data_list = []  # 存储 (page_id, image_data) 用于后续 OCR

        for i, image_file in enumerate(images):
            image_data = await image_file.read()
            if not image_data:
                logger.warning(f"图片 {i+1} 数据为空，跳过")
                continue

            # 保存图片到文件系统
            relative_path = file_storage.save_page_image(
                book_id=book_id,
                page_number=i + 1,
                image_data=image_data,
            )
            image_url = f"/static/{relative_path}"

            # 创建页面记录
            page = BookPage(
                book_id=book.id,
                page_number=i + 1,
                image_url=image_url,
            )
            db.add(page)
            db.flush()

            page_data_list.append((page.id, image_data))
            logger.debug(f"保存图片 {i+1} 成功: {relative_path}")

        if not page_data_list:
            db.rollback()
            raise HTTPException(status_code=400, detail="没有有效的图片数据")

        # 提交数据库事务
        db.commit()

        logger.info(f"图片上传完成: book_id={book_id}, pages={len(page_data_list)}")

        # 步骤5: 启动后台 OCR 任务
        background_tasks.add_task(process_ocr_task, book_id, page_data_list)

        # 立即返回成功
        return {
            "book_id": book_id,
            "title": title,
            "status": "processing",
            "total_pages": len(page_data_list),
            "message": "上传成功，正在后台识别文字...",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传绘本失败: {e}\n{traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/book/sync", deprecated=True)
async def generate_book_sync(
    title: str = Form(...),
    cover: UploadFile = File(None),
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成朗读绘本（同步版本，已废弃）。

    ⚠️ 此接口已废弃，请使用 /generate/book 接口。

    保持此接口是为了向后兼容，但建议使用新的异步接口。
    """
    user_id = current_user["id"]
    logger.info(f"[已废弃] 同步生成绘本: user_id={user_id}, title={title}")

    async def generate_with_progress():
        """生成绘本并发送进度。"""
        total_steps = len(images) + 2
        current_step = 0

        def progress_message(step: int, message: str, data: dict = None):
            import json
            progress = int((step / total_steps) * 100)
            result = {
                "step": step,
                "total": total_steps,
                "progress": progress,
                "message": message,
            }
            if data:
                result["data"] = data
            return f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

        try:
            yield progress_message(current_step, "正在创建绘本...")

            book = Book(
                user_id=user_id,
                title=title,
                level=1,
                status="generating",
                is_new=True,
            )
            db.add(book)
            db.flush()
            book_id = book.id

            file_storage.create_book_dir(book_id)

            cover_url = None
            if cover and cover.filename:
                cover_data = await cover.read()
                cover_path = file_storage.save_cover_image(book_id=book_id, image_data=cover_data)
                cover_url = f"/static/{cover_path}"
                book.cover_image = cover_url

            current_step += 1
            yield progress_message(current_step, f"已创建绘本: {title}")

            page_data_list = []

            for i, image_file in enumerate(images):
                image_data = await image_file.read()
                if not image_data:
                    continue

                relative_path = file_storage.save_page_image(
                    book_id=book_id,
                    page_number=i + 1,
                    image_data=image_data,
                )
                image_url = f"/static/{relative_path}"

                page = BookPage(book_id=book.id, page_number=i + 1, image_url=image_url)
                db.add(page)
                db.flush()

                page_data_list.append((page, image_data))

            if not page_data_list:
                import json
                yield f"data: {json.dumps({'error': '没有有效的图片数据'}, ensure_ascii=False)}\n\n"
                return

            current_step += 1
            yield progress_message(current_step, f"正在识别 {len(page_data_list)} 张图片中的文字...")

            ocr_tasks = [
                ocr_service.recognize_image(image_data)
                for _, image_data in page_data_list
            ]
            ocr_results: List[List[OcrSentence]] = await asyncio.gather(*ocr_tasks)

            for idx, (page, _) in enumerate(page_data_list):
                sentences = ocr_results[idx]
                for j, sentence in enumerate(sentences):
                    sentence_record = Sentence(
                        page_id=page.id,
                        sentence_order=j + 1,
                        en=sentence.en,
                        zh=sentence.zh,
                    )
                    db.add(sentence_record)

            db.commit()

            current_step += 1
            yield progress_message(current_step, f"已完成文字识别，共处理 {len(page_data_list)} 张图片")

            book.status = "completed"
            book.has_audio = True
            db.commit()

            yield progress_message(
                total_steps,
                "绘本生成完成！",
                {"book_id": book_id, "title": title, "total_pages": len(page_data_list)}
            )

        except Exception as e:
            logger.error(f"生成绘本失败: {e}\n{traceback.format_exc()}")
            import json
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_with_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )