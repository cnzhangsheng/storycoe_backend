"""API routes for book generation."""
import asyncio
import base64
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.schemas import MessageResponse
from app.services.file_storage_service import file_storage
from app.services.ocr_service import ocr_service, OcrSentence
from app.models.db_models import Book, BookPage, Sentence

router = APIRouter(prefix="/generate", tags=["Book Generation"])


@router.post("/book")
async def generate_book(
    title: str = Form(...),
    cover: UploadFile = File(None),
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成朗读绘本（带进度）。

    Args:
        title: 绘本标题
        cover: 封面图片（可选，单张）
        images: 上传的图片列表
        current_user: 当前用户
        db: 数据库会话

    Returns:
        StreamingResponse 带进度的响应
    """
    user_id = current_user["id"]

    async def generate_with_progress():
        """生成绘本并发送进度。"""
        total_steps = len(images) + 2  # 图片数 + 创建书籍 + 完成
        current_step = 0

        def progress_message(step: int, message: str, data: dict = None):
            """生成进度消息。"""
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
            # 步骤1: 创建书籍记录
            yield progress_message(current_step, "正在创建绘本...")

            book = Book(
                user_id=user_id,
                title=title,
                level=1,
                status="generating",
                is_new=True,
            )
            db.add(book)
            db.flush()  # 获取 book_id
            book_id = str(book.id)

            # 创建书籍目录
            file_storage.create_book_dir(book_id)

            # 保存封面图片
            cover_url = None
            if cover and cover.filename:
                cover_data = await cover.read()
                cover_path = file_storage.save_cover_image(
                    book_id=book_id,
                    image_data=cover_data,
                )
                cover_url = f"/static/{cover_path}"
                book.cover_image = cover_url
                logger.info(f"保存封面: book_id={book_id}, cover_url={cover_url}")

            current_step += 1
            yield progress_message(current_step, f"已创建绘本: {title}")

            # 步骤2: 读取并保存所有图片
            page_data_list = []  # 存储 (page, image_data) 用于后续 OCR

            for i, image_file in enumerate(images):
                # 读取图片数据
                image_data = await image_file.read()

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

                page_data_list.append((page, image_data))

            current_step += 1
            yield progress_message(current_step, f"正在识别 {len(images)} 张图片中的文字...")

            # 步骤3: 并行 OCR 识别所有图片
            logger.info(f"开始并行 OCR 识别: book_id={book_id}, pages={len(page_data_list)}")

            ocr_tasks = [
                ocr_service.recognize_image(image_data)
                for _, image_data in page_data_list
            ]
            ocr_results: List[List[OcrSentence]] = await asyncio.gather(*ocr_tasks)

            # 步骤4: 保存所有句子
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
            yield progress_message(
                current_step,
                f"已完成文字识别，共处理 {len(images)} 张图片",
            )

            # 步骤5: 完成
            book.status = "completed"
            book.has_audio = True
            db.commit()

            yield progress_message(
                total_steps,
                "绘本生成完成！",
                {
                    "book_id": book_id,
                    "title": title,
                    "total_pages": len(images),
                }
            )

            logger.info(f"绘本生成完成: book_id={book_id}, pages={len(images)}")

        except Exception as e:
            logger.error(f"生成绘本失败: {e}")
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