"""Reading progress service using SQLAlchemy."""
from datetime import datetime, timezone, date

from loguru import logger
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.schemas import ReadingProgressUpdate, ReadingProgressResponse, MessageResponse
from app.models.db_models import User, Book, ReadingProgress, DailyTask


def utcnow():
    """返回 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


def utcdate():
    """返回 UTC 时区的当前日期。"""
    return datetime.now(timezone.utc).date()


class ReadingService:
    """阅读进度服务类。

    封装所有阅读进度相关的业务逻辑和数据库操作。
    """

    def __init__(self, db: Session):
        """初始化服务。

        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db

    def get_reading_progress(self, user_id: int, book_id: int) -> ReadingProgressResponse:
        """获取阅读进度。

        Args:
            user_id: 用户 ID（整数）
            book_id: 书籍 ID（整数）

        Returns:
            阅读进度数据
        """
        progress = self.db.query(ReadingProgress).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.book_id == book_id,
        ).first()

        if not progress:
            # 返回默认进度
            logger.debug(f"阅读进度不存在，返回默认: user_id={user_id}, book_id={book_id}")
            return ReadingProgressResponse(
                id=None,
                user_id=user_id,
                book_id=book_id,
                current_page=0,
                total_pages=0,
                completed=False,
                last_read_at=utcnow(),
                created_at=utcnow(),
                updated_at=utcnow(),
            )

        return ReadingProgressResponse(
            id=progress.id,
            user_id=progress.user_id,
            book_id=progress.book_id,
            current_page=progress.current_page,
            total_pages=progress.total_pages,
            completed=progress.completed,
            last_read_at=progress.last_read_at,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )

    def update_reading_progress(
        self,
        user_id: int,
        book_id: int,
        update_data: ReadingProgressUpdate,
        current_books_read: int,
    ) -> ReadingProgressResponse:
        """更新阅读进度。

        Args:
            user_id: 用户 ID（整数）
            book_id: 书籍 ID（整数）
            update_data: 更新数据
            current_books_read: 当前已读书籍数

        Returns:
            更新后的阅读进度
        """
        progress = self.db.query(ReadingProgress).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.book_id == book_id,
        ).first()

        now = utcnow()

        if progress:
            # 更新已有进度
            if update_data.current_page is not None:
                progress.current_page = update_data.current_page
            if update_data.completed is not None:
                progress.completed = update_data.completed
            progress.last_read_at = now
            logger.info(f"更新阅读进度: user_id={user_id}, book_id={book_id}")
        else:
            # 创建新进度
            progress = ReadingProgress(
                user_id=user_id,
                book_id=book_id,
                current_page=update_data.current_page or 0,
                completed=update_data.completed or False,
                last_read_at=now,
            )
            self.db.add(progress)
            logger.info(f"创建阅读进度: user_id={user_id}, book_id={book_id}")

            # 标记书籍为已读（非新书）
            book = self.db.query(Book).filter(Book.id == book_id).first()
            if book:
                book.is_new = False

        self.db.commit()
        self.db.refresh(progress)

        # 如果完成阅读，更新用户统计
        if update_data.completed:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user.books_read = current_books_read + 1
                self.db.commit()
                logger.info(f"完成阅读，更新用户统计: user_id={user_id}")

        return ReadingProgressResponse(
            id=progress.id,
            user_id=progress.user_id,
            book_id=progress.book_id,
            current_page=progress.current_page,
            total_pages=progress.total_pages,
            completed=progress.completed,
            last_read_at=progress.last_read_at,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )

    def mark_book_completed(self, user_id: int, book_id: int, current_books_read: int) -> MessageResponse:
        """标记书籍为已完成，并触发游戏化奖励。

        Args:
            user_id: 用户 ID（整数）
            book_id: 书籍 ID（整数）
            current_books_read: 当前已读书籍数

        Returns:
            成功消息（包含奖励信息）

        Raises:
            NotFoundException: 书籍不存在
        """
        # 校验书籍存在性和权限
        book = self.db.query(Book).filter(Book.id == book_id).first()

        if not book:
            logger.warning(f"书籍不存在: book_id={book_id}, user_id={user_id}")
            raise NotFoundException(message="书籍未找到")

        # 更新或创建进度
        progress = self.db.query(ReadingProgress).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.book_id == book_id,
        ).first()

        now = utcnow()
        today = utcdate()

        if progress:
            # 如果已经完成过，不重复奖励
            if progress.completed:
                return MessageResponse(message="这本绘本已经读过了哦~")
            progress.completed = True
            progress.last_read_at = now
        else:
            progress = ReadingProgress(
                user_id=user_id,
                book_id=book_id,
                completed=True,
                current_page=0,
                total_pages=0,
                last_read_at=now,
            )
            self.db.add(progress)
            # 新用户首次阅读，增加绘本阅读次数（排行榜统计）
            book.read_count += 1
            logger.debug(f"更新绘本阅读数: book_id={book_id}, read_count={book.read_count}")

        # 更新用户统计
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.books_read = current_books_read + 1

            # 检查是否是今日首次阅读这本书
            is_first_book_today = self._check_first_book_today(user_id, today)

            # 触发游戏化奖励
            reward_message = self._process_gamification_rewards(user, is_first_book_today)

        # 标记书籍为非新书
        book.is_new = False

        self.db.commit()
        logger.info(f"标记书籍完成: user_id={user_id}, book_id={book_id}")

        return MessageResponse(message=f"恭喜完成阅读！{reward_message}")

    def _check_first_book_today(self, user_id: int, today: date) -> bool:
        """检查是否是今日第一本完成的绘本。

        Args:
            user_id: 用户 ID（整数）
            today: 今日日期

        Returns:
            是否是今日第一本
        """
        # 检查今日是否有其他已完成的阅读记录
        today_completions = self.db.query(ReadingProgress).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.completed == True,
        ).count()

        # 如果是第一本，返回 True
        # 这里我们用已读绘本数来判断，如果当前为0则认为是第一本
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.books_read == 0:
            return True

        return False

    def _process_gamification_rewards(self, user: User, is_first_book_today: bool) -> str:
        """处理游戏化奖励。

        Args:
            user: 用户对象
            is_first_book_today: 是否是今日第一本绘本

        Returns:
            奖励描述消息
        """
        from app.services.gamification_service import GamificationService, STAR_REWARDS

        gamification_service = GamificationService(self.db)

        total_stars = 0
        rewards = []

        # 1. 完成绘本奖励
        complete_reward = STAR_REWARDS["complete_book"]
        total_stars += complete_reward
        rewards.append(f"获得{complete_reward}星星")

        # 2. 每日首次阅读奖励（简化判断：基于 last_read_date）
        today = utcdate()
        if user.last_read_date is None or user.last_read_date < today:
            daily_reward = STAR_REWARDS["daily_first_read"]
            total_stars += daily_reward
            rewards.append(f"每日首次阅读+{daily_reward}星星")

        # 3. 更新连续打卡
        streak_info = gamification_service.update_streak(user)
        if streak_info.stars_added > 0:
            total_stars += streak_info.stars_added
            rewards.append(f"连续{streak_info.streak}天打卡+{streak_info.stars_added}星星")

        # 4. 更新每日任务进度
        task_status = gamification_service.update_daily_task_progress(user)
        if task_status.completed and not task_status.reward_claimed:
            rewards.append(f"每日任务完成！可领取{task_status.reward_stars}星星")

        # 5. 添加星星
        user.stars += total_stars
        self.db.flush()

        # 6. 检查升级
        level_up_info = gamification_service.check_level_up(user)
        if level_up_info.get("level_up"):
            rewards.append(f"升级到Lv.{level_up_info['new_level']}！获得{level_up_info['reward']}星星")

        # 7. 检查成就
        achievements = gamification_service.check_achievements(user)
        for achievement in achievements:
            rewards.append(f"解锁成就「{achievement.name}」！")

        logger.info(f"游戏化奖励: user_id={user.id}, total_stars={total_stars}")

        if rewards:
            return " " + "、".join(rewards)
        return ""