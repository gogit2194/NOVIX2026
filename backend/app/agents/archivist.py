"""
Archivist Agent
Manages canon data and generates scene briefs and summaries.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml

from app.agents.base import BaseAgent
from app.schemas.canon import Fact, TimelineEvent, CharacterState
from app.schemas.draft import SceneBrief, ChapterSummary, CardProposal
from app.schemas.volume import VolumeSummary
from app.services.llm_config_service import llm_config_service
from app.utils.chapter_id import ChapterIDValidator, normalize_chapter_id
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ArchivistAgent(BaseAgent):
    """Agent responsible for canon management and summaries."""

    MAX_CHARACTERS = 5
    MAX_WORLD_CONSTRAINTS = 5
    MAX_FACTS = 5

    STOPWORDS = {
        "的", "了", "在", "与", "和", "但", "而", "并", "及", "或", "是", "有", "为", "为", "这", "那",
        "一个", "一些", "一种", "可以", "不会", "没有", "不是", "自己", "他们", "她们", "我们", "你们",
        "因为", "所以", "因此", "可能", "需要", "必须", "如果", "然后", "同时", "随着", "对于", "关于",
        "chapter", "goal", "title",
    }

    def get_agent_name(self) -> str:
        return "archivist"

    def get_system_prompt(self) -> str:
        return (
            "You are an Archivist agent for novel writing.\n\n"
            "Your responsibilities:\n"
            "1. Maintain facts, timeline, and character states\n"
            "2. Generate scene briefs for writers based on chapter goals\n"
            "3. Detect conflicts between new content and existing canon\n"
            "4. Ensure consistency across the story\n\n"
            "Core principle:\n"
            "- Chapter goal is the primary driver. Cards/canon are constraints and a knowledge base.\n"
            "- Do NOT try to cover every card in every chapter. Select only what is relevant.\n"
            "- Prefer clarity and actionability over completeness.\n\n"
            "Output Format:\n"
            "- Generate scene briefs in JSON format\n"
            "- Include relevant context only (not exhaustive)\n"
            "- Flag any conflicts or inconsistencies\n"
        )

    async def execute(self, project_id: str, chapter: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a scene brief for a chapter using algorithmic context."""
        style_card = await self.card_storage.get_style_card(project_id)

        chapter_id = normalize_chapter_id(chapter) or chapter
        chapter_title = context.get("chapter_title", "")
        chapter_goal = context.get("chapter_goal", "")

        recent_chapters = await self._get_previous_chapters(project_id, chapter_id, limit=5)
        recent_fact_chapters = recent_chapters[-2:]
        summary_chapters = recent_chapters[:-2]

        summary_blocks = await self._build_summary_blocks(project_id, summary_chapters)
        timeline_events = await self.canon_storage.get_timeline_events_near_chapter(
            project_id=project_id,
            chapter=chapter_id,
            window=3,
            max_events=10,
        )

        instruction_text = " ".join([chapter_title, chapter_goal])
        keywords = self._extract_keywords(" ".join([instruction_text] + summary_blocks))

        chapter_texts = await self._load_chapter_texts(project_id, recent_fact_chapters)
        mentioned_characters = await self._extract_mentions_from_texts(
            project_id=project_id,
            texts=chapter_texts,
            card_type="character",
        )
        mentioned_worlds = await self._extract_mentions_from_texts(
            project_id=project_id,
            texts=chapter_texts,
            card_type="world",
        )

        instruction_characters = await self._extract_mentions_from_texts(
            project_id=project_id,
            texts=[instruction_text],
            card_type="character",
        )
        instruction_worlds = await self._extract_mentions_from_texts(
            project_id=project_id,
            texts=[instruction_text],
            card_type="world",
        )

        character_names = context.get("characters", []) or []
        selected_character_names = self._merge_unique(
            mentioned_characters,
            instruction_characters,
            character_names,
        )
        characters = await self._build_character_context(project_id, selected_character_names)

        world_names = self._merge_unique(mentioned_worlds, instruction_worlds)
        world_constraints = await self._build_world_constraints_from_names(project_id, world_names)

        facts = await self._collect_facts_for_chapters(project_id, recent_fact_chapters)
        extra_facts = await self._select_facts_by_instruction(
            project_id=project_id,
            keywords=keywords,
            exclude_ids={fact.get("id") for fact in facts if fact.get("id")},
            max_extra=5,
        )
        facts.extend(extra_facts)

        style_reminder = self._build_style_reminder(style_card)
        timeline_context = self._build_timeline_context_from_summaries(
            chapter_goal=chapter_goal,
            summaries=summary_blocks,
            fallback_events=timeline_events,
        )

        scene_brief = SceneBrief(
            chapter=chapter_id,
            title=chapter_title or f"Chapter {chapter_id}",
            goal=chapter_goal,
            characters=characters,
            timeline_context=timeline_context,
            world_constraints=world_constraints,
            facts=[fact.get("statement") for fact in facts if fact.get("statement")],
            style_reminder=style_reminder,
            forbidden=[],
        )

        await self.draft_storage.save_scene_brief(project_id, chapter_id, scene_brief)

        return {
            "success": True,
            "scene_brief": scene_brief,
            "conflicts": [],
        }

    async def _build_character_context(self, project_id: str, names: List[str]) -> List[Dict[str, str]]:
        characters = []
        for name in names:
            card = await self.card_storage.get_character_card(project_id, name)
            if not card:
                continue
            traits = card.description
            characters.append(
                {
                    "name": card.name,
                    "relevant_traits": traits,
                }
            )
        return characters

    def _build_timeline_context_from_summaries(
        self,
        chapter_goal: str,
        summaries: List[str],
        fallback_events: List[Any],
    ) -> Dict[str, str]:
        before = summaries[-1] if summaries else ""
        if not before and fallback_events:
            event = fallback_events[-1]
            before = f"{event.time}: {event.event} @ {event.location}"
        return {
            "before": before,
            "current": chapter_goal,
            "after": "",
        }

    def _extract_participants(self, events: List[Any]) -> List[str]:
        names = []
        for event in events:
            participants = getattr(event, "participants", []) or []
            for name in participants:
                if name and name not in names:
                    names.append(name)
        return names

    async def _build_world_constraints(self, project_id: str, limit: int) -> List[str]:
        constraints = []
        names = await self.card_storage.list_world_cards(project_id)
        for name in names[:limit]:
            card = await self.card_storage.get_world_card(project_id, name)
            if not card:
                continue
            if card.description:
                constraints.append(f"{card.name}: {card.description}")
        return constraints

    def _extract_keywords(self, text: str) -> List[str]:
        if not text:
            return []
        candidates = re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,}", text)
        keywords = []
        for token in candidates:
            if token in self.STOPWORDS:
                continue
            if token not in keywords:
                keywords.append(token)
        return keywords

    def _score_text_match(self, text: str, keywords: List[str]) -> int:
        if not text or not keywords:
            return 0
        score = 0
        for kw in keywords:
            if kw and kw in text:
                score += 1
        return score

    async def _get_previous_chapters(
        self,
        project_id: str,
        current_chapter: str,
        limit: int,
    ) -> List[str]:
        chapters = await self.draft_storage.list_chapters(project_id)
        current_weight = ChapterIDValidator.calculate_weight(current_chapter)
        previous = [ch for ch in chapters if ChapterIDValidator.calculate_weight(ch) < current_weight]
        return previous[-limit:]

    async def _build_summary_blocks(self, project_id: str, chapters: List[str]) -> List[str]:
        blocks: List[str] = []
        for ch in chapters:
            summary = await self.draft_storage.get_chapter_summary(project_id, ch)
            if not summary:
                continue
            title = summary.title or ch
            brief = summary.brief_summary or ""
            blocks.append(f"{ch}: {title}\n{brief}".strip())
        return blocks

    async def _load_chapter_texts(self, project_id: str, chapters: List[str]) -> List[str]:
        texts = []
        for ch in chapters:
            final = await self.draft_storage.get_final_draft(project_id, ch)
            if final:
                texts.append(final)
                continue
            versions = await self.draft_storage.list_draft_versions(project_id, ch)
            if not versions:
                texts.append("")
                continue
            latest = versions[-1]
            draft = await self.draft_storage.get_draft(project_id, ch, latest)
            texts.append(draft.content if draft else "")
        return texts

    async def _extract_mentions_from_texts(
        self,
        project_id: str,
        texts: List[str],
        card_type: str,
    ) -> List[str]:
        names = []
        if card_type == "character":
            names = await self.card_storage.list_character_cards(project_id)
        elif card_type == "world":
            names = await self.card_storage.list_world_cards(project_id)
        if not names:
            return []

        mentioned = []
        for name in names:
            for text in texts:
                if name and text and name in text:
                    mentioned.append(name)
                    break
        return mentioned

    def _merge_unique(self, *groups: List[str]) -> List[str]:
        merged: List[str] = []
        for group in groups:
            for name in group or []:
                if name and name not in merged:
                    merged.append(name)
        return merged

    async def _build_world_constraints_from_names(
        self,
        project_id: str,
        names: List[str],
    ) -> List[str]:
        constraints = []
        for name in names:
            card = await self.card_storage.get_world_card(project_id, name)
            if not card:
                continue
            description = card.description or ""
            constraints.append(f"{card.name}: {description}".strip())
        return constraints

    async def _collect_facts_for_chapters(
        self,
        project_id: str,
        chapters: List[str],
    ) -> List[Dict[str, Any]]:
        if not chapters:
            return []
        chapter_set = {normalize_chapter_id(ch) for ch in chapters if ch}
        facts = await self.canon_storage.get_all_facts_raw(project_id)
        selected = []
        for fact in facts:
            raw_chapter = fact.get("introduced_in") or fact.get("source") or ""
            fact_chapter = normalize_chapter_id(raw_chapter)
            if fact_chapter in chapter_set:
                selected.append(fact)
        return selected

    async def _select_facts_by_instruction(
        self,
        project_id: str,
        keywords: List[str],
        exclude_ids: set,
        max_extra: int,
    ) -> List[Dict[str, Any]]:
        if not keywords:
            return []
        facts = await self.canon_storage.get_all_facts_raw(project_id)
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for fact in facts:
            if fact.get("id") in exclude_ids:
                continue
            statement = str(fact.get("statement") or fact.get("content") or "")
            score = self._score_text_match(statement, keywords)
            if score > 0:
                scored.append((score, fact))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in scored[:max_extra]]

    async def _select_character_names(
        self,
        project_id: str,
        chapter_id: str,
        keywords: List[str],
        explicit_names: List[str],
        timeline_events: List[Any],
    ) -> List[str]:
        names = await self.card_storage.list_character_cards(project_id)
        name_scores: Dict[str, int] = {}
        explicit_set = [n for n in explicit_names if n]
        for name in explicit_set:
            name_scores[name] = name_scores.get(name, 0) + 100

        for event in timeline_events or []:
            for name in getattr(event, "participants", []) or []:
                if name:
                    name_scores[name] = name_scores.get(name, 0) + 10

        for name in names:
            score = 0
            if name in keywords:
                score += 5
            score += self._score_text_match(name, keywords)
            if score > 0:
                name_scores[name] = max(name_scores.get(name, 0), score)

        ranked = sorted(name_scores.items(), key=lambda x: x[1], reverse=True)
        selected = [name for name, _ in ranked][: self.MAX_CHARACTERS]
        return selected

    async def _select_relevant_facts(
        self,
        project_id: str,
        chapter_id: str,
        keywords: List[str],
    ) -> List[Dict[str, Any]]:
        all_facts = await self.canon_storage.get_all_facts_raw(project_id)
        if not all_facts:
            return []

        parsed_current = ChapterIDValidator.parse(chapter_id)
        previous_same_volume: Optional[str] = None
        if parsed_current and parsed_current.get("volume") and parsed_current.get("chapter") is not None:
            chapters = await self.draft_storage.list_chapters(project_id)
            candidates = []
            for ch in chapters:
                parsed = ChapterIDValidator.parse(ch)
                if not parsed or parsed.get("volume") != parsed_current.get("volume"):
                    continue
                if parsed.get("chapter", 0) < parsed_current.get("chapter", 0):
                    candidates.append((parsed.get("chapter", 0), ch))
            if candidates:
                previous_same_volume = max(candidates, key=lambda x: x[0])[1]

        selected: List[Dict[str, Any]] = []
        remaining = []

        for fact in all_facts:
            fact_chapter = normalize_chapter_id(
                fact.get("introduced_in") or fact.get("source") or ""
            )
            if previous_same_volume and fact_chapter == previous_same_volume:
                selected.append(fact)
            else:
                remaining.append(fact)

        if len(selected) < self.MAX_FACTS:
            scored: List[Tuple[int, Dict[str, Any]]] = []
            for fact in remaining:
                statement = str(fact.get("statement") or fact.get("content") or "")
                fact_chapter = normalize_chapter_id(
                    fact.get("introduced_in") or fact.get("source") or ""
                )
                dist = ChapterIDValidator.calculate_distance(chapter_id, fact_chapter) if fact_chapter else 999
                recency = max(0, 10 - min(dist, 10))
                match = self._score_text_match(statement, keywords) * 2
                score = recency + match
                if score > 0:
                    scored.append((score, fact))
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, fact in scored:
                if len(selected) >= self.MAX_FACTS:
                    break
                selected.append(fact)

        return selected[: self.MAX_FACTS]

    async def _select_world_constraints(
        self,
        project_id: str,
        keywords: List[str],
        facts: List[Dict[str, Any]],
        summaries: List[str],
    ) -> List[str]:
        names = await self.card_storage.list_world_cards(project_id)
        if not names:
            return []

        facts_text = " ".join([str(f.get("statement") or "") for f in facts])
        summary_text = " ".join(summaries)
        combined = " ".join([facts_text, summary_text])
        combined_keywords = list(dict.fromkeys(keywords + self._extract_keywords(combined)))

        scored: List[Tuple[int, str]] = []
        for name in names:
            card = await self.card_storage.get_world_card(project_id, name)
            if not card:
                continue
            text = f"{card.name} {card.description or ''}"
            score = 0
            if card.name and card.name in combined:
                score += 5
            score += self._score_text_match(text, combined_keywords)
            if score > 0:
                scored.append((score, f"{card.name}: {card.description or ''}".strip()))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored][: self.MAX_WORLD_CONSTRAINTS]

    def _build_style_reminder(self, style_card: Any) -> str:
        if not style_card:
            return ""
        style_text = getattr(style_card, "style", "") or ""
        return style_text.strip()



    async def detect_setting_changes(self, draft_content: str, existing_card_names: List[str]) -> List[CardProposal]:
        """Detect potential new setting cards with pure heuristics (no LLM)."""
        existing = {name for name in (existing_card_names or []) if name}
        proposals: List[CardProposal] = []

        text = draft_content or ""
        if not text.strip():
            return proposals

        sentences = self._split_sentences(text)

        world_candidates = self._extract_world_candidates(text)
        character_candidates = self._extract_character_candidates(text)

        proposals.extend(
            self._build_card_proposals(
                candidates=world_candidates,
                card_type="World",
                existing=existing,
                sentences=sentences,
                min_count=2,
            )
        )
        proposals.extend(
            self._build_card_proposals(
                candidates=character_candidates,
                card_type="Character",
                existing=existing,
                sentences=sentences,
                min_count=1,
            )
        )

        return proposals

    def _split_sentences(self, text: str) -> List[str]:
        parts = re.split(r"[。！？\\n]", text)
        return [p.strip() for p in parts if p.strip()]

    def _extract_world_candidates(self, text: str) -> Dict[str, int]:
        suffixes = "帮|派|门|宗|城|山|谷|镇|村|府|馆|寺|庙|观|宫|殿|岛|关|寨|营|会|国|州|郡|湾|湖|河"
        pattern = re.compile(rf"([\\u4e00-\\u9fff]{{2,8}}(?:{suffixes}))")
        counts: Dict[str, int] = {}
        for match in pattern.findall(text):
            counts[match] = counts.get(match, 0) + 1
        return counts

    def _extract_character_candidates(self, text: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        if not text:
            return counts

        say_pattern = re.compile(r"([\\u4e00-\\u9fff]{2,3})(?:\\s*)(?:说道|问道|答道|笑道|喝道|低声道|沉声道|道)")
        action_verbs = "走|看|望|想|叹|笑|皱|点头|摇头|转身|停下|沉默|开口|伸手|拔剑|抬眼"
        action_pattern = re.compile(rf"([\\u4e00-\\u9fff]{{2,3}})(?:\\s*)(?:{action_verbs})")

        for match in say_pattern.findall(text):
            if match in self.STOPWORDS:
                continue
            counts[match] = counts.get(match, 0) + 2

        for match in action_pattern.findall(text):
            if match in self.STOPWORDS:
                continue
            counts[match] = counts.get(match, 0) + 1

        return counts

    def _build_card_proposals(
        self,
        candidates: Dict[str, int],
        card_type: str,
        existing: set,
        sentences: List[str],
        min_count: int = 2,
    ) -> List[CardProposal]:
        proposals: List[CardProposal] = []
        for name, count in candidates.items():
            if not name or name in existing:
                continue
            if count < min_count:
                continue
            source_sentence = ""
            for sent in sentences:
                if name in sent:
                    source_sentence = sent
                    break
            if not source_sentence:
                continue
            confidence = min(0.9, 0.5 + 0.1 * min(count, 4))
            proposals.append(
                CardProposal(
                    name=name,
                    type=card_type,
                    description=source_sentence,
                    rationale=f"在本章中多次出现（{count} 次），具备可复用设定价值。",
                    source_text=source_sentence,
                    confidence=confidence,
                )
            )
        return proposals

    async def extract_style_profile(self, sample_text: str) -> str:
        """Extract writing style guidance from sample text."""
        provider = self.gateway.get_provider_for_agent(self.get_agent_name())
        if provider == "mock":
            return ""

        user_prompt = f"""请从示例文本中提炼“文风指导”。
要求（先读完再输出）：
- 用中文，结构化分条总结：视角/叙述人称、基调与情绪、节奏、用词/句式、意象与细节偏好。
- 只给可操作的写作要点，不要复述原文剧情，不要出现人物姓名/专名。
- 精炼但具体，每条一句。

示例文本：
{sample_text[:15000]}
"""
        messages = self.build_messages(
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            context_items=None,
        )
        response = await self.call_llm(messages)
        return str(response or "").strip()

    async def extract_fanfiction_card(self, title: str, content: str) -> Dict[str, str]:
        """Extract a single card summary for fanfiction import."""
        clean_title = str(title or "").strip()
        clean_content = str(content or "").strip()
        if not clean_content:
            return {
                "name": clean_title or "Unknown",
                "type": self._infer_card_type_from_title(clean_title),
                "description": "",
            }

        user_prompt = f"""你在把百科/词条页面转换为“设定卡”。
只输出 JSON 对象，字段：name, type, description。type 取 Character 或 World。

描述写法（至关重要，先读完再写）：
- 中文，多句（3-6句），结构化地概括身份/外貌（如有）/性格/角色功能等核心特征，像人物小传。
- 不要剧情复述；聚焦设定画像，覆盖全方位特征。
- 不得抄袭原文，改写且避免任意12字连续重合；句子不可重复。
- 忽略玩法/技能/版本/宣传等无关信息；忽略表格标题等噪声。
- 默认用页面标题为 name，除非正文有更合适的正式名称。
- 禁用任何“Title:”“Summary:”“Table”等标签字样。

Page Title: {clean_title}

Page Content:
{clean_content[:24000]}
"""

        provider_id = self.gateway.get_provider_for_agent(self.get_agent_name())
        profile = llm_config_service.get_profile_by_id(provider_id) or {}
        logger.info(
            "Fanfiction extraction using provider=%s model=%s content_chars=%s",
            provider_id,
            profile.get("model"),
            len(clean_content),
        )

        messages = self.build_messages(
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            context_items=None,
        )

        max_attempts = 5
        last_description = ""
        last_length = 0
        for attempt in range(1, max_attempts + 1):
            response = await self.call_llm(messages, max_tokens=1400)
            logger.info("Fanfiction extraction response_chars=%s", len(response or ""))
            parsed = self._parse_json_object(response)
            if not self._is_valid_fanfiction_payload(parsed, clean_content):
                logger.info("Fanfiction extraction JSON parse failed, retrying with strict prompt")
                parsed = await self._extract_fanfiction_json_from_content(
                    clean_title,
                    clean_content,
                    hint="请严格输出JSON，描述需覆盖身份/外貌（如有）/性格/角色功能，多句完整描述，避免重复与抄袭。",
                )

            if not self._is_valid_fanfiction_payload(parsed, clean_content):
                continue

            name = str(parsed.get("name") or clean_title or "Unknown").strip()
            card_type = str(parsed.get("type") or "").strip() or self._infer_card_type_from_title(name)
            description = self._sanitize_fanfiction_description(str(parsed.get("description") or "").strip())
            last_description = description
            last_length = len(description)

            if not description or self._is_copied_from_source(description, clean_content):
                parsed = await self._extract_fanfiction_json_from_content(
                    name,
                    clean_content,
                    hint="描述需涵盖身份、外貌（如有）、性格、角色功能等要点，多句完整描述，避免重复，确保具体。",
                )
                if self._is_valid_fanfiction_payload(parsed, clean_content):
                    description = self._sanitize_fanfiction_description(str(parsed.get("description") or "").strip())
                    last_description = description
                    last_length = len(description)
                if not description or self._is_copied_from_source(description, clean_content):
                    continue

            if card_type not in {"Character", "World"}:
                card_type = self._infer_card_type_from_title(name)

            return {
                "name": name,
                "type": card_type,
                "description": description,
            }

        # 兜底：尝试从原文提取基础摘要
        fallback_desc = self._build_fanfiction_fallback(clean_title, clean_content)
        fallback_desc = self._sanitize_fanfiction_description(fallback_desc)
        if fallback_desc:
            return {
                "name": clean_title or "Unknown",
                "type": self._infer_card_type_from_title(clean_title),
                "description": fallback_desc,
            }
        raise ValueError(f"Fanfiction extraction failed: empty description (len={last_length})")

    async def _extract_fanfiction_json_from_content(
        self,
        title: str,
        content: str,
        hint: str = "",
    ) -> Dict[str, Any]:
        if not content:
            return {}
        extra_hint = f"\nAdditional Hint:\n{hint}\n" if hint else ""
        repair_prompt = f"""Convert the following wiki content into a strict JSON object with fields: name, type, description.

Rules:
- Output JSON only. No extra text.
- type must be Character or World.
- description 必须是中文，多句完整描述（建议3-6句），覆盖身份/外貌/性格/角色功能等信息，句子不重复，务必具体。
- Do NOT include labels like "Title:", "Summary:", "Table", "RawText".
- Do NOT reuse any sequence of 12+ consecutive characters from the page.
- 使用多句完整描述，覆盖身份、外貌（如有）、性格、角色功能等要点。
{extra_hint}
Page Title: {title}

Page Content:
{content[:24000]}
"""
        messages = self.build_messages(
            system_prompt=self.get_system_prompt(),
            user_prompt=repair_prompt,
            context_items=None,
        )
        response = await self.call_llm(messages, max_tokens=1200)
        return self._parse_json_object(response)

    

    def _is_valid_fanfiction_payload(self, payload: Dict[str, Any], source: str = "") -> bool:
        if not isinstance(payload, dict):
            return False
        name = str(payload.get("name") or "").strip()
        card_type = str(payload.get("type") or "").strip()
        description = str(payload.get("description") or "").strip()
        if not name or not description:
            return False
        if card_type not in {"Character", "World"}:
            return False
        if source and self._is_copied_from_source(description, source):
            return False
        return True

    def _is_copied_from_source(self, description: str, source: str = "") -> bool:
        if not description or not source:
            return False
        text = description.strip()
        if len(text) < 20:
            return False
        if text in source:
            return True
        window = 12
        hits = 0
        for i in range(0, len(text) - window + 1, 4):
            frag = text[i : i + window]
            if frag and frag in source:
                hits += 1
                if hits >= 2:
                    return True
        return False

    def _parse_json_object(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        cleaned = text.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            if len(parts) >= 2:
                cleaned = parts[1]
        cleaned = cleaned.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                return json.loads(cleaned)
            except Exception:
                return {}
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except Exception:
                return {}
        return {}

    def _truncate_description(self, text: str, limit: int = 800) -> str:
        if not text:
            return ""
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean) <= limit:
            return clean
        return clean[:limit].rstrip()

    def _fallback_fanfiction_description(self, content: str) -> str:
        summary = ""
        summary_match = re.search(r"Summary:\s*(.+?)(?:\n\n|$)", content, re.IGNORECASE | re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()
        summary = self._sanitize_fanfiction_description(summary)
        if summary:
            return self._truncate_description(summary, limit=800)
        clean = re.sub(r"\s+", " ", content).strip()
        clean = self._sanitize_fanfiction_description(clean)
        return self._truncate_description(clean, limit=800)

    def _sanitize_fanfiction_description(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text
        cleaned = re.sub(r"\bTitle:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bSummary:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bTable\s*\d*:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bRawText:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*\|\s*", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # 去重相邻句子，减少重复
        sentences = re.split(r"(?<=[。！？!?.])", cleaned)
        deduped = []
        seen = set()
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            key = s[:20]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(s)
        result = "".join(deduped)
        return result


    def _extract_llm_section(self, content: str, label: str) -> str:
        if not content or not label:
            return ""
        pattern = re.compile(rf"{re.escape(label)}:\s*(.+?)(?:\n\n[A-Z][A-Za-z ]+:\s*|\Z)", re.DOTALL)
        match = pattern.search(content)
        return match.group(1).strip() if match else ""

    def _build_fanfiction_fallback(self, title: str, content: str) -> str:
        summary = self._extract_llm_section(content, "Summary")
        summary = self._sanitize_fanfiction_description(summary)
        if summary and len(summary) >= 60:
            return self._truncate_description(summary, limit=800)

        infobox = self._extract_llm_section(content, "Infobox")
        infobox = self._sanitize_fanfiction_description(infobox)
        info_lines = []
        if infobox:
            for line in infobox.split("\n"):
                line = line.strip("- ").strip()
                if not line:
                    continue
                key_lower = line.split(":")[0].lower() if ":" in line else line.lower()
                if any(k in key_lower for k in ["姓名", "本名", "别名", "身份", "职业", "性别", "所属", "阵营", "种族", "配音"]):
                    info_lines.append(line)
        if info_lines:
            combined = f"{title}，" + "，".join(info_lines)
            return self._truncate_description(self._sanitize_fanfiction_description(combined), limit=800)

        return self._fallback_fanfiction_description(content)

    def _infer_card_type_from_title(self, title: str) -> str:
        text = title or ""
        world_suffixes = (
            "城",
            "国",
            "派",
            "门",
            "宗",
            "山",
            "谷",
            "镇",
            "村",
            "府",
            "馆",
            "寺",
            "宫",
            "湖",
            "河",
            "岛",
            "大陆",
            "组织",
            "学院",
        )
        if any(text.endswith(suffix) for suffix in world_suffixes):
            return "World"
        return "Character"

    async def generate_chapter_summary(
        self,
        project_id: str,
        chapter: str,
        chapter_title: str,
        final_draft: str,
    ) -> ChapterSummary:
        """Generate a structured chapter summary."""
        provider = self.gateway.get_provider_for_agent(self.get_agent_name())
        if provider == "mock":
            return self._fallback_chapter_summary(chapter, chapter_title, final_draft)

        yaml_content = await self._generate_chapter_summary_yaml(
            chapter=chapter,
            chapter_title=chapter_title,
            final_draft=final_draft,
        )

        return self._parse_chapter_summary(yaml_content, chapter, chapter_title, final_draft)

    async def generate_volume_summary(
        self,
        project_id: str,
        volume_id: str,
        chapter_summaries: List[ChapterSummary],
    ) -> VolumeSummary:
        """Generate or refresh a volume summary."""
        chapter_count = len(chapter_summaries)
        provider = self.gateway.get_provider_for_agent(self.get_agent_name())

        if provider == "mock" or chapter_count == 0:
            return self._fallback_volume_summary(volume_id, chapter_summaries)

        yaml_content = await self._generate_volume_summary_yaml(volume_id, chapter_summaries)
        return self._parse_volume_summary(yaml_content, volume_id, chapter_summaries)

    async def extract_canon_updates(self, project_id: str, chapter: str, final_draft: str) -> Dict[str, Any]:
        """Extract canon updates from the final draft."""
        provider = self.gateway.get_provider_for_agent(self.get_agent_name())
        if provider == "mock":
            return {"facts": [], "timeline_events": [], "character_states": []}

        try:
            yaml_content = await self._generate_canon_updates_yaml(chapter=chapter, final_draft=final_draft)
            return await self._parse_canon_updates_yaml(
                project_id=project_id,
                chapter=chapter,
                yaml_content=yaml_content,
            )
        except Exception:
            return {"facts": [], "timeline_events": [], "character_states": []}

    async def _generate_canon_updates_yaml(self, chapter: str, final_draft: str) -> str:
        """Generate canon updates YAML via LLM."""
        user_prompt = f"""从最终稿中提取可落库的“事实/时间线/角色状态”更新，输出 YAML。
章节：{chapter}

模板：
```yaml
facts:
  - statement: <客观事实，精炼句子>
    confidence: <0.0-1.0>
timeline_events:
  - time: <时间描述>
    event: <发生了什么>
    participants: [<角色1>, <角色2>]
    location: <地点>
character_states:
  - character: <角色名>
    goals: [<目标1>]
    injuries: [<伤势1>]
    inventory: [<物品1>]
    relationships: {{ <他人>: <关系描述> }}
    location: <当前位置>
    emotional_state: <情绪>
```

规则：
- 只写能从正文推断的客观信息；不捏造。
- facts 以3-5条为宜，聚焦关键设定/剧情。
- 不确定的字段留空或空列表。

正文：
""" + final_draft

        messages = self.build_messages(
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            context_items=None,
        )
        response = await self.call_llm(messages)

        if "```yaml" in response:
            yaml_start = response.find("```yaml") + 7
            yaml_end = response.find("```", yaml_start)
            response = response[yaml_start:yaml_end].strip()
        elif "```" in response:
            yaml_start = response.find("```") + 3
            yaml_end = response.find("```", yaml_start)
            response = response[yaml_start:yaml_end].strip()

        return response

    async def _parse_canon_updates_yaml(
        self,
        project_id: str,
        chapter: str,
        yaml_content: str,
    ) -> Dict[str, Any]:
        """Parse canon update YAML."""
        data = yaml.safe_load(yaml_content) or {}

        existing_facts = await self.canon_storage.get_all_facts(project_id)
        next_fact_index = len(existing_facts) + 1

        facts: List[Fact] = []
        for item in data.get("facts", []) or []:
            statement = ""
            confidence = 1.0
            if isinstance(item, str):
                statement = item
            elif isinstance(item, dict):
                statement = str(item.get("statement", "") or "")
                conf_raw = item.get("confidence")
                try:
                    confidence = float(conf_raw) if conf_raw is not None else 1.0
                except Exception:
                    confidence = 1.0

            if not statement.strip():
                continue

            fact_id = f"F{next_fact_index:04d}"
            next_fact_index += 1
            facts.append(
                Fact(
                    id=fact_id,
                    statement=statement.strip(),
                    source=chapter,
                    introduced_in=chapter,
                    confidence=max(0.0, min(1.0, confidence)),
                )
            )

        timeline_events: List[TimelineEvent] = []
        for item in data.get("timeline_events", []) or []:
            if not isinstance(item, dict):
                continue
            timeline_events.append(
                TimelineEvent(
                    time=str(item.get("time", "") or ""),
                    event=str(item.get("event", "") or ""),
                    participants=list(item.get("participants", []) or []),
                    location=str(item.get("location", "") or ""),
                    source=chapter,
                )
            )

        character_states: List[CharacterState] = []
        for item in data.get("character_states", []) or []:
            if not isinstance(item, dict):
                continue
            character = str(item.get("character", "") or "").strip()
            if not character:
                continue
            character_states.append(
                CharacterState(
                    character=character,
                    goals=list(item.get("goals", []) or []),
                    injuries=list(item.get("injuries", []) or []),
                    inventory=list(item.get("inventory", []) or []),
                    relationships=dict(item.get("relationships", {}) or {}),
                    location=item.get("location"),
                    emotional_state=item.get("emotional_state"),
                    last_seen=chapter,
                )
            )

        return {
            "facts": facts,
            "timeline_events": timeline_events,
            "character_states": character_states,
        }

    async def _generate_chapter_summary_yaml(
        self,
        chapter: str,
        chapter_title: str,
        final_draft: str,
    ) -> str:
        """Generate ChapterSummary YAML via LLM."""
        user_prompt = f"""请用 YAML 结构化生成本章“事实摘要”。
章节：{chapter}
标题：{chapter_title}

严格匹配下列键名：
```yaml
chapter: {chapter}
title: {chapter_title}
word_count: <int>              # 估算字数即可
key_events:                    # 3-5条，客观剧情节点
  - <event1>
new_facts:                     # 3-5条，关键设定/情节事实，避免琐碎小人物小事
  - <fact1>
character_state_changes:       # 主要人物的心理/关系/目标变化
  - <change1>
open_loops:                    # 未解决的悬念/伏笔
  - <loop1>
brief_summary: <一段话摘要，聚焦剧情与重要人物心理>
```

规则：
- 只记录客观剧情与主要人物心理，不写无关路人或枝节。
- 用中文，精炼但具体；避免抄全文。
- 仅输出 YAML，无额外文本。

正文：
""" + final_draft

        messages = self.build_messages(
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            context_items=None,
        )

        response = await self.call_llm(messages)

        if "```yaml" in response:
            yaml_start = response.find("```yaml") + 7
            yaml_end = response.find("```", yaml_start)
            response = response[yaml_start:yaml_end].strip()
        elif "```" in response:
            yaml_start = response.find("```") + 3
            yaml_end = response.find("```", yaml_start)
            response = response[yaml_start:yaml_end].strip()

        return response

    async def _generate_volume_summary_yaml(
        self,
        volume_id: str,
        chapter_summaries: List[ChapterSummary],
    ) -> str:
        """Generate VolumeSummary YAML via LLM."""
        items = []
        for summary in chapter_summaries:
            items.append(
                {
                    "chapter": summary.chapter,
                    "title": summary.title,
                    "brief_summary": summary.brief_summary,
                    "key_events": summary.key_events,
                    "open_loops": summary.open_loops,
                }
            )

        user_prompt = f"""Generate a structured volume summary in YAML.

Volume: {volume_id}
Chapter count: {len(chapter_summaries)}

Chapter summaries JSON:
{json.dumps(items, ensure_ascii=True)}

Output YAML matching this schema:
```yaml
volume_id: {volume_id}
brief_summary: <one paragraph summary>
key_themes:
  - <theme1>
major_events:
  - <event1>
chapter_count: {len(chapter_summaries)}
```

Constraints:
- Summaries must be concise and consistent.
- Output YAML only, no extra text.
"""

        messages = self.build_messages(
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            context_items=None,
        )

        response = await self.call_llm(messages)

        if "```yaml" in response:
            yaml_start = response.find("```yaml") + 7
            yaml_end = response.find("```", yaml_start)
            response = response[yaml_start:yaml_end].strip()
        elif "```" in response:
            yaml_start = response.find("```") + 3
            yaml_end = response.find("```", yaml_start)
            response = response[yaml_start:yaml_end].strip()

        return response

    def _parse_volume_summary(
        self,
        yaml_content: str,
        volume_id: str,
        chapter_summaries: List[ChapterSummary],
    ) -> VolumeSummary:
        """Parse YAML into a VolumeSummary."""
        try:
            data = yaml.safe_load(yaml_content) or {}
            data["volume_id"] = volume_id
            data.setdefault("brief_summary", "")
            data.setdefault("key_themes", [])
            data.setdefault("major_events", [])
            data["chapter_count"] = len(chapter_summaries)
            data.setdefault("created_at", datetime.now())
            data["updated_at"] = datetime.now()
            return VolumeSummary(**data)
        except Exception:
            return self._fallback_volume_summary(volume_id, chapter_summaries)

    def _fallback_volume_summary(
        self,
        volume_id: str,
        chapter_summaries: List[ChapterSummary],
    ) -> VolumeSummary:
        """Fallback volume summary without LLM."""
        brief_parts = [s.brief_summary for s in chapter_summaries if s.brief_summary]
        brief_summary = " ".join(brief_parts)[:800]
        events = []
        for summary in chapter_summaries:
            events.extend(summary.key_events or [])
        major_events = list(dict.fromkeys([e for e in events if e]))[:20]

        return VolumeSummary(
            volume_id=volume_id,
            brief_summary=brief_summary,
            key_themes=[],
            major_events=major_events,
            chapter_count=len(chapter_summaries),
        )

    def _parse_chapter_summary(
        self,
        yaml_content: str,
        chapter: str,
        chapter_title: str,
        final_draft: str,
    ) -> ChapterSummary:
        """Parse YAML into ChapterSummary."""
        try:
            data = yaml.safe_load(yaml_content) or {}
            data["chapter"] = chapter
            data["title"] = data.get("title") or chapter_title
            data.setdefault("word_count", len(final_draft))
            data.setdefault("key_events", [])
            data.setdefault("new_facts", [])
            data.setdefault("character_state_changes", [])
            data.setdefault("open_loops", [])
            data.setdefault("brief_summary", "")
            return ChapterSummary(**data)
        except Exception:
            return self._fallback_chapter_summary(chapter, chapter_title, final_draft)

    def _fallback_chapter_summary(
        self,
        chapter: str,
        chapter_title: str,
        final_draft: str,
    ) -> ChapterSummary:
        """Fallback summary without LLM."""
        brief = final_draft.strip().replace("\r\n", "\n")
        brief = brief[:400] + ("..." if len(brief) > 400 else "")

        return ChapterSummary(
            chapter=chapter,
            title=chapter_title or chapter,
            word_count=len(final_draft),
            key_events=[],
            new_facts=[],
            character_state_changes=[],
            open_loops=[],
            brief_summary=brief,
        )












