# -*- coding: utf-8 -*-
"""
文枢 WenShape - 深度上下文感知的智能体小说创作系统
WenShape - Deep Context-Aware Agent-Based Novel Writing System

Copyright © 2025-2026 WenShape Team
License: PolyForm Noncommercial License 1.0.0

模块说明 / Module Description:
  卡片路由 - 角色和世界观卡片管理
  Cards Router - Character and world card management endpoints
  Provides CRUD operations for character cards, world cards, and style cards.
"""

from typing import List, Optional

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.schemas.card import CharacterCard, WorldCard, StyleCard
from app.llm_gateway import get_gateway
from app.agents import ArchivistAgent
from app.dependencies import get_card_storage, get_canon_storage, get_draft_storage
from app.utils.language import normalize_language
from app.utils.path_safety import sanitize_id

router = APIRouter(prefix="/projects/{project_id}/cards", tags=["cards"])
card_storage = get_card_storage()


class StyleExtractRequest(BaseModel):
    """
    风格提取请求 / Request body for style extraction.

    Attributes:
        content (str): 样本文本用于风格提取 / Sample text for style extraction.
    """

    language: Optional[str] = Field(
        None,
        description="Writing language override: zh/en or locale-like values",
    )
    content: str = Field(..., description="Sample text for style extraction")


async def _resolve_project_language(project_id: str, request_language: Optional[str]) -> str:
    explicit = normalize_language(request_language, default="")
    if explicit in {"zh", "en"}:
        return explicit

    try:
        from pathlib import Path

        project_yaml = Path(card_storage.data_dir) / project_id / "project.yaml"
        if not project_yaml.exists():
            return "zh"
        data = await card_storage.read_yaml(project_yaml)
        return normalize_language((data or {}).get("language"), default="zh")
    except Exception:
        return "zh"


@router.get("/characters")
async def list_character_cards(project_id: str) -> List[str]:
    """列出所有角色卡片名称 / List all character card names.

    Args:
        project_id: 项目ID / Project identifier.

    Returns:
        角色卡片名称列表 / List of character card names.
    """
    return await card_storage.list_character_cards(project_id)


@router.get("/characters/index")
async def list_character_cards_index(project_id: str) -> List[CharacterCard]:
    """列出所有角色卡片及其元数据（单个请求） / List all character cards with metadata (single request).

    Args:
        project_id: 项目ID / Project identifier.

    Returns:
        角色卡片列表 / List of CharacterCard objects.
    """
    names = await card_storage.list_character_cards(project_id)
    if not names:
        return []

    async def _safe_get(name: str) -> Optional[CharacterCard]:
        try:
            return await card_storage.get_character_card(project_id, name)
        except (FileNotFoundError, ValueError, KeyError):
            return None

    results = await asyncio.gather(*[_safe_get(name) for name in names])
    return [card for card in results if card]


