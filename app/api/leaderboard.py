"""排行榜 API 路由。

提供三种排行榜：
1. 热门绘本榜 - 按阅读数 + 收藏数综合排序
2. 新星绘本榜 - 近7天新发布的公开绘本
3. 活跃作者榜 - 按创作数 + 作品被收藏数排序
"""
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy import func, desc, and_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db_models import User, Book, Bookshelf
from app.models.schemas import (
    LeaderboardBookResponse,
    LeaderboardAuthorResponse,
    LeaderboardBookListResponse,
    LeaderboardAuthorListResponse,
)


router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


def utcnow():
    """返回 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


# ========================================
# 热门绘本榜
# ========================================

@router.get("/books/hot")
async def get_hot_books_leaderboard(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """热门绘本榜 - 综合阅读数 + 收藏数排序。

    排序权重：read_count * 1 + shelf_count * 2
    """
    # 查询公开且已完成的绘本
    query = db.query(Book).filter(
        Book.share_type == "public",
        Book.status == "completed",
    )

    # 计算综合分数并排序
    # score = read_count + shelf_count * 2 (收藏权重更高)
    books = query.order_by(
        desc(Book.read_count + Book.shelf_count * 2),
        desc(Book.created_at),
    ).limit(limit).all()

    total = query.count()

    leaderboard = []
    for rank, book in enumerate(books, start=1):
        leaderboard.append(LeaderboardBookResponse(
            id=book.id,
            title=book.title,
            cover_image=book.cover_image,
            level=book.level,
            read_count=book.read_count,
            shelf_count=book.shelf_count,
            author_id=book.user_id,
            author_name=book.user.name if book.user else "未知",
            author_avatar=book.user.avatar if book.user else None,
            rank=rank,
        ))

    logger.info(f"获取热门绘本榜: limit={limit}, results={len(leaderboard)}")

    return {
        "code": 0,
        "message": "success",
        "data": {
            "leaderboard_type": "hot",
            "books": [LeaderboardBookResponse.model_validate(b).model_dump() for b in leaderboard],
            "total": total,
        }
    }


# ========================================
# 新星绘本榜
# ========================================

@router.get("/books/new")
async def get_new_books_leaderboard(
    days: Annotated[int, Query(ge=1, le=30)] = 7,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """新星绘本榜 - 近N天新发布的公开绘本。

    按创建时间倒序排列。
    """
    # 计算起始时间
    start_date = utcnow() - timedelta(days=days)

    # 查询近N天新发布的公开绘本
    query = db.query(Book).filter(
        Book.share_type == "public",
        Book.status == "completed",
        Book.created_at >= start_date,
    )

    books = query.order_by(
        desc(Book.created_at),
    ).limit(limit).all()

    total = query.count()

    leaderboard = []
    for rank, book in enumerate(books, start=1):
        leaderboard.append(LeaderboardBookResponse(
            id=book.id,
            title=book.title,
            cover_image=book.cover_image,
            level=book.level,
            read_count=book.read_count,
            shelf_count=book.shelf_count,
            author_id=book.user_id,
            author_name=book.user.name if book.user else "未知",
            author_avatar=book.user.avatar if book.user else None,
            rank=rank,
        ))

    logger.info(f"获取新星绘本榜: days={days}, limit={limit}, results={len(leaderboard)}")

    return {
        "code": 0,
        "message": "success",
        "data": {
            "leaderboard_type": "new",
            "books": [LeaderboardBookResponse.model_validate(b).model_dump() for b in leaderboard],
            "total": total,
        }
    }


# ========================================
# 活跃作者榜
# ========================================

@router.get("/authors")
async def get_authors_leaderboard(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """活跃作者榜 - 按创作数 + 作品被收藏数排序。

    排序权重：books_created * 1 + total_shelf_count * 3
    """
    # 查询所有活跃用户（有创作绘本）
    query = db.query(User).filter(
        User.is_active == True,
        User.is_banned == False,
        User.books_created > 0,
    )

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

    # 联表查询
    users_with_shelf = (
        query
        .join(shelf_count_subquery, User.id == shelf_count_subquery.c.user_id, isouter=True)
        .add_columns(func.coalesce(shelf_count_subquery.c.total_shelf_count, 0).label("total_shelf"))
        .order_by(
            desc(User.books_created + func.coalesce(shelf_count_subquery.c.total_shelf_count, 0) * 3),
            desc(User.created_at),
        )
        .limit(limit)
        .all()
    )

    # 统计总数（有创作的用户）
    total = query.count()

    leaderboard = []
    for rank, row in enumerate(users_with_shelf, start=1):
        user = row[0]  # User 对象
        total_shelf = row[1] if len(row) > 1 else 0  # total_shelf_count

        leaderboard.append(LeaderboardAuthorResponse(
            id=user.id,
            name=user.name,
            avatar=user.avatar,
            level=user.level,
            books_created=user.books_created,
            total_shelf_count=total_shelf,
            rank=rank,
        ))

    # 如果上面的联表查询结果为空，使用简单查询
    if not leaderboard:
        users = query.order_by(
            desc(User.books_created),
            desc(User.stars),
        ).limit(limit).all()

        for rank, user in enumerate(users, start=1):
            # 计算用户作品的被收藏总数
            user_shelf_count = db.query(func.sum(Book.shelf_count)).filter(
                Book.user_id == user.id,
                Book.share_type == "public",
            ).scalar() or 0

            leaderboard.append(LeaderboardAuthorResponse(
                id=user.id,
                name=user.name,
                avatar=user.avatar,
                level=user.level,
                books_created=user.books_created,
                total_shelf_count=user_shelf_count,
                rank=rank,
            ))

    logger.info(f"获取活跃作者榜: limit={limit}, results={len(leaderboard)}")

    return {
        "code": 0,
        "message": "success",
        "data": {
            "authors": [LeaderboardAuthorResponse.model_validate(a).model_dump() for a in leaderboard],
            "total": total,
        }
    }


# ========================================
# 综合排行榜（一个接口返回多个榜单）
# ========================================

@router.get("/summary")
async def get_leaderboard_summary(
    db: Annotated[Session, Depends(get_db)] = None,
):
    """获取排行榜摘要 - 返回各榜单前3名。

    用于首页或探索页展示排行榜入口卡片。
    """
    # 热门绘本榜前3
    hot_books = db.query(Book).filter(
        Book.share_type == "public",
        Book.status == "completed",
    ).order_by(
        desc(Book.read_count + Book.shelf_count * 2),
    ).limit(3).all()

    # 新星绘本榜前3
    start_date = utcnow() - timedelta(days=7)
    new_books = db.query(Book).filter(
        Book.share_type == "public",
        Book.status == "completed",
        Book.created_at >= start_date,
    ).order_by(desc(Book.created_at)).limit(3).all()

    # 活跃作者榜前3
    authors = db.query(User).filter(
        User.is_active == True,
        User.is_banned == False,
        User.books_created > 0,
    ).order_by(desc(User.books_created)).limit(3).all()

    return {
        "hot_books": [
            {
                "id": b.id,
                "title": b.title,
                "cover_image": b.cover_image,
                "level": b.level,
                "read_count": b.read_count,
                "shelf_count": b.shelf_count,
                "author_id": b.user_id,
                "author_name": b.user.name if b.user else "未知",
                "author_avatar": b.user.avatar if b.user else None,
                "rank": rank + 1,
            }
            for rank, b in enumerate(hot_books)
        ],
        "new_books": [
            {
                "id": b.id,
                "title": b.title,
                "cover_image": b.cover_image,
                "level": b.level,
                "read_count": b.read_count,
                "shelf_count": b.shelf_count,
                "author_id": b.user_id,
                "author_name": b.user.name if b.user else "未知",
                "author_avatar": b.user.avatar if b.user else None,
                "rank": rank + 1,
            }
            for rank, b in enumerate(new_books)
        ],
        "authors": [
            {
                "id": a.id,
                "name": a.name,
                "avatar": a.avatar,
                "level": a.level,
                "books_created": a.books_created,
                "total_shelf_count": db.query(func.sum(Book.shelf_count)).filter(
                    Book.user_id == a.id,
                    Book.share_type == "public",
                ).scalar() or 0,
                "rank": rank + 1,
            }
            for rank, a in enumerate(authors)
        ],
    }