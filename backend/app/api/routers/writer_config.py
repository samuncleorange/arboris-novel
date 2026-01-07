import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.system_config import SystemConfig
from ...repositories.system_config_repository import SystemConfigRepository
from ...schemas.user import UserInDB


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/writer-config", tags=["Writer Configuration"])


class WriterConfigRead(BaseModel):
    chapter_versions: int = Field(description="每次生成的章节版本数量")


class WriterConfigUpdate(BaseModel):
    chapter_versions: int = Field(ge=1, le=10, description="每次生成的章节版本数量 (1-10)")


@router.get("", response_model=WriterConfigRead)
async def read_writer_config(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> WriterConfigRead:
    """获取写作配置"""
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")

    if record:
        try:
            value = int(record.value)
            if value > 0:
                logger.info("用户 %s 获取写作配置：版本数 = %d (来源：数据库)", current_user.id, value)
                return WriterConfigRead(chapter_versions=value)
        except (TypeError, ValueError):
            pass

    # 尝试从环境变量获取
    env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                logger.info("用户 %s 获取写作配置：版本数 = %d (来源：环境变量)", current_user.id, value)
                return WriterConfigRead(chapter_versions=value)
        except ValueError:
            pass

    # 使用默认值
    logger.info("用户 %s 获取写作配置：版本数 = 3 (来源：默认值)", current_user.id)
    return WriterConfigRead(chapter_versions=3)


@router.put("", response_model=WriterConfigRead)
async def update_writer_config(
    payload: WriterConfigUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> WriterConfigRead:
    """更新写作配置"""
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")

    if record:
        # 更新现有配置
        record.value = str(payload.chapter_versions)
        logger.info("用户 %s 更新写作配置：版本数 = %d (更新已有配置)", current_user.id, payload.chapter_versions)
    else:
        # 创建新配置
        record = SystemConfig(
            key="writer.chapter_versions",
            value=str(payload.chapter_versions),
            description="每次生成的章节版本数量"
        )
        session.add(record)
        logger.info("用户 %s 更新写作配置：版本数 = %d (创建新配置)", current_user.id, payload.chapter_versions)

    await session.commit()

    return WriterConfigRead(chapter_versions=payload.chapter_versions)


@router.delete("", status_code=204)
async def delete_writer_config(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """删除写作配置（将使用环境变量或默认值）"""
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")

    if record:
        await session.delete(record)
        await session.commit()
        logger.info("用户 %s 删除写作配置，系统将使用环境变量或默认值", current_user.id)
    else:
        logger.info("用户 %s 尝试删除写作配置，但配置不存在", current_user.id)