@router.get("/characters/{character_name}")
async def get_character_card(project_id: str, character_name: str):
    """获取特定角色卡片 / Get a character card.

    Args:
        project_id: 项目ID / Project identifier.
        character_name: 角色名称 / Character name.

    Returns:
        角色卡片对象 / CharacterCard object.

    Raises:
        HTTPException: 404 if card not found, 400 if name invalid.
    """
    try:
        sanitize_id(character_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid character name")
    card = await card_storage.get_character_card(project_id, character_name)
    if not card:
        raise HTTPException(status_code=404, detail="Character card not found")
    return card


@router.post("/characters")
async def create_character_card(project_id: str, card: CharacterCard):
    """创建角色卡片 / Create a character card.

    Args:
        project_id: 项目ID / Project identifier.
        card: 角色卡片数据 / CharacterCard object.

    Returns:
        成功消息 / Success response.
    """
    await card_storage.save_character_card(project_id, card)
    return {"success": True, "message": "Character card created"}


@router.put("/characters/{character_name}")
async def update_character_card(project_id: str, character_name: str, card: CharacterCard):
    """更新角色卡片 / Update a character card.

    Args:
        project_id: 项目ID / Project identifier.
        character_name: 角色名称 / Character name.
        card: 更新后的卡片数据 / Updated CharacterCard object.

    Returns:
        成功消息 / Success response.
    """
    card.name = character_name
    await card_storage.save_character_card(project_id, card)
    return {"success": True, "message": "Character card updated"}


@router.delete("/characters/{character_name}")
async def delete_character_card(project_id: str, character_name: str):
    """删除角色卡片 / Delete a character card.

    Args:
        project_id: 项目ID / Project identifier.
        character_name: 角色名称 / Character name.

    Returns:
        成功消息 / Success response.

    Raises:
        HTTPException: 404 if card not found, 400 if name invalid.
    """
    try:
        sanitize_id(character_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid character name")
    success = await card_storage.delete_character_card(project_id, character_name)
    if not success:
        raise HTTPException(status_code=404, detail="Character card not found")
    return {"success": True, "message": "Character card deleted"}


@router.get("/world")
async def list_world_cards(project_id: str) -> List[str]:
    """列出所有世界观卡片名称 / List all world card names.

    Args:
        project_id: 项目ID / Project identifier.

    Returns:
        世界观卡片名称列表 / List of world card names.
    """
    return await card_storage.list_world_cards(project_id)


@router.get("/world/index")
async def list_world_cards_index(project_id: str) -> List[WorldCard]:
    """列出所有世界观卡片及其元数据（单个请求） / List all world cards with metadata (single request).

    Args:
        project_id: 项目ID / Project identifier.

    Returns:
        世界观卡片列表 / List of WorldCard objects.
    """
    names = await card_storage.list_world_cards(project_id)
    if not names:
        return []

    async def _safe_get(name: str) -> Optional[WorldCard]:
        try:
            return await card_storage.get_world_card(project_id, name)
        except (FileNotFoundError, ValueError, KeyError):
            return None

    results = await asyncio.gather(*[_safe_get(name) for name in names])
    return [card for card in results if card]


@router.get("/world/{card_name}")
async def get_world_card(project_id: str, card_name: str):
    """Get a world card."""
    try:
        sanitize_id(card_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid card name")
    card = await card_storage.get_world_card(project_id, card_name)
    if not card:
        raise HTTPException(status_code=404, detail="World card not found")
    return card


@router.post("/world")
async def create_world_card(project_id: str, card: WorldCard):
    """Create a world card."""
    await card_storage.save_world_card(project_id, card)
    return {"success": True, "message": "World card created"}


@router.put("/world/{card_name}")
async def update_world_card(project_id: str, card_name: str, card: WorldCard):
    """Update a world card."""
    card.name = card_name
    await card_storage.save_world_card(project_id, card)
    return {"success": True, "message": "World card updated"}


@router.delete("/world/{card_name}")
async def delete_world_card(project_id: str, card_name: str):
    """Delete a world card."""
    try:
        sanitize_id(card_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid card name")
    success = await card_storage.delete_world_card(project_id, card_name)
    if not success:
        raise HTTPException(status_code=404, detail="World card not found")
    return {"success": True, "message": "World card deleted"}


@router.get("/style")
async def get_style_card(project_id: str):
    """Get style card."""
    card = await card_storage.get_style_card(project_id)
    if not card:
        raise HTTPException(status_code=404, detail="Style card not found")
    return card


@router.put("/style")
async def update_style_card(project_id: str, card: StyleCard):
    """Update style card."""
    await card_storage.save_style_card(project_id, card)
    return {"success": True, "message": "Style card updated"}


@router.post("/style/extract")
async def extract_style_card(project_id: str, request: StyleExtractRequest):
    """Extract style guidance from sample text."""
    content = (request.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")

    language = await _resolve_project_language(project_id, request.language)
    gateway = get_gateway()
    archivist = ArchivistAgent(
        gateway,
        card_storage,
        get_canon_storage(),
        get_draft_storage(),
        language=language,
    )
    style_text = await archivist.extract_style_profile(content)
    return {"style": style_text}
