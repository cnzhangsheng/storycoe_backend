"""Authentication service using SQLAlchemy."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger
from jose import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    CodeExpiredException,
    CodeInvalidException,
    CodeUsedException,
    AuthenticationException,
)
from app.models.schemas import UserResponse
from app.models.db_models import User, UserSettings, VerificationCode


def utcnow():
    """返回 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AuthService:
    """认证服务类。

    封装所有认证相关的业务逻辑和数据库操作。
    """

    def __init__(self, db: Session):
        """初始化服务。

        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db

    def create_access_token(self, user_id: str) -> str:
        """创建 JWT 访问令牌。

        Args:
            user_id: 用户 ID

        Returns:
            JWT 令牌字符串
        """
        expire = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode = {"sub": str(user_id), "exp": expire}
        token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        logger.info(f"创建访问令牌: user_id={user_id}")
        return token

    def send_verification_code(self, phone: str) -> str:
        """发送验证码。

        Args:
            phone: 手机号

        Returns:
            发送结果消息
        """
        # 使用固定验证码 123456（暂不接入外部短信服务）
        code = "123456"
        expires_at = utcnow() + timedelta(minutes=5)

        # 删除该手机号的旧验证码
        self.db.query(VerificationCode).filter(VerificationCode.phone == phone).delete()
        logger.debug(f"删除旧验证码: phone={phone}")

        # 存储新验证码
        new_code = VerificationCode(
            phone=phone,
            code=code,
            expires_at=expires_at,
        )
        self.db.add(new_code)
        self.db.commit()
        logger.info(f"发送验证码: phone={phone}, code={code}")

        return "验证码已发送"

    def verify_code(self, phone: str, code: str) -> dict:
        """验证码校验并登录/注册。

        Args:
            phone: 手机号
            code: 验证码

        Returns:
            用户信息和访问令牌

        Raises:
            CodeInvalidException: 验证码错误
            CodeExpiredException: 验证码过期
            CodeUsedException: 验证码已使用
        """
        # 查询验证码记录
        code_record = self.db.query(VerificationCode).filter(
            VerificationCode.phone == phone,
            VerificationCode.code == code,
        ).first()

        if not code_record:
            logger.warning(f"验证码错误: phone={phone}, code={code}")
            raise CodeInvalidException()

        # 检查是否过期
        if utcnow() > code_record.expires_at:
            logger.warning(f"验证码过期: phone={phone}")
            raise CodeExpiredException()

        # 检查是否已使用
        if code_record.used:
            logger.warning(f"验证码已使用: phone={phone}")
            raise CodeUsedException()

        # 标记验证码为已使用
        code_record.used = True
        self.db.commit()
        logger.debug(f"标记验证码已使用: id={code_record.id}")

        # 查找或创建用户
        user = self._find_or_create_user(phone)

        # 创建访问令牌
        access_token = self.create_access_token(str(user.id))

        logger.info(f"用户登录成功: user_id={user.id}, phone={phone}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse(
                id=user.id,
                name=user.name,
                avatar=user.avatar,
                level=user.level,
                books_read=user.books_read,
                stars=user.stars,
                streak=user.streak,
                created_at=user.created_at,
                updated_at=user.updated_at,
            ),
        }

    def _find_or_create_user(self, phone: str) -> User:
        """查找或创建用户。

        Args:
            phone: 手机号

        Returns:
            用户对象
        """
        user = self.db.query(User).filter(User.phone == phone).first()

        if user:
            logger.debug(f"找到已有用户: user_id={user.id}")
            return user

        # 创建新用户
        new_user = User(
            phone=phone,
            name="小读者",
            level=1,
            books_read=0,
            stars=0,
            streak=0,
        )
        self.db.add(new_user)
        self.db.flush()  # 获取 ID
        logger.info(f"创建新用户: user_id={new_user.id}, phone={phone}")

        # 创建默认用户设置
        user_settings = UserSettings(
            user_id=new_user.id,
            speed_label="中",
            accent="US",
            loop_enabled=False,
        )
        self.db.add(user_settings)
        self.db.commit()
        logger.debug(f"创建用户默认设置: user_id={new_user.id}")

        return new_user

    def get_current_user(self, user_id: int) -> dict:
        """根据用户 ID 获取当前用户。

        Args:
            user_id: 用户 ID（整数）

        Returns:
            用户数据字典

        Raises:
            AuthenticationException: 用户不存在
        """
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            logger.warning(f"用户不存在: user_id={user_id}")
            raise AuthenticationException(message="用户不存在")

        return {
            "id": user.id,
            "name": user.name,
            "avatar": user.avatar,
            "phone": user.phone,
            "level": user.level,
            "books_read": user.books_read,
            "stars": user.stars,
            "streak": user.streak,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def validate_token(self, token: str) -> int:
        """验证 JWT 令牌并返回用户 ID。

        Args:
            token: JWT 令牌

        Returns:
            用户 ID (int)

        Raises:
            AuthenticationException: 令牌无效
        """
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                raise AuthenticationException(message="令牌无效")
            return int(user_id)
        except jwt.JWTError as e:
            logger.warning(f"JWT 解析失败: {e}")
            raise AuthenticationException(message="令牌无效或已过期")