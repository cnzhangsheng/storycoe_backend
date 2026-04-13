"""Gamification service - 游戏化激励系统核心逻辑。

包含：
- 等级系统：计算等级、升级奖励
- 星星奖励：多场景星星获取规则
- 连续打卡：每日阅读更新连续天数
- 成就系统：达成目标解锁成就
- 每日任务：每日阅读任务和奖励
"""
from datetime import datetime, date, timezone
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.models.db_models import (
    User,
    Achievement,
    UserAchievement,
    DailyTask,
    LEVEL_CONFIG,
    DEFAULT_ACHIEVEMENTS,
    STAR_REWARDS,
)
from app.models.schemas import (
    AchievementResponse,
    AchievementListResponse,
    DailyTaskResponse,
    DailyTaskClaimResponse,
    GamificationStatsResponse,
    StarRewardResponse,
    StreakUpdateResponse,
)


def utcnow():
    """返回 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


def utcdate():
    """返回 UTC 时区的当前日期。"""
    return datetime.now(timezone.utc).date()


class GamificationService:
    """游戏化激励服务类。"""

    def __init__(self, db: Session):
        self.db = db

    # ========================================
    # 等级系统
    # ========================================

    def calculate_level(self, stars: int) -> int:
        """根据星星数计算等级。

        Args:
            stars: 用户当前星星数

        Returns:
            计算出的等级 (1-10)
        """
        for level in range(10, 0, -1):
            if stars >= LEVEL_CONFIG[level]["stars_required"]:
                return level
        return 1

    def get_level_info(self, level: int) -> dict:
        """获取等级信息。

        Args:
            level: 等级 (1-10)

        Returns:
            等级信息字典
        """
        return LEVEL_CONFIG.get(level, LEVEL_CONFIG[1])

    def check_level_up(self, user: User) -> dict:
        """检查并处理升级。

        Args:
            user: 用户对象

        Returns:
            升级信息字典，包含 level_up, new_level, reward 等
        """
        new_level = self.calculate_level(user.stars)

        if new_level > user.level:
            user.level = new_level
            reward = LEVEL_CONFIG[new_level]["reward"]
            user.stars += reward
            self.db.commit()
            logger.info(f"用户升级: user_id={user.id}, new_level={new_level}, reward={reward}")
            return {
                "level_up": True,
                "new_level": new_level,
                "reward": reward,
                "level_name": LEVEL_CONFIG[new_level]["name"],
                "title": LEVEL_CONFIG[new_level]["title"],
            }

        return {"level_up": False}

    def get_gamification_stats(self, user: User) -> GamificationStatsResponse:
        """获取用户游戏化统计数据。

        Args:
            user: 用户对象

        Returns:
            GamificationStatsResponse
        """
        level_info = LEVEL_CONFIG[user.level]
        next_level = user.level + 1 if user.level < 10 else 10

        # 计算当前等级进度
        current_required = level_info["stars_required"]
        next_required = LEVEL_CONFIG[next_level]["stars_required"]
        if next_required > current_required:
            progress = (user.stars - current_required) / (next_required - current_required) * 100
            progress = min(100, max(0, progress))
        else:
            progress = 100

        return GamificationStatsResponse(
            level=user.level,
            level_name=level_info["name"],
            stars=user.stars,
            streak=user.streak,
            books_read=user.books_read,
            total_sentences_read=user.total_sentences_read,
            next_level_stars=next_required,
            current_level_progress=round(progress, 1),
            title=level_info["title"],
        )

    # ========================================
    # 星星奖励
    # ========================================

    def add_stars(self, user: User, amount: int, reason: str) -> StarRewardResponse:
        """给用户添加星星。

        Args:
            user: 用户对象
            amount: 星星数量
            reason: 原因描述

        Returns:
            StarRewardResponse
        """
        user.stars += amount
        self.db.commit()

        # 检查升级
        level_up_info = self.check_level_up(user)

        # 检查成就
        achievements = self.check_achievements(user)

        logger.info(f"星星奖励: user_id={user.id}, amount={amount}, reason={reason}, total={user.stars}")

        return StarRewardResponse(
            stars_added=amount,
            reason=reason,
            total_stars=user.stars,
            level_up=level_up_info.get("level_up", False),
            new_level=level_up_info.get("new_level"),
            achievements_unlocked=achievements,
        )

    def reward_complete_book(self, user: User) -> StarRewardResponse:
        """奖励完成绘本阅读。

        Args:
            user: 用户对象

        Returns:
            StarRewardResponse
        """
        return self.add_stars(user, STAR_REWARDS["complete_book"], "完成绘本阅读")

    def reward_daily_first_read(self, user: User) -> StarRewardResponse:
        """奖励每日首次阅读。

        Args:
            user: 用户对象

        Returns:
            StarRewardResponse
        """
        return self.add_stars(user, STAR_REWARDS["daily_first_read"], "每日首次阅读")

    def reward_read_sentence(self, user: User) -> StarRewardResponse:
        """奖励朗读句子。

        Args:
            user: 用户对象

        Returns:
            StarRewardResponse
        """
        user.total_sentences_read += 1
        return self.add_stars(user, STAR_REWARDS["read_sentence"], "朗读句子")

    # ========================================
    # 连续打卡
    # ========================================

    def update_streak(self, user: User) -> StreakUpdateResponse:
        """更新连续阅读天数。

        Args:
            user: 用户对象

        Returns:
            StreakUpdateResponse
        """
        today = utcdate()

        if user.last_read_date is None:
            # 首次阅读
            user.streak = 1
            user.last_read_date = today
            self.db.commit()
            logger.info(f"开始连续打卡: user_id={user.id}, streak=1")
            return StreakUpdateResponse(
                streak=1,
                streak_started=True,
                streak_continued=False,
                streak_reset=False,
                stars_added=0,
            )

        last_date = user.last_read_date

        if today == last_date:
            # 当天已记录，不更新
            return StreakUpdateResponse(
                streak=user.streak,
                streak_started=False,
                streak_continued=False,
                streak_reset=False,
                stars_added=0,
            )

        days_diff = (today - last_date).days

        if days_diff == 1:
            # 连续阅读
            user.streak += 1
            user.last_read_date = today
            self.db.commit()

            # 连续打卡奖励
            streak_bonus = user.streak * STAR_REWARDS["streak_bonus_multiplier"]
            self.add_stars(user, streak_bonus, f"连续{user.streak}天打卡奖励")

            logger.info(f"连续打卡: user_id={user.id}, streak={user.streak}")
            return StreakUpdateResponse(
                streak=user.streak,
                streak_started=False,
                streak_continued=True,
                streak_reset=False,
                stars_added=streak_bonus,
            )

        elif days_diff > 1:
            # 断签，重新开始
            user.streak = 1
            user.last_read_date = today
            self.db.commit()
            logger.info(f"断签重置: user_id={user.id}, streak=1")
            return StreakUpdateResponse(
                streak=1,
                streak_started=False,
                streak_continued=False,
                streak_reset=True,
                stars_added=0,
            )

        return StreakUpdateResponse(
            streak=user.streak,
            streak_started=False,
            streak_continued=False,
            streak_reset=False,
            stars_added=0,
        )

    # ========================================
    # 成就系统
    # ========================================

    def init_default_achievements(self) -> None:
        """初始化默认成就数据。

        在数据库初始化时调用，确保成就表有预设数据。
        """
        for achievement_data in DEFAULT_ACHIEVEMENTS:
            existing = self.db.query(Achievement).filter(
                Achievement.code == achievement_data["code"]
            ).first()

            if not existing:
                achievement = Achievement(**achievement_data)
                self.db.add(achievement)
                logger.info(f"创建成就: {achievement_data['code']}")

        self.db.commit()

    def get_all_achievements(self, user_id: UUID) -> AchievementListResponse:
        """获取所有成就列表（包含用户解锁状态）。

        Args:
            user_id: 用户 ID

        Returns:
            AchievementListResponse
        """
        achievements = self.db.query(Achievement).order_by(Achievement.requirement_value).all()

        # 获取用户已解锁的成就
        user_achievements = self.db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id
        ).all()
        unlocked_ids = {ua.achievement_id for ua in user_achievements}
        unlocked_times = {ua.achievement_id: ua.unlocked_at for ua in user_achievements}

        achievement_responses = []
        for achievement in achievements:
            unlocked = achievement.id in unlocked_ids
            achievement_responses.append(AchievementResponse(
                id=achievement.id,
                code=achievement.code,
                name=achievement.name,
                description=achievement.description,
                icon=achievement.icon,
                requirement_type=achievement.requirement_type,
                requirement_value=achievement.requirement_value,
                reward_stars=achievement.reward_stars,
                unlocked=unlocked,
                unlocked_at=unlocked_times.get(achievement.id) if unlocked else None,
            ))

        return AchievementListResponse(
            achievements=achievement_responses,
            total_unlocked=len(unlocked_ids),
            total=len(achievements),
        )

    def check_achievements(self, user: User) -> list[AchievementResponse]:
        """检查并解锁成就。

        Args:
            user: 用户对象

        Returns:
            新解锁的成就列表
        """
        unlocked = []

        # 获取所有成就
        achievements = self.db.query(Achievement).all()

        for achievement in achievements:
            # 检查是否已解锁
            existing = self.db.query(UserAchievement).filter(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == achievement.id,
            ).first()

            if existing:
                continue

            # 检查条件
            if self._check_achievement_requirement(user, achievement):
                # 解锁成就
                user_achievement = UserAchievement(
                    user_id=user.id,
                    achievement_id=achievement.id,
                )
                self.db.add(user_achievement)

                # 奖励星星
                if achievement.reward_stars > 0:
                    user.stars += achievement.reward_stars

                unlocked.append(AchievementResponse(
                    id=achievement.id,
                    code=achievement.code,
                    name=achievement.name,
                    description=achievement.description,
                    icon=achievement.icon,
                    requirement_type=achievement.requirement_type,
                    requirement_value=achievement.requirement_value,
                    reward_stars=achievement.reward_stars,
                    unlocked=True,
                    unlocked_at=utcnow(),
                ))

                logger.info(f"解锁成就: user_id={user.id}, achievement={achievement.code}")

        if unlocked:
            self.db.commit()
            # 检查升级
            self.check_level_up(user)

        return unlocked

    def _check_achievement_requirement(self, user: User, achievement: Achievement) -> bool:
        """检查用户是否满足成就条件。

        Args:
            user: 用户对象
            achievement: 成就对象

        Returns:
            是否满足条件
        """
        requirement_type = achievement.requirement_type
        requirement_value = achievement.requirement_value

        if requirement_type == "books_read":
            return user.books_read >= requirement_value
        elif requirement_type == "streak":
            return user.streak >= requirement_value
        elif requirement_type == "level":
            return user.level >= requirement_value
        elif requirement_type == "stars":
            return user.stars >= requirement_value

        return False

    # ========================================
    # 每日任务
    # ========================================

    def get_or_create_daily_task(self, user: User) -> DailyTask:
        """获取或创建今日任务。

        Args:
            user: 用户对象

        Returns:
            DailyTask 对象
        """
        today = utcdate()

        task = self.db.query(DailyTask).filter(
            DailyTask.user_id == user.id,
            DailyTask.task_date == today,
        ).first()

        if not task:
            task = DailyTask(
                user_id=user.id,
                task_date=today,
                read_books=0,
                completed=False,
                reward_claimed=False,
            )
            self.db.add(task)
            self.db.commit()
            logger.info(f"创建每日任务: user_id={user.id}, date={today}")

        return task

    def get_daily_task_status(self, user: User) -> DailyTaskResponse:
        """获取每日任务状态。

        Args:
            user: 用户对象

        Returns:
            DailyTaskResponse
        """
        task = self.get_or_create_daily_task(user)

        target_books = 3
        progress_percent = min(100, round(task.read_books / target_books * 100, 1))

        return DailyTaskResponse(
            id=task.id,
            task_date=task.task_date,
            read_books=task.read_books,
            target_books=target_books,
            completed=task.completed,
            reward_claimed=task.reward_claimed,
            reward_stars=STAR_REWARDS["daily_task_complete"],
            progress_percent=progress_percent,
        )

    def update_daily_task_progress(self, user: User) -> DailyTaskResponse:
        """更新每日任务进度（读完一本书后调用）。

        Args:
            user: 用户对象

        Returns:
            DailyTaskResponse
        """
        task = self.get_or_create_daily_task(user)

        task.read_books += 1

        # 检查是否完成任务
        if task.read_books >= 3 and not task.completed:
            task.completed = True
            logger.info(f"每日任务完成: user_id={user.id}")

        self.db.commit()

        return self.get_daily_task_status(user)

    def claim_daily_task_reward(self, user: User) -> DailyTaskClaimResponse:
        """领取每日任务奖励。

        Args:
            user: 用户对象

        Returns:
            DailyTaskClaimResponse
        """
        task = self.get_or_create_daily_task(user)

        if not task.completed:
            return DailyTaskClaimResponse(
                success=False,
                reward_stars=0,
                message="任务尚未完成",
            )

        if task.reward_claimed:
            return DailyTaskClaimResponse(
                success=False,
                reward_stars=0,
                message="奖励已领取",
            )

        # 领取奖励
        task.reward_claimed = True
        reward = STAR_REWARDS["daily_task_complete"]
        user.stars += reward
        self.db.commit()

        # 检查升级和成就
        self.check_level_up(user)
        self.check_achievements(user)

        logger.info(f"领取每日任务奖励: user_id={user.id}, reward={reward}")

        return DailyTaskClaimResponse(
            success=True,
            reward_stars=reward,
            message=f"恭喜获得 {reward} 星星！",
        )

    # ========================================
    # 阅读触发奖励（整合方法）
    # ========================================

    def process_reading_completion(self, user: User, is_first_book_today: bool = False) -> StarRewardResponse:
        """处理绘本阅读完成后的所有游戏化奖励。

        Args:
            user: 用户对象
            is_first_book_today: 是否是今日第一本绘本

        Returns:
            StarRewardResponse 包含所有奖励信息
        """
        total_stars_added = 0
        reasons = []

        # 1. 完成绘本奖励
        complete_reward = STAR_REWARDS["complete_book"]
        total_stars_added += complete_reward
        reasons.append(f"完成绘本阅读({complete_reward})")

        # 2. 每日首次阅读奖励
        if is_first_book_today:
            daily_reward = STAR_REWARDS["daily_first_read"]
            total_stars_added += daily_reward
            reasons.append(f"每日首次阅读({daily_reward})")

        # 3. 更新连续打卡
        streak_response = self.update_streak(user)
        total_stars_added += streak_response.stars_added
        if streak_response.stars_added > 0:
            reasons.append(f"连续打卡奖励({streak_response.stars_added})")

        # 4. 更新每日任务
        self.update_daily_task_progress(user)

        # 5. 更新用户已读绘本数
        user.books_read += 1

        # 6. 统一添加星星（避免多次 commit）
        user.stars += total_stars_added
        self.db.commit()

        # 7. 检查升级
        level_up_info = self.check_level_up(user)

        # 8. 检查成就
        achievements = self.check_achievements(user)

        logger.info(f"阅读完成奖励: user_id={user.id}, stars_added={total_stars_added}, reasons={reasons}")

        return StarRewardResponse(
            stars_added=total_stars_added,
            reason=", ".join(reasons),
            total_stars=user.stars,
            level_up=level_up_info.get("level_up", False),
            new_level=level_up_info.get("new_level"),
            achievements_unlocked=achievements,
        )