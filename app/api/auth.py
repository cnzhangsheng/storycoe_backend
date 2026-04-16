"""API routes for authentication."""
import httpx
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.core.database import SessionLocal
from app.models.db_models import User
from app.models.schemas import (
    SendCodeRequest,
    VerifyCodeRequest,
    TokenResponse,
    UserResponse,
    MessageResponse,
)
from app.services import get_auth_service
from app.services.auth_service import AuthService
from app.utils.snowflake import snowflake_id

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


# 微信登录请求模型
class WechatLoginRequest(BaseModel):
    """微信登录请求。"""
    code: str


# 微信登录响应模型
class WechatLoginResponse(BaseModel):
    """微信登录响应。"""
    token: str
    user: UserResponse


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    """Get current user from JWT token."""
    user_id = auth_service.validate_token(credentials.credentials)
    return auth_service.get_current_user(user_id)


@router.post("/wechat-login", response_model=WechatLoginResponse)
async def wechat_login(
    request: WechatLoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """微信小程序登录。

    通过微信 code 获取 openid，创建或获取用户，返回 JWT token。
    """
    # 微信小程序 AppID 和 AppSecret（需要配置）
    appid = getattr(settings, 'wechat_appid', None) or getattr(settings, 'WECHAT_APPID', None)
    secret = getattr(settings, 'wechat_secret', None) or getattr(settings, 'WECHAT_SECRET', None)

    # 如果没有配置微信 AppID/Secret，使用测试模式
    if not appid or not secret:
        logger.info("[WechatLogin] 测试模式: 未配置微信 AppID/Secret")
        db = SessionLocal()
        try:
            # 生成测试 open_id
            test_open_id = f"test_openid_{request.code[:8]}"

            # 查找或创建测试用户（通过 wechat_open_id）
            test_user = db.query(User).filter(User.wechat_open_id == test_open_id).first()
            if not test_user:
                test_user = User(
                    wechat_open_id=test_open_id,
                    phone=None,
                    name='测试用户',
                    level=1,
                    books_read=0,
                    stars=0,
                    streak=0,
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
                logger.info(f"[WechatLogin] 创建测试用户: id={test_user.id}, open_id={test_open_id}")
            else:
                logger.info(f"[WechatLogin] 找到已有测试用户: id={test_user.id}, open_id={test_open_id}")

            # 生成 JWT token
            token = auth_service.create_access_token(str(test_user.id))

            return WechatLoginResponse(
                token=token,
                user=UserResponse(
                    id=test_user.id,
                    name=test_user.name,
                    avatar=test_user.avatar,
                    level=test_user.level,
                    books_read=test_user.books_read,
                    stars=test_user.stars,
                    streak=test_user.streak,
                    created_at=test_user.created_at,
                    updated_at=test_user.updated_at,
                )
            )
        finally:
            db.close()

    # 正常模式：调用微信 API 获取 open_id
    logger.info(f"[WechatLogin] 正常模式: 调用微信 API, appid={appid}")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            'https://api.weixin.qq.com/sns/jscode2session',
            params={
                'appid': appid,
                'secret': secret,
                'js_code': request.code,
                'grant_type': 'authorization_code',
            },
            timeout=10.0,
        )
        data = resp.json()
        logger.info(f"[WechatLogin] 微信 API 返回: {data}")

        if 'errcode' in data and data['errcode'] != 0:
            logger.error(f"[WechatLogin] 微信 API 错误: {data}")
            raise AuthenticationException(
                message=f"微信登录失败: {data.get('errmsg', '未知错误')}"
            )

        openid = data.get('openid')
        if not openid:
            logger.error(f"[WechatLogin] 未获取到 openid")
            raise AuthenticationException(message="微信登录失败: 未获取到 openid")

        # 查找或创建用户（通过 wechat_open_id）
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.wechat_open_id == openid).first()
            if not user:
                user = User(
                    wechat_open_id=openid,
                    phone=None,
                    name='微信用户',
                    level=1,
                    books_read=0,
                    stars=0,
                    streak=0,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"[WechatLogin] 创建新用户: id={user.id}, open_id={openid}")
            else:
                logger.info(f"[WechatLogin] 找到已有用户: id={user.id}, open_id={openid}")

            # 生成 JWT token
            token = auth_service.create_access_token(str(user.id))

            return WechatLoginResponse(
                token=token,
                user=UserResponse(
                    id=user.id,
                    name=user.name,
                    avatar=user.avatar,
                    level=user.level,
                    books_read=user.books_read,
                    stars=user.stars,
                    streak=user.streak,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )
        finally:
            db.close()


@router.post("/send-code", response_model=MessageResponse)
async def send_verification_code(
    request: SendCodeRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Send verification code to phone number."""
    message = auth_service.send_verification_code(request.phone)
    return MessageResponse(message=message)


@router.post("/verify", response_model=TokenResponse)
async def verify_code_and_login(
    request: VerifyCodeRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Verify code and login/register user."""
    return auth_service.verify_code(request.phone, request.code)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current user information."""
    return UserResponse(**current_user)


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """Logout user (client should discard token)."""
    return MessageResponse(message="已退出登录")