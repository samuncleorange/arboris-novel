#!/usr/bin/env python3
"""清理数据库中的embedding配置，让系统使用环境变量"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.system_config import SystemConfig
from app.core.config import settings


async def clear_embedding_config():
    """清理数据库中的embedding相关配置"""

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
        # 查询现有的embedding配置
        stmt = select(SystemConfig).where(SystemConfig.key.like("embedding%"))
        result = await session.execute(stmt)
        configs = result.scalars().all()

        if not configs:
            print("✅ 数据库中没有embedding配置，已经使用环境变量")
            return

        print(f"🔍 发现 {len(configs)} 个embedding配置项：")
        for config in configs:
            print(f"   - {config.key} = {config.value}")

        # 删除所有embedding配置
        delete_stmt = delete(SystemConfig).where(SystemConfig.key.like("embedding%"))
        result = await session.execute(delete_stmt)
        await session.commit()

        print(f"\n✅ 已删除 {result.rowcount} 个配置项")
        print("💡 系统将使用 .env 文件中的 EMBEDDING_* 环境变量")

    await engine.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 清理数据库embedding配置")
    print("=" * 60)
    asyncio.run(clear_embedding_config())
    print("=" * 60)
    print("✅ 完成！请重启容器：docker-compose restart")
    print("=" * 60)
