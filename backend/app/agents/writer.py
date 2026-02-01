"""
Writer Agent
Generates draft based on scene brief.
"""

from typing import Any, Dict, List
import json

from app.agents.base import BaseAgent


class WriterAgent(BaseAgent):
    """Agent responsible for generating drafts."""

    DEFAULT_QUESTIONS = [
        {"type": "plot_point", "text": "为达成本章目标，尚缺的剧情/世界信息是什么？"},
        {"type": "character_change", "text": "哪些主角的动机或情绪需再确认，避免违背既有事实？"},
        {"type": "detail_gap", "text": "还有哪些具体细节（地点/时间/物件）需要确定后再写？"},
    ]

    def get_agent_name(self) -> str:
        return "writer"

    def get_system_prompt(self) -> str:
        return (
            "You are the Writer (主笔)。\n"
            "【最高优先】严禁违背用户指令、章节目标、事实摘要和禁忌。\n"
            "职责：\n"
            "1. 基于场景简报撰写正文，严格遵守文风卡与事实约束。\n"
            "2. 不新增设定，若信息不足必须用[TO_CONFIRM:细节]标记。\n"
            "3. 维护角色边界与时间线一致性。\n"
            "原则：章节目标优先，只选取相关卡片/事实；先生成3-6个写作节拍计划，再成文。\n"
            "输出：先输出<plan>节拍，再输出<draft>正文；保持中文叙事，避免重复啰嗦。\n"
            "【再次提醒】宁缺毋滥，不得凭空捏造或违背事实与指令。\n"
        )

    async def execute(self, project_id: str, chapter: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate draft for a chapter."""
        scene_brief = context.get("scene_brief")
        if not scene_brief:
            scene_brief = await self.draft_storage.get_scene_brief(project_id, chapter)

        if not scene_brief:
            return {"success": False, "error": "Scene brief not found"}

        previous_summaries = context.get("previous_summaries")
        context_package = context.get("context_package")
        if previous_summaries is None and context_package:
            previous_summaries = self._build_previous_summaries_from_context(context_package)
        if previous_summaries is None:
            previous_summaries = await self._load_previous_summaries(project_id, chapter)

        style_card = context.get("style_card")
        character_cards = context.get("character_cards") or []
        world_cards = context.get("world_cards") or []
        facts = context.get("facts") or []
        timeline = context.get("timeline") or []
        character_states = context.get("character_states") or []
        chapter_goal = context.get("chapter_goal")
        user_answers = context.get("user_answers") or []
        user_feedback = context.get("user_feedback") or ""

        draft_content = await self._generate_draft(
            scene_brief=scene_brief,
            target_word_count=context.get("target_word_count", 3000),
            previous_summaries=previous_summaries,
            style_card=style_card,
            character_cards=character_cards,
            world_cards=world_cards,
            facts=facts,
            timeline=timeline,
            character_states=character_states,
            chapter_goal=chapter_goal,
            user_answers=user_answers,
            user_feedback=user_feedback,
        )

        pending_confirmations = self._extract_confirmations(draft_content)
        word_count = len(draft_content)

        draft = await self.draft_storage.save_draft(
            project_id=project_id,
            chapter=chapter,
            version="v1",
            content=draft_content,
            word_count=word_count,
            pending_confirmations=pending_confirmations,
        )

        return {
            "success": True,
            "draft": draft,
            "word_count": word_count,
            "pending_confirmations": pending_confirmations,
        }

    async def generate_questions(
        self,
        context_package: Dict[str, Any],
        scene_brief: Any,
        chapter_goal: str
    ) -> List[Dict[str, str]]:
        """Generate pre-writing questions for user confirmation."""
        def get_field(obj, field, default=""):
            if hasattr(obj, field):
                return getattr(obj, field, default)
            if isinstance(obj, dict):
                return obj.get(field, default)
            return default

        brief_chapter = get_field(scene_brief, "chapter", "")
        brief_title = get_field(scene_brief, "title", "")
        brief_goal = get_field(scene_brief, "goal", "")
        brief_characters = get_field(scene_brief, "characters", [])

        characters_text = []
        for char in brief_characters or []:
            if isinstance(char, dict):
                characters_text.append(char.get("name", str(char)))
            elif hasattr(char, "name"):
                characters_text.append(char.name)
            else:
                characters_text.append(str(char))

        context_items = [
            f"Chapter: {brief_chapter}",
            f"Title: {brief_title}",
            f"Goal: {brief_goal or chapter_goal}",
            f"Characters: {', '.join(characters_text) if characters_text else 'None'}",
        ]

        if context_package:
            context_items.append("事实摘要（节选，供反问参考）：")
            for key in ["summary_with_events", "summary_only", "full_facts"]:
                items = context_package.get(key, []) or []
                for item in items[:2]:
                    summary = str(item.get("summary") or "").strip()
                    events = item.get("key_events") or []
                    chapter_id = item.get("chapter") or ""
                    title = item.get("title") or ""
                    if summary or events:
                        block = [f"- {chapter_id} {title}".strip()]
                        if summary:
                            block.append(f"摘要：{summary}")
                        if events:
                            block.append("事件：" + "；".join([str(e) for e in events[:4]]))
                        context_items.append("\n".join(block))

        system_prompt = (
            "你是主笔，写作前必须针对用户指令与事实摘要提出关键反问，"
            "目的是补齐缺失信息、避免违背既有事实与章节目标。"
        )

        user_prompt = (
            "仅返回JSON数组（恰好3条），每条包含 type 与 text。"
            "type 只能是 plot_point / character_change / detail_gap。"
            "围绕章节目标与事实摘要，提出最缺的关键信息，必须具体、可回答、不可空泛。"
        )

        messages = self.build_messages(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_items=context_items,
        )

        try:
            raw = await self.call_llm(messages)
            data = json.loads(raw.strip())
            if isinstance(data, list) and len(data) == 3:
                cleaned = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    q_type = item.get("type")
                    text = item.get("text")
                    if q_type and text:
                        cleaned.append({"type": q_type, "text": text})
                if len(cleaned) == 3:
                    return cleaned
        except Exception:
            pass

        return list(self.DEFAULT_QUESTIONS)

    async def execute_stream(self, project_id: str, chapter: str, context: Dict[str, Any]):
        """Stream draft generation token by token."""
        scene_brief = context.get("scene_brief")
        if not scene_brief:
            yield "[Error: Scene brief not found]"
            return

        messages = self._build_draft_messages(
            scene_brief=scene_brief,
            target_word_count=context.get("target_word_count", 3000),
            previous_summaries=context.get("previous_summaries"),
            style_card=context.get("style_card"),
            character_cards=context.get("character_cards") or [],
            world_cards=context.get("world_cards") or [],
            facts=context.get("facts") or [],
            timeline=context.get("timeline") or [],
            character_states=context.get("character_states") or [],
            chapter_goal=context.get("chapter_goal"),
            user_answers=context.get("user_answers") or [],
            user_feedback=context.get("user_feedback") or "",
            include_plan=False,
        )

        async for chunk in self.call_llm_stream(messages):
            yield chunk

    async def execute_stream_draft(self, project_id: str, chapter: str, context: Dict[str, Any]):
        """Stream draft text only (no plan tags)."""
        scene_brief = context.get("scene_brief")
        if not scene_brief:
            yield "[Error: Scene brief not found]"
            return

        messages = self._build_draft_messages(
            scene_brief=scene_brief,
            target_word_count=context.get("target_word_count", 3000),
            previous_summaries=context.get("previous_summaries"),
            style_card=context.get("style_card"),
            character_cards=context.get("character_cards") or [],
            world_cards=context.get("world_cards") or [],
            facts=context.get("facts") or [],
            timeline=context.get("timeline") or [],
            character_states=context.get("character_states") or [],
            chapter_goal=context.get("chapter_goal"),
            user_answers=context.get("user_answers") or [],
            user_feedback=context.get("user_feedback") or "",
            include_plan=False,
        )

        async for chunk in self.call_llm_stream(messages):
            yield chunk

    async def _load_previous_summaries(self, project_id: str, current_chapter: str) -> List[str]:
        """Load previous summaries."""
        context_package = await self.draft_storage.get_context_for_writing(project_id, current_chapter)
        return self._build_previous_summaries_from_context(context_package)

    def _build_previous_summaries_from_context(self, context_package: Dict[str, Any]) -> List[str]:
        """Build summary blocks from structured context."""
        blocks: List[str] = []

        def add_block(items: List[Dict[str, Any]], fields: List[str]) -> None:
            for item in items:
                parts = [f"{item.get('chapter')}: {item.get('title')}"]
                for field in fields:
                    value = item.get(field)
                    if isinstance(value, list):
                        value = "\n".join([f"- {val}" for val in value]) or "-"
                    if value:
                        parts.append(f"{field}:\n{value}")
                blocks.append("\n".join(parts))

        add_block(context_package.get("full_facts", []), ["summary", "key_events", "open_loops"])
        add_block(context_package.get("summary_with_events", []), ["summary", "key_events"])
        add_block(context_package.get("summary_only", []), ["summary"])
        add_block(context_package.get("title_only", []), [])

        for volume in context_package.get("volume_summaries", []):
            parts = [f"{volume.get('volume_id')}: {volume.get('brief_summary')}"]
            key_themes = volume.get("key_themes") or []
            major_events = volume.get("major_events") or []
            if key_themes:
                parts.append("Key Themes:\n" + "\n".join([f"- {val}" for val in key_themes]))
            if major_events:
                parts.append("Major Events:\n" + "\n".join([f"- {val}" for val in major_events]))
            blocks.append("\n".join(parts))

        return blocks

    async def _generate_draft(
        self,
        scene_brief: Any,
        target_word_count: int,
        previous_summaries: List[str],
        style_card: Any = None,
        character_cards: List[Any] = None,
        world_cards: List[Any] = None,
        facts: List[Any] = None,
        timeline: List[Any] = None,
        character_states: List[Any] = None,
        chapter_goal: str = None,
        user_answers: List[Dict[str, str]] = None,
        user_feedback: str = None,
    ) -> str:
        """Generate draft using LLM."""
        messages = self._build_draft_messages(
            scene_brief=scene_brief,
            target_word_count=target_word_count,
            previous_summaries=previous_summaries,
            style_card=style_card,
            character_cards=character_cards,
            world_cards=world_cards,
            facts=facts,
            timeline=timeline,
            character_states=character_states,
            chapter_goal=chapter_goal,
            user_answers=user_answers,
            user_feedback=user_feedback,
            include_plan=True,
        )

        raw_response = await self.call_llm(messages)
        draft_content = raw_response
        if "<draft>" in raw_response:
            start = raw_response.find("<draft>") + 7
            end = raw_response.find("</draft>")
            if end == -1:
                end = len(raw_response)
            draft_content = raw_response[start:end].strip()

        return draft_content

    def _build_draft_messages(
        self,
        scene_brief: Any,
        target_word_count: int,
        previous_summaries: List[str],
        style_card: Any = None,
        character_cards: List[Any] = None,
        world_cards: List[Any] = None,
        facts: List[Any] = None,
        timeline: List[Any] = None,
        character_states: List[Any] = None,
        chapter_goal: str = None,
        user_answers: List[Dict[str, str]] = None,
        user_feedback: str = None,
        include_plan: bool = True,
    ) -> List[Dict[str, str]]:
        context_items = []

        def get_field(obj, field, default=""):
            if hasattr(obj, field):
                return getattr(obj, field, default)
            if isinstance(obj, dict):
                return obj.get(field, default)
            return default

        if chapter_goal:
            context_items.append(
                "GOAL PRIORITY:\n- " + str(chapter_goal).strip() + "\n"
                "Only write content that serves the goal."
            )

        brief_chapter = get_field(scene_brief, "chapter", "")
        brief_title = get_field(scene_brief, "title", "")
        brief_goal = get_field(scene_brief, "goal", "")
        brief_characters = get_field(scene_brief, "characters", [])
        brief_timeline = get_field(scene_brief, "timeline_context", {})
        brief_constraints = get_field(scene_brief, "world_constraints", [])
        brief_style = get_field(scene_brief, "style_reminder", "")
        brief_forbidden = get_field(scene_brief, "forbidden", [])

        brief_text = f"""Scene Brief:
Chapter: {brief_chapter}
Title: {brief_title}
Goal: {brief_goal}

Characters:
{self._format_characters(brief_characters)}

Timeline Context:
{self._format_dict(brief_timeline)}

World Constraints:
{self._format_list(brief_constraints)}

Style Reminder: {brief_style}

FORBIDDEN:
{self._format_list(brief_forbidden)}
"""
        context_items.append(brief_text)

        if style_card:
            try:
                context_items.append("Style Card:\n" + str(style_card.model_dump()))
            except Exception:
                context_items.append("Style Card:\n" + str(style_card))


        if character_cards:
            lines = ["Character Cards:"]
            for card in character_cards[:10]:
                try:
                    lines.append(str(card.model_dump()))
                except Exception:
                    lines.append(str(card))
            context_items.append("\n".join(lines))

        if world_cards:
            lines = ["World Cards:"]
            for card in world_cards[:10]:
                try:
                    lines.append(str(card.model_dump()))
                except Exception:
                    lines.append(str(card))
            context_items.append("\n".join(lines))

        if facts:
            lines = ["Canon Facts:"]
            for fact in facts[-20:]:
                try:
                    lines.append(str(fact.model_dump()))
                except Exception:
                    lines.append(str(fact))
            context_items.append("\n".join(lines))

        if timeline:
            lines = ["Canon Timeline:"]
            for item in timeline[-20:]:
                try:
                    lines.append(str(item.model_dump()))
                except Exception:
                    lines.append(str(item))
            context_items.append("\n".join(lines))

        if character_states:
            lines = ["Character States:"]
            for state in character_states[:20]:
                try:
                    lines.append(str(state.model_dump()))
                except Exception:
                    lines.append(str(state))
            context_items.append("\n".join(lines))

        if user_answers:
            lines = ["User Answers:"]
            for answer in user_answers:
                if not isinstance(answer, dict):
                    continue
                question = answer.get("question") or answer.get("text") or answer.get("type") or ""
                reply = answer.get("answer") or ""
                if question or reply:
                    lines.append(f"- {question}: {reply}")
            if len(lines) > 1:
                context_items.append("\n".join(lines))

        if user_feedback:
            context_items.append("User Feedback:\n" + str(user_feedback))

        if previous_summaries:
            context_items.append("Previous Chapters:\n" + "\n\n".join(previous_summaries))

        if include_plan:
            user_prompt = f"""【必须遵守】严禁违背用户指令、事实摘要、禁忌；信息缺口用[TO_CONFIRM:细节]标记。
章节目标（最高优先）：{chapter_goal or brief_goal}
目标字数：约 {target_word_count} 字；严格遵守文风提醒与风格卡。

输出格式（先计划后成文）：
<plan>
- 列出3-6个节拍，覆盖冲突、转折、情绪推进，确保达成章节目标
</plan>
<draft>
叙事正文（中文），不要包含计划或任何额外说明
</draft>
"""
            system_prompt = self.get_system_prompt()
        else:
            user_prompt = f"""【必须遵守】严禁违背用户指令、事实摘要、禁忌；信息缺口用[TO_CONFIRM:细节]标记。
章节目标（最高优先）：{chapter_goal or brief_goal}
目标字数：约 {target_word_count} 字；严格遵守文风提醒与风格卡。

输出格式：仅输出叙事正文（中文），不得包含计划或额外标题。
"""
            system_prompt = (
                "你是主笔，仅输出正文草稿；必须遵守事实摘要与禁忌，禁止新增设定。"
            )

        return self.build_messages(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context_items=context_items,
        )

    def _format_characters(self, characters: List[Dict]) -> str:
        if not characters:
            return "None specified"
        lines = []
        for char in characters:
            name = char.get("name", "Unknown")
            state = char.get("current_state", "Normal")
            traits = char.get("relevant_traits", "")
            lines.append(f"- {name}: {state} ({traits})")
        return "\n".join(lines)

    def _format_dict(self, data: Dict) -> str:
        if not data:
            return "None"
        return "\n".join([f"- {key}: {value}" for key, value in data.items()])

    def _format_list(self, items: List) -> str:
        if not items:
            return "None"
        return "\n".join([f"- {item}" for item in items])

    def _extract_confirmations(self, content: str) -> List[str]:
        confirmations = []
        for line in content.split("\n"):
            if "[TO_CONFIRM:" in line:
                start = line.find("[TO_CONFIRM:") + 12
                end = line.find("]", start)
                if end > start:
                    confirmations.append(line[start:end].strip())
        return confirmations
