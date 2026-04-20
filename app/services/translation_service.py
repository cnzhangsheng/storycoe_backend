"""Translation service using Aliyun Bailian API (Qwen 3.5 Plus)."""
import httpx
from loguru import logger

from app.core.config import settings


class TranslationService:
    """翻译服务 - 使用阿里百炼平台 Qwen 3.5 Plus。

    与 OCR 服务使用相同的大模型 API。
    """

    def __init__(self):
        """初始化翻译服务。"""
        self.api_key = settings.aliyun_api_key
        self.base_url = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
        self.model = "qwen3.5-plus"

    async def translate_sentence(self, en_text: str) -> str:
        """翻译英文句子为中文。

        Args:
            en_text: 英文句子

        Returns:
            中文翻译
        """
        if not en_text or not en_text.strip():
            return ""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""请将以下英文句子翻译成中文。

要求：
1. 翻译要准确、自然，适合儿童阅读
2. 保持原有的语气和风格
3. 只输出翻译结果，不要添加任何解释或说明

英文句子：
{en_text}

中文翻译：""",
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    logger.error(f"翻译 API 调用失败: {response.status_code} - {response.text}")
                    raise Exception(f"翻译 API 调用失败: {response.status_code}")

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                translation = content.strip()

                # 移除可能的前缀
                if translation.startswith("中文翻译：") or translation.startswith("中文翻译:"):
                    translation = translation.split("：", 1)[-1].split(":", 1)[-1].strip()

                logger.info(f"翻译成功: '{en_text}' -> '{translation}'")
                return translation

        except Exception as e:
            logger.error(f"翻译失败: {type(e).__name__} - {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return ""

    async def translate_sentences(self, en_texts: list[str]) -> list[str]:
        """批量翻译多个英文句子。

        Args:
            en_texts: 英文句子列表

        Returns:
            中文翻译列表
        """
        if not en_texts:
            return []

        # 逐个翻译（批量翻译容易出错）
        translations = []
        for text in en_texts:
            zh = await self.translate_sentence(text)
            translations.append(zh)

        return translations


# 全局实例
translation_service = TranslationService()