#!/usr/bin/env python3
"""数据库诊断脚本 - 检查绘本数据问题"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.db_models import User, Book, Bookshelf, BookPage
from sqlalchemy import func


def diagnose(user_id=None):
    """诊断数据库问题"""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("数据库诊断报告")
        print("=" * 60)

        # 1. 检查用户表
        print("\n【用户表】")
        total_users = db.query(func.count(User.id)).scalar()
        print(f"总用户数: {total_users}")

        users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
        for user in users:
            print(f"  ID: {user.id} (类型: {type(user.id).__name__}, 长度: {len(str(user.id))})")
            print(f"      姓名: {user.name} | 手机: {user.phone} | wechat_open_id: {user.wechat_open_id}")

        # 2. 检查绘本表
        print("\n【绘本表】")
        total_books = db.query(func.count(Book.id)).scalar()
        print(f"总绘本数: {total_books}")

        books = db.query(Book).order_by(Book.created_at.desc()).limit(10).all()
        for book in books:
            pages_count = db.query(func.count(BookPage.id)).filter(BookPage.book_id == book.id).scalar() or 0
            print(f"  ID: {book.id} | user_id: {book.user_id} | 标题: {book.title[:20]}...")
            print(f"      状态: {book.status} | share_type: {book.share_type} | 页数: {pages_count}")

        # 3. 如果指定了用户ID，详细检查该用户
        if user_id:
            print(f"\n{'=' * 60}")
            print(f"【指定用户检查】user_id={user_id}")
            print("=" * 60)

            user = db.query(User).filter(User.id == user_id).first()
            if user:
                print(f"✓ 用户存在:")
                print(f"  ID: {user.id} (类型: {type(user.id).__name__})")
                print(f"  姓名: {user.name}")
                print(f"  手机: {user.phone}")
                print(f"  wechat_open_id: {user.wechat_open_id}")
                print(f"  books_created: {user.books_created}")
            else:
                print(f"⚠️ 用户不存在: ID={user_id}")
                # 搜索相近ID
                similar = db.query(User).filter(User.id == user_id).first()
                if not similar:
                    print("  注意: 该 ID 在数据库中不存在")
                return

            # 查询用户的绘本
            print(f"\n【用户绘本】")
            my_books = db.query(Book).filter(Book.user_id == user_id).order_by(Book.created_at.desc()).all()
            if my_books:
                print(f"共 {len(my_books)} 本绘本:")
                for book in my_books:
                    pages_count = db.query(func.count(BookPage.id)).filter(BookPage.book_id == book.id).scalar() or 0
                    print(f"  ID: {book.id} | 标题: {book.title} | 状态: {book.status} | 页数: {pages_count}")
            else:
                print("⚠️ 该用户没有绘本")
                # 检查是否有绘本的 user_id 与此用户相近
                print("\n  检查绘本表中的 user_id:")
                all_books = db.query(Book).limit(5).all()
                for b in all_books:
                    match = "✓ 匹配" if b.user_id == user_id else "✗ 不匹配"
                    print(f"    book.user_id={b.user_id} | {match}")

            # 检查书架
            print(f"\n【用户书架】")
            shelves = db.query(Bookshelf).filter(Bookshelf.user_id == user_id).all()
            if shelves:
                print(f"共收藏 {len(shelves)} 本绘本:")
                for shelf in shelves:
                    book = db.query(Book).filter(Book.id == shelf.book_id).first()
                    title = book.title if book else "绘本已删除"
                    print(f"  book_id: {shelf.book_id} | 标题: {title}")
            else:
                print("书架为空")

        # 4. ID 格式检查
        print(f"\n{'=' * 60}")
        print("【ID 格式统计】")
        print("=" * 60)

        sample_user = db.query(User).first()
        sample_book = db.query(Book).first()

        if sample_user:
            id_str = str(sample_user.id)
            print(f"用户 ID 示例: {sample_user.id}")
            print(f"  字符串形式: '{id_str}' (长度: {len(id_str)})")

        if sample_book:
            print(f"绘本 ID 示例: {sample_book.id}")
            print(f"  user_id: {sample_book.user_id}")

            # 检查 user_id 是否匹配用户表
            user_match = db.query(User).filter(User.id == sample_book.user_id).first()
            if user_match:
                print(f"  ✓ user_id 匹配用户: {user_match.name}")
            else:
                print(f"  ✗ user_id 不匹配任何用户!")

        # 5. 检查 user_id 类型匹配问题
        print(f"\n【类型匹配检查】")
        books_without_user = db.query(Book).filter(
            ~Book.user_id.in_(db.query(User.id))
        ).limit(10).all()

        if books_without_user:
            print(f"⚠️ 发现 {len(books_without_user)} 本绘本的 user_id 不存在于用户表!")
            for book in books_without_user:
                print(f"  book_id: {book.id} | user_id: {book.user_id} | 标题: {book.title[:20]}")
        else:
            print("✓ 所有绘本的 user_id 都匹配用户表")

        print("\n" + "=" * 60)
        print("诊断完成")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    user_id = None
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            print(f"无效的 user_id: {sys.argv[1]}")
            sys.exit(1)

    diagnose(user_id)