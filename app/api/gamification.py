"""API routes for gamification system.

游戏化激励系统 API：
- 用户统计
- 成就系统
- 每日任务
- 星星奖励记录
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.schemas import (
    GamificationStatsResponse,
    AchievementListResponse,
    DailyTaskResponse,
    DailyTaskClaimResponse,
    MessageResponse,
)
from app.services.gamification_service import GamificationService


router = APIRouter(prefix="/gamification", tags=["Gamification"])


def get_gamification_service(
    db: Annotated[Session, Depends(get_db)],
) -> GamificationService:
    """获取游戏化服务实例。"""
    return GamificationService(db)


# ========================================
# 用户统计
# ========================================


@router.get("/stats", response_model=GamificationStatsResponse)
async def get_gamification_stats(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    gamification_service: Annotated[GamificationService, Depends(get_gamification_service)],
):
    """获取用户游戏化统计数据。

    返回等级、星星、连续天数、已读绘本数等信息。
    """
    from app.models.db_models import User

    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        return GamificationStatsResponse(
            level=1,
            level_name="小读者",
            stars=0,
            streak=0,
            books_read=0,
            total_sentences_read=0,
            next_level_stars=100,
            current_level_progress=0,
            title="森林探索者",
        )

    return gamification_service.get_gamification_stats(user)


# ========================================
# 成就系统
# ========================================


@router.get("/achievements", response_model=AchievementListResponse)
async def get_achievements(
    current_user: Annotated[dict, Depends(get_current_user)],
    gamification_service: Annotated[GamificationService, Depends(get_gamification_service)],
):
    """获取所有成就列表（包含解锁状态）。"""
    return gamification_service.get_all_achievements(current_user["id"])


@router.get("/achievements/check", response_model=AchievementListResponse)
async def check_achievements(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    gamification_service: Annotated[GamificationService, Depends(get_gamification_service)],
):
    """检查并解锁成就。

    手动触发成就检查（通常阅读完成时自动触发）。
    """
    from app.models.db_models import User

    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        return AchievementListResponse(achievements=[], total_unlocked=0, total=0)

    # 检查成就
    gamification_service.check_achievements(user)

    return gamification_service.get_all_achievements(current_user["id"])


# ========================================
# 每日任务
# ========================================


@router.get("/daily-task", response_model=DailyTaskResponse)
async def get_daily_task(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    gamification_service: Annotated[GamificationService, Depends(get_gamification_service)],
):
    """获取今日任务状态。"""
    from app.models.db_models import User

    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        return DailyTaskResponse(
            id=None,
            task_date=None,
            read_books=0,
            target_books=3,
            completed=False,
            reward_claimed=False,
            reward_stars=20,
            progress_percent=0,
        )

    return gamification_service.get_daily_task_status(user)


@router.post("/daily-task/claim", response_model=DailyTaskClaimResponse)
async def claim_daily_task_reward(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    gamification_service: Annotated[GamificationService, Depends(get_gamification_service)],
):
    """领取每日任务奖励。

    只有完成任务且未领取时才能领取。
    """
    from app.models.db_models import User

    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        return DailyTaskClaimResponse(success=False, reward_stars=0, message="用户不存在")

    return gamification_service.claim_daily_task_reward(user)


# ========================================
# 初始化（仅用于管理员或开发）
# ========================================


@router.post("/init", response_model=MessageResponse)
async def init_achievements(
    gamification_service: Annotated[GamificationService, Depends(get_gamification_service)],
):
    """初始化默认成就数据。

    仅在数据库初始化时调用一次。
    """
    gamification_service.init_default_achievements()
    return MessageResponse(message="成就数据初始化完成")