"""API routes for admin management."""
import hashlib
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.db_models import User, Book, SystemConfig, ReadingProgress
from app.models.schemas import (
    MessageResponse,
    AdminLoginRequest,
    AdminTokenResponse,
    AdminUserResponse,
    AdminUserListResponse,
    AdminBookListResponse,
    AdminBookDetailResponse,
    AdminStatsOverviewResponse,
    AdminBanRequest,
    SystemConfigUpdate,
    SystemConfigResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin"])
security = HTTPBearer()

# 硬编码管理员账户
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin777777"
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()


def verify_admin_token(token: str) -> bool:
    """验证管理员 JWT Token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("role") == "admin"
    except Exception:
        return False


async def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict:
    """获取当前管理员"""
    token = credentials.credentials
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="无效的管理员凭证")
    return {"username": ADMIN_USERNAME, "role": "admin"}


# ========================================
# 管理员认证
# ========================================

@router.post("/auth/login", response_model=AdminTokenResponse)
async def admin_login(request: AdminLoginRequest):
    """管理员登录"""
    if request.username != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 验证密码
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    if password_hash != ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 生成 JWT Token
    token_data = {
        "sub": ADMIN_USERNAME,
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    token = jwt.encode(token_data, settings.secret_key, algorithm="HS256")

    return AdminTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=86400,
    )


@router.post("/auth/logout", response_model=MessageResponse)
async def admin_logout():
    """管理员登出"""
    return MessageResponse(message="已退出登录")


@router.get("/auth/me", response_model=AdminUserResponse)
async def get_admin_info(admin: Annotated[dict, Depends(get_current_admin)]):
    """获取当前管理员信息"""
    return AdminUserResponse(
        username=admin["username"],
        role=admin["role"],
    )


# ========================================
# 用户管理
# ========================================

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_banned: Optional[bool] = Query(None),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取用户列表"""
    query = db.query(User)

    # 搜索
    if search:
        query = query.filter(
            (User.name.ilike(f"%{search}%")) |
            (User.phone.ilike(f"%{search}%"))
        )

    # 筛选封禁状态
    if is_banned is not None:
        query = query.filter(User.is_banned == is_banned)

    # 统计总数
    total = query.count()

    # 分页
    users = query.order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return AdminUserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        users=[
            AdminUserResponse.from_orm(user) for user in users
        ],
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user_detail(
    user_id: int,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取用户详情"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return AdminUserResponse.from_orm(user)


@router.put("/users/{user_id}/ban", response_model=MessageResponse)
async def ban_user(
    user_id: int,
    request: AdminBanRequest,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """封禁用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_banned = True
    user.banned_reason = request.reason
    db.commit()

    return MessageResponse(message=f"用户 {user.name} 已被封禁")


@router.put("/users/{user_id}/unban", response_model=MessageResponse)
async def unban_user(
    user_id: int,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """解封用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_banned = False
    user.banned_reason = None
    db.commit()

    return MessageResponse(message=f"用户 {user.name} 已解除封禁")


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """删除用户（级联删除关联数据）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()

    return MessageResponse(message="用户已删除")


# ========================================
# 绘本管理
# ========================================

@router.get("/books", response_model=AdminBookListResponse)
async def list_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取绘本列表"""
    query = db.query(Book)

    # 搜索
    if search:
        query = query.filter(Book.title.ilike(f"%{search}%"))

    # 筛选状态
    if status:
        query = query.filter(Book.status == status)

    # 统计总数
    total = query.count()

    # 分页，预加载用户信息
    books = query.order_by(desc(Book.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return AdminBookListResponse(
        total=total,
        page=page,
        page_size=page_size,
        books=[
            {
                "id": book.id,
                "title": book.title,
                "user_id": book.user_id,
                "user_name": book.user.name if book.user else None,
                "status": book.status,
                "progress": book.progress,
                "created_at": book.created_at.isoformat() if book.created_at else None,
            }
            for book in books
        ],
    )


@router.get("/books/{book_id}", response_model=AdminBookDetailResponse)
async def get_book_detail(
    book_id: int,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取绘本详情（包含 pages 和 sentences）"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    # 构建 pages 数据
    pages_data = []
    for page in (book.pages or []):
        sentences_data = []
        for sentence in (page.sentences or []):
            sentences_data.append({
                "id": sentence.id,
                "sentence_order": sentence.sentence_order,
                "en": sentence.en,
                "zh": sentence.zh,
                "audio_url": sentence.audio_url,
            })

        pages_data.append({
            "id": page.id,
            "page_number": page.page_number,
            "image_url": page.image_url,
            "sentences": sentences_data,
        })

    return AdminBookDetailResponse(
        id=book.id,
        title=book.title,
        user_id=book.user_id,
        user_name=book.user.name if book.user else None,
        status=book.status,
        progress=book.progress,
        level=book.level,
        has_audio=book.has_audio,
        cover_image=book.cover_image,
        created_at=book.created_at.isoformat() if book.created_at else None,
        pages=pages_data,
    )


@router.put("/books/{book_id}/status", response_model=MessageResponse)
async def update_book_status(
    book_id: int,
    status: str = Query(..., pattern="^(completed|error|draft)$"),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """更新绘本状态"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    book.status = status
    db.commit()

    return MessageResponse(message=f"绘本状态已更新为: {status}")


@router.delete("/books/{book_id}", response_model=MessageResponse)
async def delete_book(
    book_id: int,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """删除绘本"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    db.delete(book)
    db.commit()

    return MessageResponse(message="绘本已删除")


# ========================================
# 数据统计
# ========================================

@router.get("/stats/overview", response_model=AdminStatsOverviewResponse)
async def get_stats_overview(
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取数据总览"""
    # 用户总数
    total_users = db.query(func.count(User.id)).scalar()

    # 绘本总数
    total_books = db.query(func.count(Book.id)).scalar()

    # 今日新增用户
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    new_users_today = db.query(func.count(User.id)).filter(User.created_at >= today_start).scalar()

    # 今日新增绘本
    new_books_today = db.query(func.count(Book.id)).filter(Book.created_at >= today_start).scalar()

    # 今日阅读量
    readings_today = db.query(func.count(ReadingProgress.id)).filter(
        ReadingProgress.last_read_at >= today_start
    ).scalar()

    return AdminStatsOverviewResponse(
        total_users=total_users or 0,
        total_books=total_books or 0,
        new_users_today=new_users_today or 0,
        new_books_today=new_books_today or 0,
        readings_today=readings_today or 0,
    )


@router.get("/stats/users/daily")
async def get_daily_users_stats(
    days: int = Query(7, ge=1, le=30),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取每日新增用户统计"""
    result = []
    for i in range(days - 1, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())

        count = db.query(func.count(User.id)).filter(
            User.created_at >= day_start,
            User.created_at <= day_end
        ).scalar()

        result.append({
            "date": date.isoformat(),
            "count": count or 0,
        })

    return result


@router.get("/stats/books/daily")
async def get_daily_books_stats(
    days: int = Query(7, ge=1, le=30),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取每日新增绘本统计"""
    result = []
    for i in range(days - 1, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())

        count = db.query(func.count(Book.id)).filter(
            Book.created_at >= day_start,
            Book.created_at <= day_end
        ).scalar()

        result.append({
            "date": date.isoformat(),
            "count": count or 0,
        })

    return result


@router.get("/stats/reading/daily")
async def get_daily_reading_stats(
    days: int = Query(7, ge=1, le=30),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取每日阅读量统计"""
    result = []
    for i in range(days - 1, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())

        count = db.query(func.count(ReadingProgress.id)).filter(
            ReadingProgress.last_read_at >= day_start,
            ReadingProgress.last_read_at <= day_end
        ).scalar()

        result.append({
            "date": date.isoformat(),
            "count": count or 0,
        })

    return result


# ========================================
# 系统配置
# ========================================

@router.get("/configs", response_model=list[SystemConfigResponse])
async def list_configs(
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取所有系统配置"""
    configs = db.query(SystemConfig).all()
    return [
        SystemConfigResponse(
            key=config.key,
            value=config.value,
            description=config.description,
            updated_at=config.updated_at.isoformat() if config.updated_at else None,
        )
        for config in configs
    ]


@router.put("/configs/{key}", response_model=MessageResponse)
async def update_config(
    key: str,
    request: SystemConfigUpdate,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """更新系统配置"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config:
        config.value = request.value
    else:
        config = SystemConfig(key=key, value=request.value, description=request.description)
        db.add(config)

    db.commit()

    return MessageResponse(message="配置已更新")


# ========================================
# 排行榜管理
# ========================================

@router.get("/leaderboard/books")
async def list_leaderboard_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: str = Query("score", pattern="^(score|read_count|shelf_count|created_at)$"),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取排行榜绘本列表（含统计数据）"""
    query = db.query(Book).filter(
        Book.share_type == "public",
        Book.status == "completed",
    )

    # 搜索
    if search:
        query = query.filter(Book.title.ilike(f"%{search}%"))

    # 统计总数
    total = query.count()

    # 排序
    if sort_by == "score":
        query = query.order_by(desc(Book.read_count + Book.shelf_count * 2))
    elif sort_by == "read_count":
        query = query.order_by(desc(Book.read_count))
    elif sort_by == "shelf_count":
        query = query.order_by(desc(Book.shelf_count))
    else:
        query = query.order_by(desc(Book.created_at))

    # 分页
    books = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "books": [
            {
                "id": book.id,
                "title": book.title,
                "cover_image": book.cover_image,
                "level": book.level,
                "read_count": book.read_count,
                "shelf_count": book.shelf_count,
                "score": book.read_count + book.shelf_count * 2,
                "author_id": book.user_id,
                "author_name": book.user.name if book.user else "未知",
                "created_at": book.created_at.isoformat() if book.created_at else None,
            }
            for book in books
        ],
    }


@router.get("/leaderboard/authors")
async def list_leaderboard_authors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: str = Query("score", pattern="^(score|books_created|stars|created_at)$"),
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """获取排行榜作者列表（含统计数据）"""
    query = db.query(User).filter(
        User.is_active == True,
        User.is_banned == False,
    )

    # 搜索
    if search:
        query = query.filter(User.name.ilike(f"%{search}%"))

    # 统计总数
    total = query.count()

    # 子查询：计算每个用户的作品被收藏总数
    shelf_count_subquery = (
        db.query(
            Book.user_id,
            func.sum(Book.shelf_count).label("total_shelf_count"),
        )
        .filter(Book.share_type == "public")
        .group_by(Book.user_id)
        .subquery()
    )

    # 排序
    if sort_by == "score":
        query = query.order_by(desc(User.books_created))
    elif sort_by == "books_created":
        query = query.order_by(desc(User.books_created))
    elif sort_by == "stars":
        query = query.order_by(desc(User.stars))
    else:
        query = query.order_by(desc(User.created_at))

    # 分页
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "authors": [
            {
                "id": user.id,
                "name": user.name,
                "avatar": user.avatar,
                "level": user.level,
                "books_created": user.books_created,
                "stars": user.stars,
                "streak": user.streak,
                "total_shelf_count": db.query(func.sum(Book.shelf_count)).filter(
                    Book.user_id == user.id,
                    Book.share_type == "public",
                ).scalar() or 0,
                "score": user.books_created + (db.query(func.sum(Book.shelf_count)).filter(
                    Book.user_id == user.id,
                    Book.share_type == "public",
                ).scalar() or 0) * 3,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ],
    }


@router.put("/leaderboard/books/{book_id}/stats")
async def update_book_leaderboard_stats(
    book_id: int,
    read_count: Optional[int] = None,
    shelf_count: Optional[int] = None,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """更新绘本排行榜统计数据"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="绘本不存在")

    if read_count is not None:
        book.read_count = read_count
    if shelf_count is not None:
        book.shelf_count = shelf_count

    db.commit()

    return MessageResponse(message=f"绘本 '{book.title}' 统计数据已更新")


@router.put("/leaderboard/users/{user_id}/stats")
async def update_user_leaderboard_stats(
    user_id: int,
    books_created: Optional[int] = None,
    stars: Optional[int] = None,
    admin: Annotated[dict, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """更新用户排行榜统计数据"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if books_created is not None:
        user.books_created = books_created
    if stars is not None:
        user.stars = stars

    db.commit()

    return MessageResponse(message=f"用户 '{user.name}' 统计数据已更新")