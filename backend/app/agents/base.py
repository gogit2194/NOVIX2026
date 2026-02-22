# -*- coding: utf-8 -*-
"""
文枢 WenShape - 深度上下文感知的智能体小说创作系统
WenShape - Deep Context-Aware Agent-Based Novel Writing System

Copyright © 2025-2026 WenShape Team
License: PolyForm Noncommercial License 1.0.0

模块说明 / Module Description:
  Agent 基类，提供所有智能体的通用功能和 LLM 调用接口。
  Base Agent class providing common functionality and LLM interface for all agents.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.llm_gateway import LLMGateway
from app.storage import CardStorage, CanonStorage, DraftStorage
from app.context_engine.trace_collector import trace_collector, TraceEventType
from app.prompts import base_agent_system_prompt, format_context_message
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    所有智能体的抽象基类 - 提供通用功能

    Abstract base class for all agents. Provides common LLM interface,
    storage access, and tracing capabilities for derived Agent implementations.

    Attributes:
        gateway: LLM gateway instance for model calls.
        card_storage: Storage instance for character/world cards.
        canon_storage: Storage instance for canonical facts.
        draft_storage: Storage instance for draft chapters.
    """

    def __init__(
        self,
        gateway: LLMGateway,
        card_storage: CardStorage,
        canon_storage: CanonStorage,
        draft_storage: DraftStorage,
        language: str = "zh",
    ):
        """
        初始化智能体 - 注入所有依赖

        Initialize agent with storage and LLM gateway dependencies.

        Args:
            gateway: LLM gateway instance for model calls.
            card_storage: Card storage instance for character/world cards.
            canon_storage: Canon storage instance for facts and settings.
            draft_storage: Draft storage instance for chapters and summaries.
            language: Writing language ("zh" for Chinese, "en" for English).
        """
        self.gateway = gateway
        self.card_storage = card_storage
        self.canon_storage = canon_storage
        self.draft_storage = draft_storage
        self.language = language

    @abstractmethod
    async def execute(
        self,
        project_id: str,
        chapter: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行智能体的核心任务 - 由子类实现

        Execute the agent's main task. Must be implemented by subclasses.

        Args:
            project_id: Unique project identifier.
            chapter: Chapter ID for context.
            context: Context dictionary with task-specific parameters.

        Returns:
            Dictionary with execution results (success status, output data, etc).
        """
        pass

    @abstractmethod
    def get_agent_name(self) -> str:
        """
        获取智能体标识名 - 用于配置和日志

        Get the agent's unique name identifier for configuration and logging.

        Returns:
            Agent name string (e.g., "writer", "editor", "archivist").
        """
        pass

    def get_system_prompt(self) -> str:
        """
        获取系统提示词 - 根据智能体类型生成

        Get the system prompt for this agent instance.

        Returns:
            System prompt string customized for the agent type.
        """
        return base_agent_system_prompt(self.get_agent_name(), language=self.language)
    
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        config_agent: Optional[str] = None,
        return_meta: bool = False,
    ) -> Any:
        """
        调用大模型 - 支持智能体特定配置和流量追踪

        Call LLM with agent-specific configuration from gateway settings.
        Automatically records token usage and latency metrics for monitoring.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            temperature: Temperature override for this call (uses agent default if None).
            max_tokens: Maximum output tokens for this call.
            config_agent: Override agent name for configuration lookup.
            return_meta: If True, return full response dict including metadata.

        Returns:
            If return_meta=False: LLM response content string.
            If return_meta=True: Full response dict with content, usage, model info.
        """
        agent_name = config_agent or self.get_agent_name()
        provider = self.gateway.get_provider_for_agent(agent_name)

        if temperature is None:
            temperature = self.gateway.get_temperature_for_agent(agent_name)

        response = await self.gateway.chat(
            messages=messages,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # ============================================================================
        # 记录 LLM 请求和统计 / Record LLM request and update metrics
        # ============================================================================
        # Track token usage in three categories for context monitor:
        # - guiding: system prompt tokens
        # - informational: context tokens
        # - actionable: prompt instruction + completion tokens
        try:
            usage = response.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            # Heuristic breakdown for Context Monitor
            # Guiding ~ 10% of prompt (System prompt)
            # Informational ~ 80% of prompt (Context)
            # Actionable ~ 10% of prompt + 100% of completion
            guiding = int(prompt_tokens * 0.1)
            informational = int(prompt_tokens * 0.8)
            actionable = prompt_tokens - guiding - informational + completion_tokens

            # 1. Update global stats (for Gauge)
            await trace_collector.update_token_stats(
                total_delta=total_tokens,
                breakdown_delta={
                    "guiding": guiding,
                    "informational": informational,
                    "actionable": actionable
                }
            )

            # 2. Record detailed event (for Timeline)
            await trace_collector.record(
                TraceEventType.LLM_REQUEST,
                self.get_agent_name(),
                {
                    "model": response.get("model", "unknown"),
                    "provider": response.get("provider", "unknown"),
                    "config_agent": agent_name,
                    "tokens": {
                        "total": total_tokens,
                        "prompt": prompt_tokens,
                        "completion": completion_tokens
                    },
                    "latency_ms": int(response.get("elapsed_time", 0) * 1000)
                }
            )

        except Exception as e:
            logger.warning("TRACE ERROR (LLM): %s", e)

        if return_meta:
            return response
        return response["content"]
    
    async def call_llm_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ):
        """
        流式输出大模型响应 - 逐token返回，适合前端实时显示

        Stream LLM response token by token. Yields tokens as they arrive.
        Falls back to non-streaming if upstream chunked read fails.

        Args:
            messages: List of message dicts with "role" and "content" keys.
            temperature: Temperature override (uses agent default if None).

        Yields:
            Token strings as they arrive from LLM.
        """
        agent_name = self.get_agent_name()
        provider = self.gateway.get_provider_for_agent(agent_name)

        if temperature is None:
            temperature = self.gateway.get_temperature_for_agent(agent_name)

        has_chunk = False
        try:
            async for chunk in self.gateway.stream_chat(
                messages=messages,
                provider=provider,
                temperature=temperature
            ):
                if chunk:
                    has_chunk = True
                yield chunk
        except Exception:
            if has_chunk:
                raise
            # Fallback to non-streaming to avoid hard failures on upstream chunked reads.
            response = await self.gateway.chat(
                messages=messages,
                provider=provider,
                temperature=temperature
            )
            yield response.get("content", "")
    
    def build_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        context_items: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        构建发送给大模型的消息列表 - 标准格式

        Build message list in standard format for LLM API calls.
        Supports system prompt + context + user prompt structure.

        Args:
            system_prompt: System message content (instructions, constraints).
            user_prompt: Main user message content (question, task).
            context_items: Optional list of context items to insert as user message.

        Returns:
            List of message dicts with "role" and "content" keys in order:
            1. System message
            2. Context message (if provided)
            3. User message
        """
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add context if provided
        if context_items:
            messages.append({
                "role": "user",
                "content": format_context_message(context_items, language=self.language)
            })

        # Add main user prompt
        messages.append({
            "role": "user",
            "content": user_prompt
        })

        return messages
