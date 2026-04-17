#!/usr/bin/env python3
"""查询特定用户的绘本"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.db_models import User, Book, BookPage
from sqlalchemy import func


def query_user(user_id: int):
    """查询用户及其绘本"""
    db = SessionLocal()

    try:
        # 查找用户
        user = db.query(User).filter(User.id == user_id).first()

        if user:
            print(f"\n✓ 用户存在:")
            print(f"  ID: {user.id}")
            print(f"  姓名: {user.name}")
            print(f"  手机: {user.phone}")
            print(f"  wechat_open_id: {user.wechat_open_id}")
            print(f"  level: {user.level}")
            print(f"  books_read: {user.books_read}")
            print(f"  books_created: {user.books_created}")
            print(f"  stars: {user.stars}")
            print(f"  created_at: {user.created_at}")
        else:
            print(f"\n⚠️ 用户不存在: ID={user_id}")
            # 尝试搜索相近ID
            similar = db.query(User).filter(User.id.like(f'%{str(user_id)[:6]}%')).limit(5).all()
            if similar:
                print("相近ID的用户:")
                for u in similar:
                    print(f"  ID: {u.id} | 姓名: {u.name}")
            return

        # 查询用户的绘本
        print(f"\n【用户的绘本】")
        books = db.query(Book).filter(Book.user_id == user_id).order_by(Book.created_at.desc()).all()

        if books:
            print(f"共 {len(books)} 本绘本:")
            for book in books:
                pages_count = db.query(func.count(BookPage.id)).filter(BookPage.book_id == book.id).scalar() or 0
                print(f"  ID: {book.id} | 标题: {book.title} | 状态: {book.status} | share_type: {book.share_type} | 页数: {pages_count}")
        else:
            print("该用户没有绘本")

        # 检查 bookshelf 表
        print(f"\n【书架收藏】")
        from app.models.db_models import Bookshelf
        shelves = db.query(Bookshelf).filter(Bookshelf.user_id == user_id).all()
        if shelves:
            print(f"共收藏 {len(shelves)} 本绘本:")
            for shelf in shelves:
                book = db.query(Book).filter(Book.id == shelf.book_id).first()
                if book:
                    print(f"  book_id: {shelf.book_id} | 标题: {book.title}")
        else:
            print("书架为空")

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
    else:
        user_id = 166747893760

    query_user(user_id)