# -*- coding: utf-8 -*-
"""
文枢 WenShape - 深度上下文感知的智能体小说创作系统
WenShape - Deep Context-Aware Agent-Based Novel Writing System

Copyright © 2025-2026 WenShape Team
License: PolyForm Noncommercial License 1.0.0

模块说明 / Module Description:
  工作记忆服务 - 编译写作工作记忆，通过缺口检测生成针对性问题，支持证据检索和用户交互。
  Working memory compilation and gap-driven questions - Builds working memory packs with evidence retrieval and generates user questions based on content gaps.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.evidence_service import evidence_service
from app.services.chapter_binding_service import chapter_binding_service
from app.schemas.draft import SceneBrief
from app.config import config
from app.utils.language import normalize_language


class WorkingMemoryService:
    """
    工作记忆编译服务 - 为写作过程编译上下文和生成缺口问题。

    Compile working memory, evidence packs, and generates gap-driven questions to guide user research.
    Supports semantic reranking, entity tracking, and memory persistence.

    Attributes:
        MIN_GAP_SUPPORT_SCORE: 缺口支持最小分数 / Minimum score for gap support
        MIN_WORLD_RULE_SCORE: 世界规则最小分数 / Minimum score for world rules
        MAX_ITEMS: 各类型证据的最大数量 / Max items per evidence type in memory
    """

    MIN_GAP_SUPPORT_SCORE = 3.0
    MIN_WORLD_RULE_SCORE = 3.5
    SEMANTIC_RERANK_TOP_K = 16

    MAX_ITEMS = {
        "world_rule": 6,
        "fact": 8,
        "summary": 4,
        "world_entity": 6,
        "character": 4,
        "text_chunk": 4,
        "memory": 4,
    }

    def build_gap_items(
        self,
        scene_brief: Optional[SceneBrief],
        chapter_goal: str,
        language: str = "zh",
        seed_characters: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Build gap items from scene brief and chapter goal.

        Args:
            scene_brief: Scene brief object or dict.
            chapter_goal: Target goal text.

        Returns:
            List of gap items with queries.
        """
        gaps: List[Dict[str, Any]] = []
        lang = normalize_language(language, default="zh")

        goal_text = str(chapter_goal or "").strip()
        brief_goal = str(getattr(scene_brief, "goal", "") or "").strip()
        goal_text = goal_text or brief_goal
        if goal_text:
            gaps.append(
                {
                    "kind": "plot_point",
                    "text": (
                        "围绕章节目标的关键推进点是什么（避免偏离目标）"
                        if lang == "zh"
                        else "What is the key progression point aligned with the chapter goal (avoid drifting off-goal)?"
                    ),
                    "queries": [goal_text],
                    "ask_user": True,
                }
            )

        characters = getattr(scene_brief, "characters", []) or []
        character_names = []
        for item in characters:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = str(getattr(item, "name", "") or "").strip()
            if name:
                character_names.append(name)

        if seed_characters:
            merged = []
            for item in seed_characters:
                name = str(item).strip()
                if name and name not in merged:
                    merged.append(name)
            for name in character_names:
                if name and name not in merged:
                    merged.append(name)
            character_names = merged

        if not character_names:
            gaps.append(
                {
                    "kind": "detail_gap",
                    "text": "本章涉及的主要角色有哪些" if lang == "zh" else "Who are the main characters involved in this chapter?",
                    "queries": ["角色 人物 参与"] if lang == "zh" else ["main characters", "participants", "cast"],
                    "ask_user": True,
                }
            )
        else:
            for name in character_names[:2]:
                gaps.append(
                    {
                        "kind": "character_change",
                        "text": f"{name} 在本章的动机/状态是否有变化" if lang == "zh" else f"Does {name}'s motivation/state change in this chapter?",
                        "queries": [f"{name} 动机", f"{name} 状态"] if lang == "zh" else [f"{name} motivation", f"{name} current state"],
                        "ask_user": True,
                        "entity_name": name,
                    }
                )

        timeline_context = getattr(scene_brief, "timeline_context", {}) or {}
        if not timeline_context:
            gaps.append(
                {
                    "kind": "detail_gap",
                    "text": "本章时间/地点的具体边界是什么" if lang == "zh" else "What are the concrete boundaries of time and place in this chapter?",
                    "queries": ["时间 地点 场景"] if lang == "zh" else ["time", "location", "setting"],
                    "ask_user": True,
                }
            )

        world_constraints = getattr(scene_brief, "world_constraints", []) or []
        if not world_constraints:
            gaps.append(
                {
                    "kind": "plot_point",
                    "text": "本章需遵守的世界规则/禁忌/代价有哪些" if lang == "zh" else "Which world rules/taboos/costs must be respected in this chapter?",
                    "queries": ["规则 禁忌 代价 限制"] if lang == "zh" else ["rules", "taboos", "cost", "constraints"],
                    "ask_user": True,
                }
            )

        facts = getattr(scene_brief, "facts", []) or []
        if not facts:
            gaps.append(
                {
                    "kind": "detail_gap",
                    "text": "与本章目标直接相关的已确立事实有哪些" if lang == "zh" else "Which established facts directly matter for this chapter goal?",
                    "queries": ["关键事实 已确立事实"] if lang == "zh" else ["key facts", "established facts"],
                    "ask_user": True,
                }
            )

        return _unique_gaps(gaps, limit=8)

    def _is_gap_supported(self, gap: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
        queries = [q for q in gap.get("queries", []) if q]
        if not queries:
            return False
        for item in items or []:
            try:
                score = float(item.get("score") or 0)
            except Exception:
                score = 0.0
            if score < self.MIN_GAP_SUPPORT_SCORE:
                continue
            text = str(item.get("text") or "")
            if _query_hits(text, queries):
                return True
        return False

    async def prepare(
        self,
        project_id: str,
        chapter: str,
        scene_brief: Optional[SceneBrief],
        chapter_goal: str,
        language: str = "zh",
        user_answers: Optional[List[Dict[str, Any]]] = None,
        extra_queries: Optional[List[str]] = None,
        force_minimum_questions: Optional[bool] = None,
        semantic_rerank: Optional[bool] = None,
        round_index: Optional[int] = None,
        trace_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepare working memory, evidence pack, and questions.

        Args:
            project_id: Target project id.
            chapter: Chapter id.
            scene_brief: Scene brief object or dict.
            chapter_goal: Chapter goal text.
            semantic_rerank: Enable semantic rerank when available.
            round_index: Optional research round index for trace metadata.
            trace_note: Optional note to include in retrieval stats.

        Returns:
            Dict containing working_memory, gaps, unresolved_gaps, evidence_pack, retrieval_requests, questions.
        """
        user_answers_list = user_answers or []
        lang = normalize_language(language, default="zh")
        if semantic_rerank is None:
            semantic_rerank = bool((config.get("retrieval") or {}).get("semantic_rerank", True))
        rerank_top_k = int((config.get("retrieval") or {}).get("rerank_top_k", self.SEMANTIC_RERANK_TOP_K))

        seed_window = 2
        recent_chapters = await chapter_binding_service.get_recent_chapters(
            project_id,
            chapter,
            window=seed_window,
            include_current=False,
        )
        seed_entities = await chapter_binding_service.get_seed_entities(
            project_id,
            chapter,
            window=seed_window,
            ensure_built=True,
        )
        instruction_entities = await chapter_binding_service.extract_entities_from_text(project_id, chapter_goal)
        instruction_characters = instruction_entities.get("characters") or []
        instruction_worlds = instruction_entities.get("world_entities") or []
        seed_entities = list(dict.fromkeys(seed_entities + instruction_characters + instruction_worlds))

        loose_mentions = chapter_binding_service.extract_loose_mentions(chapter_goal, limit=6)
        missing_mentions = [m for m in (loose_mentions or []) if m and m not in seed_entities]
        binding_chapters = await chapter_binding_service.get_chapters_for_entities(
            project_id,
            instruction_characters + instruction_worlds,
            limit=6,
        )
        recent_character_candidates: List[str] = []
        for ch in recent_chapters:
            bindings = await chapter_binding_service.read_bindings(project_id, ch)
            if not bindings:
                continue
            recent_character_candidates.extend(bindings.get("characters") or [])
        recent_character_candidates = list(dict.fromkeys([item for item in recent_character_candidates if item]))
        if instruction_characters:
            recent_character_candidates = list(
                dict.fromkeys([item for item in instruction_characters + recent_character_candidates if item])
            )

        gaps = self.build_gap_items(
            scene_brief,
            chapter_goal,
            language=lang,
            seed_characters=recent_character_candidates,
        )
        extra_list = [str(q).strip() for q in (extra_queries or []) if str(q).strip()]
        if missing_mentions:
            extra_list = list(dict.fromkeys(extra_list + [str(m).strip() for m in missing_mentions if str(m).strip()]))[:8]
        if extra_list:
            gaps.append(
                {
                    "kind": "extra_research",
                    "text": "研究补充查询" if lang == "zh" else "Supplementary research queries",
                    "queries": extra_list,
                    "ask_user": False,
                }
            )
        query_list = []
        for gap in gaps:
            query_list.extend([q for q in gap.get("queries", []) if q])
        query_list = list(dict.fromkeys(query_list))

        answer_items = _answer_to_evidence_items(user_answers_list, chapter=chapter)
        answered_gap_texts = _answered_gap_texts_from_answers(gaps, user_answers_list)
        unknown_gap_texts = _unknown_gap_texts_from_answers(gaps, user_answers_list)

        # If user answers are not provided in this call (e.g. new session),
        # reuse persisted answer memories for the current chapter to avoid
        # re-asking and to keep working memory consistent.
        persisted_answer_items: List[Dict[str, Any]] = []
        if not user_answers_list:
            persisted_answer_items = await _load_chapter_answer_memory_items(project_id, chapter)
            answered_gap_texts |= _answered_gap_texts_from_memory(gaps, persisted_answer_items, chapter)

        evidence_groups: List[Dict[str, Any]] = []
        retrieval_requests: List[Dict[str, Any]] = []
        combined_items: List[Dict[str, Any]] = []
        gap_supported: Dict[str, bool] = {}
        gap_support_scores: Dict[str, float] = {}
        skip_retrieval_kinds = {"character_change"}
        trace_meta = {"round": round_index, "note": trace_note or ""}
        for gap in gaps:
            queries = [q for q in gap.get("queries", []) if q]
            if not queries:
                continue
            gap_text = str(gap.get("text") or "").strip()
            gap_kind = str(gap.get("kind") or "").strip()
            if gap_text and gap_text in answered_gap_texts and gap_kind in skip_retrieval_kinds:
                # For answered non-plot gaps (especially character state checks),
                # skip retrieval to avoid dragging in replay-heavy evidence.
                gap_supported[gap_text] = True
                gap_support_scores[gap_text] = self.MIN_GAP_SUPPORT_SCORE + 1.0
                retrieval_requests.append(
                    {
                        "gap": gap,
                        "queries": queries,
                        "types": {},
                        "count": 0,
                        "skipped": True,
                        "reason": "answered_gap_skip_retrieval",
                    }
                )
                continue
            text_chunk_chapters = None
            semantic_rerank_enabled = False
            rerank_query = None
            if gap_kind == "plot_point":
                text_chunk_chapters = _merge_chapter_window(recent_chapters, binding_chapters)
                semantic_rerank_enabled = bool(semantic_rerank)
                rerank_query = f"{chapter_goal} | {gap_text}" if gap_text else str(chapter_goal or "")
            result = await evidence_service.search(
                project_id=project_id,
                queries=queries,
                seed_entities=seed_entities,
                include_text_chunks=True,
                text_chunk_chapters=text_chunk_chapters,
                semantic_rerank=semantic_rerank_enabled,
                rerank_query=rerank_query,
                rerank_top_k=rerank_top_k,
                trace_meta=trace_meta,
            )
            items = result.get("items", [])
            stats = result.get("stats", {})
            evidence_groups.append(
                {
                    "gap": gap,
                    "queries": queries,
                    "items": items,
                    "stats": stats,
                }
            )
            retrieval_requests.append(
                {
                    "gap": gap,
                    "queries": queries,
                    "types": stats.get("types", {}),
                    "count": len(items),
                    "top_sources": stats.get("top_sources") or [],
                }
            )
            combined_items.extend(items)
            if gap_text:
                score = self._gap_support_score(gap, items)
                gap_support_scores[gap_text] = score
                gap_supported[gap_text] = score >= self.MIN_GAP_SUPPORT_SCORE

        # Defensive fallback: even if all gaps are considered "answered", ensure we
        # still retrieve goal-related evidence so working memory isn't reduced to
        # Q&A memories only.
        if not retrieval_requests:
            goal_text = str(chapter_goal or "").strip()
            brief_goal = str(getattr(scene_brief, "goal", "") or "").strip()
            goal_text = goal_text or brief_goal
            if goal_text:
                result = await evidence_service.search(
                    project_id=project_id,
                    queries=[goal_text],
                    seed_entities=seed_entities,
                    include_text_chunks=True,
                    text_chunk_chapters=_merge_chapter_window(recent_chapters, binding_chapters),
                    semantic_rerank=bool(semantic_rerank),
                    rerank_query=goal_text,
                    rerank_top_k=rerank_top_k,
                    trace_meta=trace_meta,
                )
                items = result.get("items", [])
                stats = result.get("stats", {})
                evidence_groups.append(
                    {
                        "gap": {"kind": "fallback", "text": "goal_fallback", "queries": [goal_text], "ask_user": False},
                        "queries": [goal_text],
                        "items": items,
                        "stats": stats,
                    }
                )
                retrieval_requests.append(
                    {
                        "gap": {"kind": "fallback", "text": "goal_fallback", "queries": [goal_text], "ask_user": False},
                        "queries": [goal_text],
                        "types": stats.get("types", {}),
                        "count": len(items),
                        "skipped": False,
                        "top_sources": stats.get("top_sources") or [],
                    }
                )
                combined_items.extend(items)

        combined_items.extend(answer_items)
        combined_items.extend(persisted_answer_items)
        deduped_items = _dedup_items(combined_items)

        goal_text = str(chapter_goal or "").strip()
        brief_goal = str(getattr(scene_brief, "goal", "") or "").strip()
        goal_text = goal_text or brief_goal
        focus_terms = _build_focus_terms(scene_brief, goal_text)
        if recent_character_candidates:
            focus_terms.extend(recent_character_candidates)
            focus_terms = list(dict.fromkeys([t for t in focus_terms if t]))

        minimum_questions = bool(force_minimum_questions)
        unresolved_gaps = self._select_unresolved_gaps(
            gaps,
            gap_supported,
            gap_support_scores=gap_support_scores,
            focus_terms=focus_terms,
            force_minimum_questions=minimum_questions,
        )

        sufficiency_report = self._build_sufficiency_report(
            gaps=gaps,
            gap_supported=gap_supported,
            gap_support_scores=gap_support_scores,
            evidence_items=deduped_items,
            focus_terms=focus_terms,
            unknown_gap_texts=unknown_gap_texts,
        )

        evidence_pack = {
            "items": deduped_items,
            "groups": evidence_groups,
            "stats": {
                "total": len(deduped_items),
                "types": _count_types(deduped_items),
                "queries": query_list,
            },
        }

        questions = self._build_questions(unresolved_gaps, chapter, language=lang, unknown_gap_texts=unknown_gap_texts)

        working_memory = self._compile_working_memory(
            scene_brief=scene_brief,
            chapter_goal=chapter_goal,
            evidence_items=deduped_items,
            unresolved_gaps=unresolved_gaps,
        )

        return {
            "working_memory": working_memory,
            "gaps": gaps,
            "unresolved_gaps": unresolved_gaps,
            "evidence_pack": evidence_pack,
            "retrieval_requests": retrieval_requests,
            "seed_entities": seed_entities,
            "seed_window": seed_window,
            "questions": questions,
            "sufficiency_report": sufficiency_report,
        }

    def _select_unresolved_gaps(
        self,
        gaps: List[Dict[str, Any]],
        supported: Dict[str, bool],
        gap_support_scores: Dict[str, float],
        focus_terms: List[str],
        force_minimum_questions: bool = True,
    ) -> List[Dict[str, Any]]:
        askable = [g for g in gaps if g.get("ask_user", True)]
        if not askable:
            return []

        selected: List[Dict[str, Any]] = []
        seen = set()

        def add_gap(gap: Dict[str, Any]) -> None:
            text = gap.get("text") or ""
            if not text or text in seen:
                return
            selected.append(gap)
            seen.add(text)

        if force_minimum_questions:
            # Always ask at least one plot-focused question to confirm the intended
            # chapter push, even when retrieval finds related evidence.
            for gap in askable:
                if gap.get("kind") == "plot_point":
                    add_gap(gap)
                    break

        for gap in askable:
            if len(selected) >= 3:
                break
            text = gap.get("text") or ""
            if not text:
                continue
            if not supported.get(text, False):
                add_gap(gap)
                continue
            score = gap_support_scores.get(text, 0.0)
            is_focus = _is_focus_related(text, focus_terms) or gap.get("kind") == "plot_point"
            if score < (self.MIN_GAP_SUPPORT_SCORE + 0.8) and is_focus:
                add_gap(gap)

        if force_minimum_questions:
            for gap in askable:
                if len(selected) >= 3:
                    break
                add_gap(gap)

        return selected

    def _build_questions(
        self,
        gaps: List[Dict[str, Any]],
        chapter: str,
        language: str = "zh",
        unknown_gap_texts: Optional[set] = None,
    ) -> List[Dict[str, str]]:
        questions = []
        lang = normalize_language(language, default="zh")
        for gap in gaps[:3]:
            kind = gap.get("kind") or "detail_gap"
            text = gap.get("text") or ""
            if not text:
                continue
            if unknown_gap_texts and text in unknown_gap_texts:
                continue
            if lang == "en":
                q = str(text).strip()
                starts_like_question = bool(re.match(r"^(what|who|which|where|when|why|how|does|do|is|are|can|should)\b", q, re.I))
                if starts_like_question or "?" in q:
                    question = q
                    if not question.endswith("?"):
                        question += "?"
                else:
                    if kind == "plot_point":
                        question = f"To achieve this chapter goal, {q.rstrip('.')}?"
                    elif kind == "character_change":
                        question = f"Character: {q.rstrip('.')}?"
                    else:
                        question = f"Details: {q.rstrip('.')}?"
                reason = f"Insufficient evidence; gap: {q}"
            else:
                if kind == "plot_point":
                    question = f"为达成本章目标，{text}？"
                elif kind == "character_change":
                    question = f"角色方面：{text}？"
                else:
                    question = f"细节方面：{text}？"
                reason = f"证据不足，缺口：{text}"
            questions.append(
                {
                    "type": kind,
                    "text": question,
                    "key": _make_question_key(chapter, kind, text),
                    "reason": reason,
                }
            )
        return questions

    def _gap_support_score(self, gap: Dict[str, Any], items: List[Dict[str, Any]]) -> float:
        queries = [q for q in gap.get("queries", []) if q]
        if not queries:
            return 0.0
        best = 0.0
        for item in items or []:
            text = str(item.get("text") or "")
            if not text:
                continue
            if not _query_hits(text, queries):
                continue
            best = max(best, _safe_score(item))
        return best

    def _build_sufficiency_report(
        self,
        gaps: List[Dict[str, Any]],
        gap_supported: Dict[str, bool],
        gap_support_scores: Dict[str, float],
        evidence_items: List[Dict[str, Any]],
        focus_terms: List[str],
        unknown_gap_texts: set,
    ) -> Dict[str, Any]:
        unresolved = []
        weak = []
        critical_weak = []
        missing_entities = []

        for gap in gaps or []:
            if not gap.get("ask_user", True):
                continue
            text = str(gap.get("text") or "").strip()
            if not text:
                continue
            supported = gap_supported.get(text, False)
            score = gap_support_scores.get(text, 0.0)
            if not supported:
                unresolved.append(text)
                missing_entities.append(text)
            elif score < (self.MIN_GAP_SUPPORT_SCORE + 0.8):
                weak.append(text)
                is_focus = _is_focus_related(text, focus_terms) or gap.get("kind") == "plot_point"
                if is_focus:
                    critical_weak.append(text)

        insufficient = bool(unresolved or critical_weak)
        report = {
            "sufficient": not insufficient,
            "needs_user_input": insufficient,
            "missing_entities": list(dict.fromkeys(missing_entities)),
            "weak_gaps": list(dict.fromkeys(weak)),
            "critical_weak_gaps": list(dict.fromkeys(critical_weak)),
            "unknown_gaps": list(dict.fromkeys(list(unknown_gap_texts or []))),
            "evidence_types": _count_types(evidence_items or []),
        }
        return report

    def _compile_working_memory(
        self,
        scene_brief: Optional[SceneBrief],
        chapter_goal: str,
        evidence_items: List[Dict[str, Any]],
        unresolved_gaps: List[Dict[str, Any]],
    ) -> str:
        goal_text = str(chapter_goal or "").strip()
        brief_goal = str(getattr(scene_brief, "goal", "") or "").strip()
        goal_text = goal_text or brief_goal or "未提供"

        world_constraints = list(getattr(scene_brief, "world_constraints", []) or [])
        forbidden = list(getattr(scene_brief, "forbidden", []) or [])
        facts = list(getattr(scene_brief, "facts", []) or [])
        focus_terms = _build_focus_terms(scene_brief, goal_text)

        lines = ["本章目标: " + goal_text]

        lines.append("硬约束:")
        constraint_lines = []
        rule_text_to_card = _build_rule_text_to_card(evidence_items)
        constraint_lines.extend([_maybe_prefix_world_rule(str(item), rule_text_to_card) for item in world_constraints])
        constraint_lines.extend([_clean_text_for_memory(f"禁忌: {item}") for item in forbidden if item])
        world_rule_items = [item for item in evidence_items if item.get("type") == "world_rule"]
        world_rule_items.sort(key=lambda x: (_item_stars(x), _safe_score(x)), reverse=True)
        for item in world_rule_items:
            if _item_stars(item) < 3:
                continue
            if _safe_score(item) < self.MIN_WORLD_RULE_SCORE:
                continue
            text = _format_material_text(item)
            if text:
                constraint_lines.append(text)
        constraint_lines = _dedup_material_lines(_unique_texts(constraint_lines))
        if constraint_lines:
            for item in constraint_lines[: self.MAX_ITEMS["world_rule"]]:
                lines.append(f"- {item}")
        else:
            lines.append("- 无")

        lines.append("可用素材:")
        material_lines: List[str] = []
        for t in ["fact", "summary", "text_chunk", "world_entity", "character", "memory"]:
            candidates = [item for item in evidence_items if item.get("type") == t and _should_include_material(item)]
            if t in {"text_chunk", "summary"} and focus_terms:
                candidates.sort(
                    key=lambda x: (_focus_score_text(str(x.get("text") or ""), focus_terms), _safe_score(x)),
                    reverse=True,
                )
                focused = [item for item in candidates if _focus_score_text(str(item.get("text") or ""), focus_terms) > 0]
                candidates = focused or candidates
            else:
                if t in {"world_entity", "character"}:
                    candidates.sort(key=lambda x: (_item_stars(x), _safe_score(x)), reverse=True)
                else:
                    candidates.sort(key=_safe_score, reverse=True)
            for item in candidates[: self.MAX_ITEMS.get(t, 4)]:
                text = _format_material_text(item)
                if text:
                    material_lines.append(text)

        material_lines.extend(_select_focus_facts(facts, focus_terms, limit=12))
        material_lines = _dedup_material_lines(_unique_texts(material_lines))
        if material_lines:
            for item in material_lines:
                lines.append(f"- {truncate(_clean_text_for_memory(item), 140)}")
        else:
            lines.append("- 无")

        lines.append("未解决缺口:")
        if unresolved_gaps:
            for gap in unresolved_gaps[:6]:
                lines.append(f"- {gap.get('text')}")
        else:
            lines.append("- 无")

        return "\n".join(lines)


def _build_focus_terms(scene_brief: Optional[SceneBrief], goal_text: str) -> List[str]:
    terms: List[str] = []
    terms.extend(_extract_terms(goal_text))

    characters = getattr(scene_brief, "characters", []) or []
    for item in characters[:6]:
        name = ""
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(getattr(item, "name", "") or "").strip()
        if name:
            terms.append(name)

    return list(dict.fromkeys([t for t in terms if t]))


def _focus_score_text(text: str, focus_terms: List[str]) -> int:
    if not (text and focus_terms):
        return 0
    return _term_overlap(text, focus_terms)


def _select_focus_facts(facts: List[Any], focus_terms: List[str], limit: int = 12) -> List[str]:
    raw = [str(item).strip() for item in (facts or []) if str(item).strip()]
    if not raw:
        return []
    limit = max(int(limit or 0), 0)
    if limit <= 0:
        return []

    if not focus_terms:
        return raw[:limit]

    scored: List[tuple[int, str]] = []
    for fact in raw:
        scored.append((_focus_score_text(fact, focus_terms), fact))
    scored.sort(key=lambda x: (x[0], len(x[1])), reverse=True)

    focused = [fact for score, fact in scored if score > 0]
    if focused:
        return focused[:limit]

    # If nothing overlaps, keep a small prefix instead of dumping everything.
    return raw[: min(limit, 5)]


def _build_rule_text_to_card(items: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for item in items or []:
        if item.get("type") != "world_rule":
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        source = item.get("source") or {}
        card = str(source.get("card") or "").strip()
        if not card:
            continue
        key = _normalize_text(text)
        if not key or key in mapping:
            continue
        mapping[key] = card
    return mapping


def _maybe_prefix_world_rule(text: str, rule_text_to_card: Dict[str, str]) -> str:
    text = str(text or "").strip()
    if not text or not rule_text_to_card:
        return _clean_text_for_memory(text)
    key = _normalize_text(text)
    card = rule_text_to_card.get(key)
    if not card:
        return _clean_text_for_memory(text)
    if text.startswith(f"{card}:") or text.startswith(f"{card}："):
        return _clean_text_for_memory(text)
    return _clean_text_for_memory(f"{card}: {text}".strip())


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", "", str(text).lower())


def _strip_field_prefix(text: str, field: str) -> str:
    text = str(text or "").strip()
    field = str(field or "").strip()
    if not (text and field):
        return text
    prefix = f"{field}:"
    if text.startswith(prefix):
        return text[len(prefix) :].lstrip()
    return text


def _format_material_text(item: Dict[str, Any]) -> str:
    text = str(item.get("text") or "").strip()
    if not text:
        return ""

    item_type = str(item.get("type") or "").strip()
    source = item.get("source") or {}
    card = str(source.get("card") or "").strip()
    field = str(source.get("field") or "").strip()

    if item_type == "world_rule" and card:
        return truncate(_clean_text_for_memory(f"{card}: {text}".strip()), 140)
    if item_type == "world_entity" and card:
        if text == card or text.startswith(f"{card}:") or text.startswith(f"{card}："):
            return truncate(_clean_text_for_memory(text), 140)
        return truncate(_clean_text_for_memory(f"{card}: {text}".strip()), 140)
    if item_type == "character" and card:
        stripped = _strip_field_prefix(text, field)
        if not stripped:
            return card
        return truncate(_clean_text_for_memory(f"{card}: {stripped}".strip()), 140)

    if item_type in {"text_chunk", "summary"}:
        return _truncate_to_boundary(_clean_text_for_memory(text), 120)

    return truncate(_clean_text_for_memory(text), 140)


def _clean_text_for_memory(text: str) -> str:
    """Clean evidence text for working memory (compact, less meta-noise)."""
    text = str(text or "").strip()
    if not text:
        return ""

    # Drop common meta annotations used in cards/briefs.
    for marker in ["\n理由:", "\r\n理由:", "理由:"]:
        if marker in text:
            text = text.split(marker, 1)[0].strip()
            break

    # Remove markdown emphasis which may leak into prose.
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)

    # Normalize ellipsis and whitespace.
    text = text.replace("…", "")
    text = re.sub(r"\.{3,}", ".", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate_to_boundary(text: str, max_len: int) -> str:
    text = str(text or "")
    if not text:
        return ""
    if len(text) <= max_len:
        return text

    head = text[:max_len]
    for punct in ["。", "！", "？", "；", ";", "，", "、", ".", ","]:
        idx = head.rfind(punct)
        if idx >= max(12, max_len // 3):
            return head[: idx + 1].strip()
    return truncate(text, max_len)


def _normalize_for_dedup(text: str) -> str:
    text = _clean_text_for_memory(text)
    text = re.sub(r"[\s\-—–,，。；;、:：()（）\[\]{}<>\"“”'’]", "", text).lower()
    return text


def _dedup_material_lines(lines: List[str]) -> List[str]:
    kept: List[str] = []
    kept_norms: List[str] = []

    for line in lines or []:
        line = str(line or "").strip()
        if not line:
            continue
        norm = _normalize_for_dedup(line)
        if not norm:
            continue

        duplicate_index = None
        for idx, existing in enumerate(kept_norms):
            if norm in existing or existing in norm:
                duplicate_index = idx
                break

        if duplicate_index is None:
            kept.append(line)
            kept_norms.append(norm)
            continue

        # Prefer the longer (more informative) line.
        if len(line) > len(kept[duplicate_index]):
            kept[duplicate_index] = line
            kept_norms[duplicate_index] = norm

    return kept


def _unique_gaps(gaps: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for gap in gaps:
        key = gap.get("text") or ""
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(gap)
        if len(result) >= limit:
            break
    return result


def _gap_answered(gap: Dict[str, Any], answers: List[Dict[str, Any]]) -> bool:
    gap_text = str(gap.get("text") or "").strip()
    if not gap_text:
        return False
    gap_norm = _normalize_for_dedup(gap_text)
    for item in answers or []:
        if not isinstance(item, dict):
            continue
        q_text = str(item.get("question") or item.get("text") or "").strip()
        answer_text = str(item.get("answer") or "").strip()
        if not q_text:
            continue
        if _is_invalid_answer_text(answer_text):
            continue
        if gap_text in q_text:
            return True
        q_norm = _normalize_for_dedup(q_text)
        if gap_norm and q_norm and gap_norm in q_norm:
            return True
    return False


def _answered_gap_texts_from_answers(gaps: List[Dict[str, Any]], answers: List[Dict[str, Any]]) -> set:
    answered = set()
    for gap in gaps or []:
        gap_text = str(gap.get("text") or "").strip()
        if not gap_text:
            continue
        if _gap_answered(gap, answers):
            answered.add(gap_text)
    return answered


def _unknown_gap_texts_from_answers(gaps: List[Dict[str, Any]], answers: List[Dict[str, Any]]) -> set:
    unknown = set()
    for gap in gaps or []:
        gap_text = str(gap.get("text") or "").strip()
        if not gap_text:
            continue
        gap_norm = _normalize_for_dedup(gap_text)
        for item in answers or []:
            if not isinstance(item, dict):
                continue
            q_text = str(item.get("question") or item.get("text") or "").strip()
            answer_text = str(item.get("answer") or "").strip()
            if not q_text:
                continue
            if not _is_invalid_answer_text(answer_text):
                continue
            if gap_text in q_text:
                unknown.add(gap_text)
                break
            q_norm = _normalize_for_dedup(q_text)
            if gap_norm and q_norm and gap_norm in q_norm:
                unknown.add(gap_text)
                break
    return unknown


def _answered_gap_texts_from_memory(
    gaps: List[Dict[str, Any]],
    memory_items: List[Dict[str, Any]],
    chapter: str,
) -> set:
    answered = set()
    for gap in gaps or []:
        gap_text = str(gap.get("text") or "").strip()
        if not gap_text:
            continue
        for item in memory_items or []:
            source = item.get("source") or {}
            question = str(source.get("question") or "").strip()
            question_key = str(source.get("question_key") or "").strip()
            if question_key and question_key == _make_question_key(chapter, gap.get("kind"), gap_text):
                answered.add(gap_text)
                break
            if question and gap_text in question:
                answered.add(gap_text)
                break
    return answered


async def _load_chapter_answer_memory_items(project_id: str, chapter: str) -> List[Dict[str, Any]]:
    try:
        await evidence_service.build_all(project_id, force=False)
        items = await evidence_service.index_storage.read_items(project_id, evidence_service.MEMORY_INDEX)
    except Exception:
        return []

    results: List[Dict[str, Any]] = []
    for item in items or []:
        if getattr(item, "type", None) != "memory":
            continue
        source = getattr(item, "source", {}) or {}
        meta = getattr(item, "meta", {}) or {}
        if str(meta.get("kind") or "") != "user_answer":
            continue
        if str(source.get("chapter") or "") != str(chapter):
            continue
        text = str(getattr(item, "text", "") or "").strip()
        if not text:
            continue
        results.append(
            {
                "id": getattr(item, "id", ""),
                "type": "memory",
                "text": text,
                # Give persisted answers a strong weight so they reliably enter the pack.
                "score": 10.0,
                "source": source,
                "meta": meta,
            }
        )
    return results


def _query_hits(text: str, queries: List[str]) -> bool:
    for query in queries:
        if not query:
            continue
        terms = _extract_terms(query)
        if not terms:
            continue
        if _term_overlap(text, terms) > 0:
            return True
    return False


def _extract_terms(text: str) -> List[str]:
    text = (text or "").lower()
    terms: List[str] = []
    for block in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(block) == 1:
            terms.append(block)
            continue
        for n in (2, 3):
            if len(block) < n:
                continue
            for i in range(0, len(block) - n + 1):
                terms.append(block[i : i + n])
    terms.extend(re.findall(r"[a-z0-9]+", text))
    return list(dict.fromkeys(terms))


def _term_overlap(text: str, terms: List[str]) -> int:
    count = 0
    for term in terms:
        if term and term in text:
            count += 1
    return count


def _is_focus_related(text: str, focus_terms: List[str]) -> bool:
    if not text or not focus_terms:
        return False
    return _term_overlap(text, focus_terms) > 0


def _merge_chapter_window(primary: List[str], secondary: List[str]) -> Optional[List[str]]:
    merged: List[str] = []
    for items in (primary or [], secondary or []):
        for chapter in items:
            value = str(chapter or "").strip()
            if value and value not in merged:
                merged.append(value)
    return merged or None


def _unique_texts(items: List[Any]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _safe_score(item: Dict[str, Any]) -> float:
    try:
        return float(item.get("score") or 0)
    except Exception:
        return 0.0


def _item_stars(item: Dict[str, Any]) -> int:
    meta = item.get("meta") or {}
    try:
        stars = int(meta.get("stars") or 1)
    except Exception:
        return 1
    return max(1, min(stars, 3))


def _should_include_material(item: Dict[str, Any]) -> bool:
    text = str(item.get("text") or "").strip()
    if not text:
        return False

    source = item.get("source") or {}
    field = str(source.get("field") or "").strip()
    item_type = str(item.get("type") or "").strip()
    stars = _item_stars(item)
    score = _safe_score(item)
    meta = item.get("meta") or {}

    if item_type == "memory" and str(meta.get("kind") or "") == "user_unknown":
        return False
    if item_type == "memory" and str(meta.get("kind") or "") == "research_trace":
        # Trace memories are for observability/debugging and should never pollute
        # the writer-facing working memory context.
        return False

    if text.startswith("aliases:") or field == "aliases":
        if item_type == "character" and stars <= 1:
            return True
        return False
    if text.startswith("category:") or field == "category" or text.startswith("类别:"):
        if item_type == "world_entity" and stars >= 2:
            return True
        return False
    if text.startswith("immutable:") or field == "immutable":
        return False
    if text.startswith("理由:"):
        return False
    if any(text.startswith(prefix) for prefix in ["description: 理由", "identity: 理由", "appearance: 理由", "motivation: 理由"]):
        return False

    if item_type == "world_entity" and stars <= 1 and score < 2.5:
        return False

    if item_type == "character":
        if stars <= 1:
            return field in {"description", "aliases"}
        if stars == 2:
            return field in {"description", "identity", "motivation", "relationships", "appearance", "arc"}

    return True


def _dedup_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        item_id = item.get("id") or ""
        if item_id and item_id in seen:
            continue
        if item_id:
            seen.add(item_id)
        result.append(item)
    return result


def _count_types(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        t = item.get("type")
        if not t:
            continue
        counts[t] = counts.get(t, 0) + 1
    return counts


def _answer_text(answer: Dict[str, Any]) -> str:
    question = str(answer.get("question") or answer.get("text") or "").strip()
    reply = str(answer.get("answer") or "").strip()
    if question and reply:
        return f"{question} -> {reply}"
    return reply or question


def _is_invalid_answer_text(text: str) -> bool:
    normalized = re.sub(r"\s+", "", str(text or ""))
    if not normalized:
        return True
    invalid_terms = {
        "不知道",
        "不清楚",
        "不确定",
        "无",
        "没有",
        "随便",
        "都行",
        "不会",
        "不懂",
    }
    return normalized in invalid_terms


def _sanitize_answer_items(answers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for item in answers:
        if not isinstance(item, dict):
            continue
        text = _answer_text(item)
        if not text:
            continue
        cleaned.append(item)
    return cleaned


def _answer_to_evidence_items(answers: List[Dict[str, Any]], chapter: Optional[str] = None) -> List[Dict[str, Any]]:
    import time
    items = []
    timestamp = int(time.time())
    for idx, answer in enumerate(_sanitize_answer_items(answers)):
        question_text = str(answer.get("question") or answer.get("text") or "").strip()
        reply = str(answer.get("answer") or "").strip()
        invalid = _is_invalid_answer_text(reply)
        if invalid:
            if reply:
                text = f"{question_text} -> {reply}" if question_text else reply
            else:
                text = f"{question_text} -> [用户未回答]" if question_text else "[用户未回答]"
        else:
            text = _answer_text(answer)
        if not text:
            continue
        question_key = answer.get("key") or answer.get("question_key")
        if not question_key and chapter:
            question_key = _make_question_key(chapter, answer.get("type"), question_text)
        items.append(
            {
                "id": f"memory:answer:{timestamp}:{idx + 1}",
                "type": "memory",
                "text": text,
                "score": 1.0,
                "source": {
                    "question": question_text,
                    "question_key": question_key,
                    "kind": answer.get("type"),
                },
                "meta": {"kind": "user_unknown" if invalid else "user_answer"},
            }
        )
    return items


def _make_question_key(chapter: Optional[str], q_type: Optional[str], text: Optional[str]) -> str:
    base = f"{chapter or ''}|{q_type or ''}|{text or ''}".strip()
    return _normalize_for_dedup(base)


working_memory_service = WorkingMemoryService()
