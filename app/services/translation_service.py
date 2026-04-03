"""Translation service using Aliyun Bailian API (Qwen 3.5 Plus)."""
import httpx
from loguru import logger

from app.core.config import settings


class TranslationService:
    """翻译服务 - 使用阿里百炼平台 Qwen 3.5 Plus。

    用于将英文句子翻译成中文，适合儿童绘本阅读。
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
3. 如果有对话，保留引号
4. 只输出翻译结果，不要添加任何解释或说明

英文句子：
{en_text}

中文翻译：""",
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.3,  # 较低温度确保翻译稳定性
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
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

                # 清理返回内容（移除可能的前缀说明）
                translation = content.strip()

                # 移除可能的前缀
                if translation.startswith("中文翻译：") or translation.startswith("中文翻译:"):
                    translation = translation.split("：", 1)[-1].split(":", 1)[-1].strip()

                logger.info(f"翻译成功: '{en_text}' -> '{translation}'")
                return translation

        except Exception as e:
            logger.error(f"翻译失败: {e}")
            # 返回空字符串，不阻止更新操作
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

        # 批量翻译（合并为一个请求，提高效率）
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # 构建批量翻译提示
            sentences_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(en_texts)])

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""请将以下英文句子翻译成中文，按序号对应输出。

要求：
1. 翻译要准确、自然，适合儿童阅读
2. 保持原有的语气和风格
3. 每行一个翻译，格式为：序号. 中文翻译
4. 只输出翻译结果，不要添加任何解释

英文句子：
{sentences_text}

中文翻译：""",
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.3,
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    logger.error(f"批量翻译 API 调用失败: {response.status_code}")
                    # 降级为逐个翻译
                    return [await self.translate_sentence(text) for text in en_texts]

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # 解析返回的翻译列表
                translations = []
                for line in content.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # 移除序号前缀
                    if line and line[0].isdigit():
                        # 格式: "1. 翻译内容"
                        parts = line.split(".", 1)
                        if len(parts) > 1:
                            translations.append(parts[1].strip())
                        else:
                            translations.append(line)
                    else:
                        translations.append(line)

                # 确保返回数量与输入一致
                while len(translations) < len(en_texts):
                    translations.append(await self.translate_sentence(en_texts[len(translations)]))

                logger.info(f"批量翻译成功: {len(translations)} 个句子")
                return translations[:len(en_texts)]

        except Exception as e:
            logger.error(f"批量翻译失败: {e}")
            # 降级为逐个翻译
            return [await self.translate_sentence(text) for text in en_texts]


# 全局实例
translation_service = TranslationService()