#!/usr/bin/env python3
"""数据库诊断脚本 - 检查绘本数据问题"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.db_models import User, Book, Bookshelf
from sqlalchemy import func


def diagnose():
    """诊断数据库问题"""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("数据库诊断报告")
        print("=" * 60)

        # 1. 检查用户表
        print("\n【用户表】")
        users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
        print(f"总用户数: {db.query(func.count(User.id)).scalar()}")
        for user in users:
            print(f"  ID: {user.id} (类型: {type(user.id).__name__}) | 姓名: {user.name} | 手机: {user.phone}")

        # 2. 检查绘本表
        print("\n【绘本表】")
        books = db.query(Book).order_by(Book.created_at.desc()).limit(10).all()
        total_books = db.query(func.count(Book.id)).scalar()
        print(f"总绘本数: {total_books}")
        for book in books:
            print(f"  ID: {book.id} | user_id: {book.user_id} | 标题: {book.title} | 状态: {book.status} | share_type: {book.share_type}")

        # 3. 检查 user_id 与实际用户的匹配
        print("\n【绘本作者匹配检查】")
        books_without_user = db.query(Book).filter(
            ~Book.user_id.in_(db.query(User.id))
        ).all()
        if books_without_user:
            print(f"⚠️ 发现 {len(books_without_user)} 本绘本的 user_id 不存在于用户表:")
            for book in books_without_user:
                print(f"  book_id: {book.id} | user_id: {book.user_id} | 标题: {book.title}")
        else:
            print("✓ 所有绘本的 user_id 都匹配用户表")

        # 4. 检查书架表
        print("\n【书架表】")
        shelves = db.query(Bookshelf).order_by(Bookshelf.created_at.desc()).limit(10).all()
        print(f"总收藏数: {db.query(func.count(Bookshelf.id)).scalar()}")
        for shelf in shelves:
            print(f"  user_id: {shelf.user_id} | book_id: {shelf.book_id}")

        # 5. 检查每个用户的绘本数量
        print("\n【用户绘本统计】")
        user_book_counts = db.query(
            User.id, User.name, func.count(Book.id).label('book_count')
        ).outerjoin(Book).group_by(User.id, User.name).order_by(User.created_at.desc()).limit(10).all()

        for user_id, name, count in user_book_counts:
            print(f"  用户 {name} (ID: {user_id}): {count} 本绘本")

        # 6. 检查 ID 格式
        print("\n【ID 格式检查】")
        sample_user = db.query(User).first()
        sample_book = db.query(Book).first()

        if sample_user:
            print(f"  用户 ID 示例: {sample_user.id} (长度: {len(str(sample_user.id))})")
        if sample_book:
            print(f"  绘本 ID 示例: {sample_book.id} (长度: {len(str(sample_book.id))})")

        # 7. 检查是否有空绘本（无页面）
        print("\n【空绘本检查】")
        from app.models.db_models import BookPage
        books_no_pages = db.query(Book).filter(
            ~Book.id.in_(db.query(BookPage.book_id))
        ).all()
        if books_no_pages:
            print(f"⚠️ 发现 {len(books_no_pages)} 本绘本没有页面:")
            for book in books_no_pages:
                print(f"  ID: {book.id} | 标题: {book.title}")
        else:
            print("✓ 所有绘本都有页面")

        print("\n" + "=" * 60)
        print("诊断完成")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    diagnose()