"""OCR service using Aliyun Bailian API (Qwen 3.5 Plus)."""
import base64
import re
from typing import List, Optional

import httpx
from loguru import logger

from app.core.config import settings


class OcrSentence:
    """OCR 识别的句子。"""

    def __init__(self, en: str, zh: str = ""):
        self.en = en
        self.zh = zh


class OcrService:
    """OCR 服务 - 使用阿里百炼平台 Qwen 3.5 Plus。

    阿里百炼 API 文档: https://help.aliyun.com/document_detail/2712195.html
    """

    def __init__(self):
        """初始化 OCR 服务。"""
        self.api_key = settings.aliyun_api_key
        self.base_url = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
        self.model = "qwen3.5-plus"  # 阿里百炼支持的模型名称

    async def recognize_image(self, image_data: bytes) -> List[OcrSentence]:
        """识别图片中的英文文字。

        Args:
            image_data: 图片字节数据

        Returns:
            识别的句子列表
        """
        try:
            # 将图片转为 base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")
            image_url = f"data:image/jpeg;base64,{image_base64}"

            # 调用阿里百炼 API
            sentences = await self._call_api(image_url)

            logger.info(f"OCR 识别完成，共 {len(sentences)} 个句子")
            return sentences

        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            raise

    async def _call_api(self, image_url: str) -> List[OcrSentence]:
        """调用阿里百炼 API。

        Args:
            image_url: 图片 URL（base64 格式）

        Returns:
            识别的句子列表（包含英文和中文翻译）
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                        {
                            "type": "text",
                            "text": """请仔细识别这张绘本图片中的所有英文文字，并将每个句子翻译成中文。

要求：
1. 只提取英文文字，忽略图片中已有的中文和其他语言
2. 按照句子顺序输出，每个句子后紧跟其中文翻译
3. 句子以 . ! ? 等标点符号结尾
4. 如果有对话，保留引号
5. 中文翻译要准确、自然，适合儿童阅读
6. 不要添加任何解释或说明

请严格按以下格式输出（每行一个句子）：
EN: 英文句子内容
ZH: 中文翻译内容
EN: 下一个英文句子
ZH: 下一个中文翻译
...

开始输出：""",
                        },
                    ],
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.1,  # 低温度确保稳定性
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"API 调用失败: {response.status_code} - {response.text}")
                raise Exception(f"API 调用失败: {response.status_code}")

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 解析返回的内容为句子列表
            sentences = self._parse_sentences(content)

            return sentences

    def _parse_sentences(self, text: str) -> List[OcrSentence]:
        """解析 API 返回的文本为句子列表（包含英文和中文）。

        Args:
            text: API 返回的文本

        Returns:
            句子列表（包含英文和中文翻译）
        """
        sentences = []

        # 按行分割
        lines = text.strip().split("\n")

        current_en = ""
        current_zh = ""

        for line in lines:
            line = line.strip()

            # 跳过空行和说明性文字
            if not line:
                continue
            if line.startswith("识别") or line.startswith("以下是") or line.startswith("图片中"):
                continue

            # 解析 EN: 开头的行（英文句子）
            if line.startswith("EN:") or line.startswith("EN ："):
                # 如果有上一个未完成的句子，先保存
                if current_en and current_zh:
                    sentences.append(OcrSentence(en=current_en, zh=current_zh))
                    current_en = ""
                    current_zh = ""
                # 提取英文句子
                en_content = re.sub(r"^EN[:\s：]+", "", line).strip()
                current_en = en_content

            # 解析 ZH: 开头的行（中文翻译）
            elif line.startswith("ZH:") or line.startswith("ZH ："):
                zh_content = re.sub(r"^ZH[:\s：]+", "", line).strip()
                current_zh = zh_content
                # 英文和中文配对完成，保存句子
                if current_en:
                    sentences.append(OcrSentence(en=current_en, zh=current_zh))
                    current_en = ""
                    current_zh = ""

            # 如果不是 EN/ZH 格式，可能是旧格式或其他格式
            elif len(line) >= 3:
                # 移除行号
                line = re.sub(r"^\d+[\.\)、\s]+", "", line)
                line = line.strip()

                if line and not line.startswith("EN") and not line.startswith("ZH"):
                    # 尝试作为纯英文句子处理（兼容旧格式）
                    sentences.append(OcrSentence(en=line, zh=""))

        # 处理最后一个未配对的句子
        if current_en:
            sentences.append(OcrSentence(en=current_en, zh=current_zh if current_zh else ""))

        # 如果没有成功解析任何句子，尝试备用解析方式
        if not sentences:
            # 使用正则表达式按句子分割
            pattern = r'[^.!?]*[.!?]'
            matches = re.findall(pattern, text)

            for match in matches:
                sentence = match.strip()
                if sentence and len(sentence) > 2:
                    sentences.append(OcrSentence(en=sentence, zh=""))

        logger.debug(f"解析句子: {len(sentences)} 个, 内容: {[{'en': s.en, 'zh': s.zh} for s in sentences[:3]]}")
        return sentences


# 全局实例
ocr_service = OcrService()


async def translate_text(text: str) -> str:
    """翻译英文文本为中文。

    Args:
        text: 英文文本

    Returns:
        中文翻译
    """
    if not text or not text.strip():
        return ""

    try:
        headers = {
            "Authorization": f"Bearer {settings.aliyun_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "qwen3.5-plus",
            "messages": [
                {
                    "role": "user",
                    "content": f"""请将以下英文翻译成中文。要求：
1. 翻译准确、自然，适合儿童阅读
2. 只输出中文翻译，不要添加任何解释或说明

英文原文：
{text}

中文翻译：""",
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"翻译 API 调用失败: {response.status_code}")
                return ""

            result = response.json()
            translation = result["choices"][0]["message"]["content"].strip()
            logger.info(f"翻译完成: {text[:30]}... -> {translation[:30]}...")
            return translation

    except Exception as e:
        logger.error(f"翻译失败: {e}")
        return ""