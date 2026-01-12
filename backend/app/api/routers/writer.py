import json
import logging
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import Chapter, ChapterOutline
from ...schemas.novel import (
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService
from ...utils.json_utils import remove_think_tags, sanitize_json_like_text, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    # 收集所有可用的历史章节摘要，便于在 Prompt 中提供前情背景
    completed_chapters = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            summary = await llm_service.get_summary(
                existing.selected_version.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            existing.real_summary = remove_think_tags(summary)
            await session.commit()
        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
                "summary": existing.real_summary,
            }
        )
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    # 蓝图中禁止携带章节级别的细节信息，避免重复传输大段场景或对话内容
    banned_blueprint_keys = {
        "chapter_outline",
        "chapter_summaries",
        "chapter_details",
        "chapter_dialogues",
        "chapter_events",
        "conversation_history",
        "character_timelines",
    }
    for key in banned_blueprint_keys:
        if key in blueprint_dict:
            blueprint_dict.pop(key, None)

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置名为 'writing' 的写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

    # 初始化向量检索服务，若未配置则自动降级为纯提示词生成
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=current_user.id,
    )
    chunk_count = len(rag_context.chunks) if rag_context and rag_context.chunks else 0
    summary_count = len(rag_context.summaries) if rag_context and rag_context.summaries else 0
    logger.info(
        "项目 %s 第 %s 章检索到 %s 个剧情片段和 %s 条摘要",
        project_id,
        request.chapter_number,
        chunk_count,
        summary_count,
    )
    # print("rag_context:",rag_context)
    # 将蓝图、前情、RAG 检索结果拼装成结构化段落，供模型理解
    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
    completed_lines = [
        f"- 第{item['chapter_number']}章 - {item['title']}:{item['summary']}"
        for item in completed_chapters
    ]
    previous_summary_text = previous_summary_text or "暂无可用摘要"
    previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
    completed_section = "\n".join(completed_lines) if completed_lines else "暂无前情摘要"
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        # ("[前情摘要]", completed_section),
        ("[上一章摘要]", previous_summary_text),
        ("[上一章结尾]", previous_tail_excerpt),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要]", rag_summaries_text),
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        ),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)
    async def _generate_single_version(idx: int) -> Dict:
        # 字数要求的重试策略：4500 -> 3500 -> 2500 -> 1500
        target_word_counts = [4500, 3500, 2500, 1500]
        
        for retry_attempt, target_words in enumerate(target_word_counts):
            try:
                # 如果是重试，修改提示词中的字数要求
                current_prompt = writer_prompt
                if retry_attempt > 0:
                    logger.info(
                        "项目 %s 第 %s 章第 %s 个版本因token限制重试，降低字数要求至 %d 字",
                        project_id,
                        request.chapter_number,
                        idx + 1,
                        target_words,
                    )
                    # 在用户消息中明确降低字数要求
                    retry_instruction = f"\n\n【重要提示】由于上次生成被截断，请将本章字数控制在 {target_words} 字左右，确保内容完整。"
                    current_user_content = prompt_input + retry_instruction
                else:
                    current_user_content = prompt_input
                
                response = await llm_service.get_llm_response(
                    system_prompt=current_prompt,
                    conversation_history=[{"role": "user", "content": current_user_content}],
                    temperature=0.9,
                    user_id=current_user.id,
                    timeout=600.0,
                    response_format=None,  # Claude API不支持response_format参数
                    max_tokens=16000,  # 确保有足够的token生成完整章节
                )
                cleaned = remove_think_tags(response)
                normalized = unwrap_markdown_json(cleaned)
                sanitized = sanitize_json_like_text(normalized)  # 清理未转义的控制字符
                try:
                    result = json.loads(sanitized)
                    logger.info(
                        "项目 %s 第 %s 章第 %s 个版本生成成功（尝试 %d/%d，目标字数 %d）",
                        project_id,
                        request.chapter_number,
                        idx + 1,
                        retry_attempt + 1,
                        len(target_word_counts),
                        target_words,
                    )
                    return result
                except json.JSONDecodeError as parse_err:
                    logger.warning(
                        "项目 %s 第 %s 章第 %s 个版本 JSON 解析失败，尝试正则提取: %s",
                        project_id,
                        request.chapter_number,
                        idx + 1,
                        parse_err,
                    )
                    # 记录响应内容的前500字符，便于调试
                    logger.debug("响应内容预览: %s", sanitized[:500])
                    
                    import re
                    
                    # 检查是否是纯文本响应（没有JSON结构）
                    if not sanitized.strip().startswith('{'):
                        logger.warning("LLM返回的不是JSON格式，将作为纯文本处理")
                        return {"full_content": sanitized}
                    
                    # 尝试修复被截断的JSON（补全缺失的引号和括号）
                    repaired = sanitized.rstrip()
                    if repaired and not repaired.endswith('}'):
                        # 检查是否在字符串值中被截断
                        if repaired.count('"') % 2 == 1:  # 奇数个引号，说明字符串未闭合
                            repaired += '"'
                        # 补全缺失的闭合括号
                        open_braces = repaired.count('{') - repaired.count('}')
                        repaired += '}' * open_braces
                        
                        # 尝试解析修复后的JSON
                        try:
                            result = json.loads(repaired)
                            logger.info("成功修复并解析JSON")
                            return result
                        except json.JSONDecodeError:
                            logger.debug("修复JSON失败，继续使用正则提取")
                    
                    # 方案1：尝试提取完整的full_content字段（有闭合引号）
                    match = re.search(r'"(?:full_)?content"\s*:\s*"((?:[^"\\]|\\.)*)"', sanitized, re.DOTALL)
                    if match:
                        try:
                            # 直接使用提取的内容，不做unicode_escape解码
                            # 因为JSON中的转义字符已经被json.loads处理过了
                            extracted = match.group(1)
                            # 只处理基本的转义序列
                            extracted = extracted.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                            logger.info("成功通过正则提取完整的content字段，长度: %d", len(extracted))
                            return { "full_content": extracted }
                        except Exception as e:
                            logger.warning("正则提取后处理失败: %s", e)
                    
                    # 方案2：尝试提取被截断的content字段（没有闭合引号，提取到字符串末尾）
                    match_incomplete = re.search(r'"(?:full_)?content"\s*:\s*"(.*)$', sanitized, re.DOTALL)
                    if match_incomplete:
                        try:
                            # 移除末尾可能的不完整字符和多余的括号/引号
                            raw_content = match_incomplete.group(1).rstrip('"}]')
                            # 处理基本的转义序列，不使用unicode_escape
                            extracted = raw_content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                            logger.info("成功提取被截断的content字段，长度: %d", len(extracted))
                            return { "full_content": extracted }
                        except Exception as e:
                            logger.warning("提取被截断content失败: %s", e)
                    
                    # 方案3：完全无法解析，返回原始内容
                    logger.error("无法从响应中提取章节内容，返回原始文本")
                    return {"content": sanitized}
                    
            except HTTPException as http_exc:
                # 检查是否是token限制异常
                if http_exc.status_code == 413 and "TOKEN_LIMIT_EXCEEDED" in str(http_exc.detail):
                    if retry_attempt < len(target_word_counts) - 1:
                        logger.warning(
                            "项目 %s 第 %s 章第 %s 个版本遇到token限制，将重试并降低字数（当前目标: %d字）",
                            project_id,
                            request.chapter_number,
                            idx + 1,
                            target_words,
                        )
                        continue  # 继续下一次重试
                    else:
                        logger.error(
                            "项目 %s 第 %s 章第 %s 个版本经过 %d 次重试仍超过token限制",
                            project_id,
                            request.chapter_number,
                            idx + 1,
                            len(target_word_counts),
                        )
                        raise HTTPException(
                            status_code=500,
                            detail=f"生成章节失败：即使降低字数要求至 {target_word_counts[-1]} 字仍超过token限制，请简化章节大纲或调整模型参数"
                        )
                else:
                    # 其他HTTP异常直接抛出
                    raise
        
        # 如果所有重试都失败（理论上不会到这里）
        raise HTTPException(
            status_code=500,
            detail="生成章节失败：所有重试尝试都已耗尽"
        )

    version_count = await _resolve_version_count(session)
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本",
        project_id,
        request.chapter_number,
        version_count,
    )

    # 生成多个版本，允许部分失败
    raw_versions = []
    for idx in range(version_count):
        try:
            version = await _generate_single_version(idx)
            raw_versions.append(version)
        except Exception as exc:
            logger.error(
                "项目 %s 第 %s 章第 %s 个版本生成失败，继续尝试下一个版本: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            # 如果是第一个版本就失败，记录错误但继续尝试其他版本
            # 只有所有版本都失败时才抛出异常
            if idx == version_count - 1 and not raw_versions:
                # 所有版本都失败了，更新章节状态为failed
                chapter.status = "failed"
                await session.commit()
                logger.error(
                    "项目 %s 第 %s 章所有 %s 个版本生成都失败",
                    project_id,
                    request.chapter_number,
                    version_count,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"生成章节失败：所有 {version_count} 个版本都生成失败，请重试"
                )

    # 检查是否至少有一个版本成功
    if not raw_versions:
        chapter.status = "failed"
        await session.commit()
        raise HTTPException(
            status_code=500,
            detail="生成章节失败：未能成功生成任何版本"
        )

    logger.info(
        "项目 %s 第 %s 章成功生成 %s/%s 个版本",
        project_id,
        request.chapter_number,
        len(raw_versions),
        version_count,
    )

    contents: List[str] = []
    metadata: List[Dict] = []
    for variant in raw_versions:
        if isinstance(variant, dict):
            # 优先提取 full_content 字段（新的章节生成格式）
            if "full_content" in variant and isinstance(variant["full_content"], str):
                contents.append(variant["full_content"])
            # 其次尝试 content 字段
            elif "content" in variant and isinstance(variant["content"], str):
                contents.append(variant["content"])
            # 最后尝试 chapter_content 字段
            elif "chapter_content" in variant:
                contents.append(str(variant["chapter_content"]))
            # 如果以上字段都不存在，则将整个对象序列化为 JSON
            else:
                contents.append(json.dumps(variant, ensure_ascii=False))
            metadata.append(variant)
        else:
            contents.append(str(variant))
            metadata.append({"raw": variant})

    await novel_service.replace_chapter_versions(chapter, contents, metadata)
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    return await _load_project_schema(novel_service, project_id, current_user.id)


async def _resolve_version_count(session: AsyncSession) -> int:
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")
    if record:
        try:
            value = int(record.value)
            if value > 0:
                logger.info("从数据库读取版本数量: %d", value)
                return value
        except (TypeError, ValueError):
            pass
    env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
    logger.info("环境变量 WRITER_CHAPTER_VERSION_COUNT = %s", env_value)
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                logger.info("使用环境变量版本数量: %d", value)
                return value
        except ValueError:
            pass
    logger.warning("未找到有效配置，使用默认值: 3")
    return 3


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法选择版本", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    selected = await novel_service.select_chapter_version(chapter, request.version_index)
    logger.info(
        "用户 %s 选择了项目 %s 第 %s 章的第 %s 个版本",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )
    if selected and selected.content:
        summary = await llm_service.get_summary(
            selected.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
        await session.commit()

        # 选定版本后同步向量库，确保后续章节可检索到最新内容
        vector_store: Optional[VectorStoreService]
        if not settings.vector_store_enabled:
            vector_store = None
        else:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过章节向量同步: %s", exc)
                vector_store = None

        if vector_store:
            ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
            outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            
            total_chunks = 0
            successful_chunks = 0
            failed_chunks = 0
            
            try:
                # 先统计章节会被切成多少块
                content_chunks = ingestion_service._split_into_chunks(selected.content)
                total_chunks = len(content_chunks)
                
                # 尝试生成所有块的向量
                chunk_records = []
                for index, chunk_text in enumerate(content_chunks):
                    embedding = await llm_service.get_embedding(
                        chunk_text,
                        user_id=current_user.id,
                    )
                    if embedding:
                        successful_chunks += 1
                        record_id = f"{project_id}:{chapter.chapter_number}:{index}"
                        chunk_records.append({
                            "id": record_id,
                            "project_id": project_id,
                            "chapter_number": chapter.chapter_number,
                            "chunk_index": index,
                            "chapter_title": chapter_title,
                            "content": chunk_text,
                            "embedding": embedding,
                            "metadata": {
                                "chunk_id": record_id,
                                "length": len(chunk_text),
                            },
                        })
                    else:
                        failed_chunks += 1
                        continue
                
                # 写入成功的记录
                if chunk_records:
                    await vector_store.delete_by_chapters(project_id, [chapter.chapter_number])
                    await vector_store.upsert_chunks(records=chunk_records)
                    logger.info(
                        "项目 %s 第 %s 章向量同步完成: 成功 %d/%d",
                        project_id,
                        chapter.chapter_number,
                        successful_chunks,
                        total_chunks,
                    )
                
                # 处理错误情况
                if successful_chunks == 0:
                    # 全部失败，抛出异常
                    if total_chunks > 0:
                        logger.error(
                            "项目 %s 第 %s 章向量同步完全失败: 0/%d",
                            project_id,
                            chapter.chapter_number,
                            total_chunks,
                        )
                        raise HTTPException(
                            status_code=500,
                            detail="章节向量同步失败，可能是 AI 服务余额不足或 API 速率限制"
                        )
                else:
                    # 部分成功，记录警告
                    if failed_chunks > 0:
                        logger.warning(
                            "项目 %s 第 %s 章向量同步部分失败: 成功 %d/%d",
                            project_id,
                            chapter.chapter_number,
                            successful_chunks,
                            total_chunks,
                        )
                    
            except openai.RateLimitError as exc:
                logger.error(
                    "项目 %s 第 %s 章向量同步速率限制",
                    project_id,
                    chapter.chapter_number,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=429,
                    detail="AI 服务速率限制，请稍后重试"
                ) from exc
            except openai.APIError as exc:
                error_msg = str(exc)
                if "余额不足" in error_msg or "insufficient" in error_msg.lower():
                    logger.error(
                        "项目 %s 第 %s 章向量同步余额不足",
                        project_id,
                        chapter.chapter_number,
                    )
                    raise HTTPException(
                        status_code=402,
                        detail="AI 服务余额不足，请充值后重试"
                    ) from exc
                else:
                    logger.error(
                        "项目 %s 第 %s 章向量同步 API 错误: %s",
                        project_id,
                        chapter.chapter_number,
                        error_msg,
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"向量同步失败: {error_msg}"
                    ) from exc
            except Exception as exc:
                logger.error(
                    "项目 %s 第 %s 章向量同步失败: %s",
                    project_id,
                    chapter.chapter_number,
                    exc,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"向量同步失败: {str(exc)}"
                ) from exc

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法执行评估", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无可评估版本", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可评估的章节版本")

    evaluator_prompt = await prompt_service.get_prompt("evaluation")
    if not evaluator_prompt:
        logger.error("缺少评估提示词，项目 %s 第 %s 章评估失败", project_id, request.chapter_number)
        raise HTTPException(status_code=500, detail="缺少评估提示词，请联系管理员配置 'evaluation' 提示词")

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    versions_to_evaluate = [
        {"version_id": idx + 1, "content": version.content}
        for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
    ]
    # print("blueprint_dict:",blueprint_dict)
    evaluator_payload = {
        "novel_blueprint": blueprint_dict,
        "content_to_evaluate": {
            "chapter_number": chapter.chapter_number,
            "versions": versions_to_evaluate,
        },
    }

    evaluation_raw = await llm_service.get_llm_response(
        system_prompt=evaluator_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
        temperature=0.3,
        user_id=current_user.id,
        timeout=360.0,
    )
    evaluation_clean = remove_think_tags(evaluation_raw)
    await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
    logger.info("项目 %s 第 %s 章评估完成", project_id, request.chapter_number)

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapter_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 请求生成项目 %s 的章节大纲，起始章节 %s，数量 %s",
        current_user.id,
        project_id,
        request.start_chapter,
        request.num_chapters,
    )
    outline_prompt = await prompt_service.get_prompt("outline")
    if not outline_prompt:
        logger.error("缺少大纲提示词，项目 %s 大纲生成失败", project_id)
        raise HTTPException(status_code=500, detail="缺少大纲提示词，请联系管理员配置 'outline' 提示词")

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint_dict = project_schema.blueprint.model_dump()

    payload = {
        "novel_blueprint": blueprint_dict,
        "wait_to_generate": {
            "start_chapter": request.start_chapter,
            "num_chapters": request.num_chapters,
        },
    }

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        temperature=0.7,
        user_id=current_user.id,
        timeout=360.0,
    )
    normalized = unwrap_markdown_json(remove_think_tags(response))
    sanitized = sanitize_json_like_text(normalized)
    try:
        data = json.loads(sanitized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 大纲生成 JSON 解析失败: %s, 原始内容预览: %s",
            project_id,
            exc,
            normalized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"章节大纲生成失败，AI 返回的内容格式不正确: {str(exc)}"
        ) from exc

    new_outlines = data.get("chapters", [])
    for item in new_outlines:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == item.get("chapter_number"),
            )
        )
        result = await session.execute(stmt)
        record = result.scalars().first()
        if record:
            record.title = item.get("title", record.title)
            record.summary = item.get("summary", record.summary)
        else:
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=item.get("chapter_number"),
                    title=item.get("title", ""),
                    summary=item.get("summary"),
                )
            )
    await session.commit()
    logger.info("项目 %s 章节大纲生成完成", project_id)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 更新项目 %s 第 %s 章大纲",
        current_user.id,
        project_id,
        request.chapter_number,
    )

    stmt = (
        select(ChapterOutline)
        .where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    outline = result.scalars().first()
    if not outline:
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=request.chapter_number,
        )
        session.add(outline)

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()
    logger.info("项目 %s 第 %s 章大纲已更新", project_id, request.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    if not request.chapter_numbers:
        logger.warning("项目 %s 删除章节时未提供章节号", project_id)
        raise HTTPException(status_code=400, detail="请提供要删除的章节号列表")
    novel_service = NovelService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 删除项目 %s 的章节 %s",
        current_user.id,
        project_id,
        request.chapter_numbers,
    )
    await novel_service.delete_chapters(project_id, request.chapter_numbers)

    # 删除章节时同步清理向量库，避免过时内容被检索
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量删除: %s", exc)
            vector_store = None

    if vector_store:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        await ingestion_service.delete_chapters(project_id, request.chapter_numbers)
        logger.info(
            "项目 %s 已从向量库移除章节 %s",
            project_id,
            request.chapter_numbers,
        )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or chapter.selected_version is None:
        logger.warning("项目 %s 第 %s 章尚未生成或未选择版本，无法编辑", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节尚未生成或未选择版本")

    chapter.selected_version.content = request.content
    chapter.word_count = len(request.content)
    logger.info("用户 %s 更新了项目 %s 第 %s 章内容", current_user.id, project_id, request.chapter_number)

    if request.content.strip():
        summary = await llm_service.get_summary(
            request.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
    await session.commit()

    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量更新: %s", exc)
            vector_store = None

    if vector_store and chapter.selected_version and chapter.selected_version.content:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
        chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
        await ingestion_service.ingest_chapter(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            title=chapter_title,
            content=chapter.selected_version.content,
            summary=chapter.real_summary,
            user_id=current_user.id,
        )
        logger.info("项目 %s 第 %s 章更新内容已同步至向量库", project_id, chapter.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)
