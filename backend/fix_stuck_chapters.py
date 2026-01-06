#!/usr/bin/env python3
"""修复卡在 generating 状态的章节"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.novel import Chapter
from app.core.config import settings


async def fix_stuck_chapters():
    """将所有卡在 generating 状态的章节标记为 failed"""

    # 创建数据库连接
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        # 查找所有状态为 generating 的章节
        stmt = select(Chapter).where(Chapter.status == "generating")
        result = await session.execute(stmt)
        stuck_chapters = result.scalars().all()

        if not stuck_chapters:
            print("✅ 没有发现卡住的章节")
            return

        print(f"🔍 发现 {len(stuck_chapters)} 个卡在 generating 状态的章节:")
        for chapter in stuck_chapters:
            print(f"   - 项目: {chapter.project_id}, 章节: {chapter.chapter_number}")

        # 更新状态为 failed
        update_stmt = (
            update(Chapter)
            .where(Chapter.status == "generating")
            .values(status="failed")
        )
        await session.execute(update_stmt)
        await session.commit()

        print(f"✅ 已将 {len(stuck_chapters)} 个章节状态更新为 failed")
        print("💡 用户现在可以在前端删除这些章节并重新生成")

    await engine.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 修复卡住的章节")
    print("=" * 60)
    asyncio.run(fix_stuck_chapters())
    print("=" * 60)
    print("✅ 修复完成")
    print("=" * 60)
