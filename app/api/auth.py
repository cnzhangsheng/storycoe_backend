"""API routes for authentication."""
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.models.schemas import (
    SendCodeRequest,
    VerifyCodeRequest,
    TokenResponse,
    UserResponse,
    MessageResponse,
)
from app.services import get_auth_service
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


class WechatLoginRequest(BaseModel):
    """微信登录请求。"""
    code: str


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
    result = await auth_service.wechat_login(request.code)
    return WechatLoginResponse(
        token=result["access_token"],
        user=result["user"],
    )


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