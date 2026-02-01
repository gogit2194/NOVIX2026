"""
Base Agent Class / Agent 基类
Common functionality for all agents
所有 Agent 的通用功能
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.llm_gateway import LLMGateway
from app.storage import CardStorage, CanonStorage, DraftStorage
from app.context_engine.trace_collector import trace_collector, TraceEventType


class BaseAgent(ABC):
    """
    Abstract base class for all agents
    所有 Agent 的抽象基类
    """
    
    def __init__(
        self,
        gateway: LLMGateway,
        card_storage: CardStorage,
        canon_storage: CanonStorage,
        draft_storage: DraftStorage
    ):
        """
        Initialize agent
        
        Args:
            gateway: LLM gateway instance / 大模型网关实例
            card_storage: Card storage instance / 卡片存储实例
            canon_storage: Canon storage instance / 事实表存储实例
            draft_storage: Draft storage instance / 草稿存储实例
        """
        self.gateway = gateway
        self.card_storage = card_storage
        self.canon_storage = canon_storage
        self.draft_storage = draft_storage
    
    @abstractmethod
    async def execute(
        self,
        project_id: str,
        chapter: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute agent's task
        执行 Agent 的任务
        
        Args:
            project_id: Project ID / 项目ID
            chapter: Chapter ID / 章节ID
            context: Context data / 上下文数据
            
        Returns:
            Execution result / 执行结果
        """
        pass
    
    @abstractmethod
    def get_agent_name(self) -> str:
        """
        Get agent name
        获取 Agent 名称
        
        Returns:
            Agent name / Agent 名称
        """
        pass
    
    def get_system_prompt(self) -> str:
        """
        Get system prompt for this agent
        获取此 Agent 的系统提示词
        
        Returns:
            System prompt / 系统提示词
        """
        return f"You are a {self.get_agent_name()} agent for novel writing."
    
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Call LLM with agent-specific configuration
        使用 Agent 特定配置调用大模型
        
        Args:
            messages: Message list / 消息列表
            temperature: Temperature override / 温度覆盖
            
        Returns:
            LLM response content / 大模型响应内容
        """
        agent_name = self.get_agent_name()
        provider = self.gateway.get_provider_for_agent(agent_name)
        
        if temperature is None:
            temperature = self.gateway.get_temperature_for_agent(agent_name)
        
        response = await self.gateway.chat(
            messages=messages,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # === TRACE: Record LLM Request & Update Stats ===
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
                    "tokens": {
                        "total": total_tokens,
                        "prompt": prompt_tokens,
                        "completion": completion_tokens
                    },
                    "latency_ms": int(response.get("elapsed_time", 0) * 1000)
                }
            )
            
        except Exception as e:
            print(f"TRACE ERROR (LLM): {e}")
        
        return response["content"]
    
    async def call_llm_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ):
        """
        Stream LLM response token by token
        流式输出大模型响应
        
        Args:
            messages: Message list / 消息列表
            temperature: Temperature override / 温度覆盖
            
        Yields:
            Token chunks as they arrive
        """
        agent_name = self.get_agent_name()
        provider = self.gateway.get_provider_for_agent(agent_name)
        
        if temperature is None:
            temperature = self.gateway.get_temperature_for_agent(agent_name)
        
        async for chunk in self.gateway.stream_chat(
            messages=messages,
            provider=provider,
            temperature=temperature
        ):
            yield chunk
    
    def build_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        context_items: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Build message list for LLM
        构建发送给大模型的消息列表
        
        Args:
            system_prompt: System prompt / 系统提示词
            user_prompt: User prompt / 用户提示词
            context_items: Additional context items / 额外上下文项
            
        Returns:
            Message list / 消息列表
        """
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add context if provided / 添加上下文
        if context_items:
            context_text = "\n\n".join(context_items)
            messages.append({
                "role": "user",
                "content": f"Context:\n{context_text}"
            })
        
        # Add main user prompt / 添加主要用户提示
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        return messages
