"""
Editor Agent / 缂栬緫
Revises drafts based on user feedback
鏍规嵁鐢ㄦ埛鍙嶉淇鑽夌
"""

from typing import Dict, Any, List
from app.agents.base import BaseAgent
from app.utils.logger import get_logger
from app.utils.version import increment_version

logger = get_logger(__name__)


class EditorAgent(BaseAgent):
    """
    Editor agent responsible for revising drafts
    缂栬緫锛岃礋璐ｄ慨璁㈣崏绋?
    """

    def get_agent_name(self) -> str:
        """Get agent name / 鑾峰彇 Agent 鍚嶇О"""
        return "editor"

    def get_system_prompt(self) -> str:
        """Get system prompt / 鑾峰彇绯荤粺鎻愮ず璇?"""
        return (
            "你是编辑（Editor）。\n"
            "职责：\n"
            "1) 严格按用户反馈修改，只改涉及的部分；\n"
            "2) 维持作者原有文风与语气，润色流畅度；\n"
            "3) 不引入新设定与矛盾。\n"
            "输出：仅输出修改后的正文，确保改动可见且满足反馈。"
        )

    async def execute(
        self,
        project_id: str,
        chapter: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Revise draft based on user feedback
        鏍规嵁鐢ㄦ埛鍙嶉淇鑽夌

        Args:
            project_id: Project ID / 椤圭洰ID
            chapter: Chapter ID / 绔犺妭ID
            context: Context with draft_version, user_feedback / 鍖呭惈鑽夌鐗堟湰鍜岀敤鎴峰弽棣堢殑涓婁笅鏂?
        Returns:
            Result with revised draft / 鍖呭惈淇绋跨殑缁撴灉
        """
        draft_version = context.get("draft_version", "v1")
        draft = await self.draft_storage.get_draft(project_id, chapter, draft_version)

        if not draft:
            return {
                "success": False,
                "error": f"Draft {draft_version} not found"
            }

        user_feedback = context.get("user_feedback", "")
        if not user_feedback:
            return {
                "success": False,
                "error": "User feedback is required"
            }

        style_card = await self.card_storage.get_style_card(project_id)
        rejected_entities = context.get("rejected_entities", [])

        revised_content = await self._generate_revision_from_feedback(
            original_draft=draft.content,
            user_feedback=user_feedback,
            style_card=style_card,
            rejected_entities=rejected_entities
        )

        new_version = increment_version(draft_version)
        word_count = len(revised_content)

        revised_draft = await self.draft_storage.save_draft(
            project_id=project_id,
            chapter=chapter,
            version=new_version,
            content=revised_content,
            word_count=word_count,
            pending_confirmations=[]
        )

        return {
            "success": True,
            "draft": revised_draft,
            "version": new_version,
            "word_count": word_count
        }

    async def _generate_revision_from_feedback(
        self,
        original_draft: str,
        user_feedback: str,
        style_card: Any = None,
        rejected_entities: List[str] = None
    ) -> str:
        """
        Generate revised draft directly from user feedback
        鐩存帴鏍规嵁鐢ㄦ埛鍙嶉鐢熸垚淇鍐呭

        CRITICAL: This MUST follow user instructions. Never refuse.
        """
        context_items = []

        if style_card:
            try:
                context_items.append(f"Style: {style_card.style}")
            except (AttributeError, TypeError) as e:
                logger.warning(f"Failed to add style guidance: {e}")

        if rejected_entities:
            context_items.append(
                "Rejected Concepts: " + ", ".join(rejected_entities) + "\n"
                "You MUST remove or rewrite any rejected concepts."
            )

        user_prompt = f"""你是编辑，必须100%执行用户修改意见，只改涉及部分且改动可见。
规则：
- 不得拒绝或敷衍，必须体现修改。
- 未被提及的内容保持不变；禁止新增设定或剧情。
- 如反馈是风格类请求，需在全文体现相应变化。

原稿：
{original_draft}

用户反馈：
{user_feedback}

输出：仅输出修改后的正文。"""

        messages = self.build_messages(
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            context_items=context_items
        )

        response = await self.call_llm(messages)
        return response.strip()
