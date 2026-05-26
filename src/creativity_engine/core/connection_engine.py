from __future__ import annotations

import json
import logging
import random
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..config import EngineConfig
from ..llm.base import BaseLLMClient
from ..llm.claude import ClaudeClient
from .models import Idea, IdeaSet, InputBundle

logger = logging.getLogger(__name__)

# 하위 호환을 위해 유지 (외부에서 import 하는 테스트 대응)
_SERENDIPITY_DOMAINS = [
    "요리", "음악", "고고학", "우주항공", "패션", "원예", "마술", "스포츠",
    "신화", "지질학", "해양생물", "건축", "철학", "만화", "의학", "종교",
    "경제학", "수학", "영화", "곤충학", "기후학", "언어학", "무용", "항해",
]


# ──────────────────────────────────────────────
# LangGraph State
# ──────────────────────────────────────────────

class ConnectionState(TypedDict):
    bundle: InputBundle
    diverged_ideas: list[Idea]
    linked_ideas: list[Idea]
    relaxed_ideas: list[Idea]
    serendipity_ideas: list[Idea]
    extra_ideas: list[Idea]
    all_ideas: list[Idea]
    scored_ideas: list[Idea]
    idea_set: IdeaSet


# ──────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """마크다운 코드 펜스 제거 후 JSON 문자열 반환."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return match.group(1).strip() if match else text.strip()


def _normalize_idea_dict(item: dict) -> dict:
    """AI가 content 대신 title 등 다른 키를 반환하는 경우를 정규화한다."""
    if "content" not in item:
        for alt in ("title", "idea", "description", "text"):
            if alt in item:
                item = {**item, "content": item[alt]}
                break
    return item


def _parse_ideas_json(text: str, retries: int = 2) -> list[dict]:
    """JSON 파싱 with 재시도 (코드 펜스 제거 포함)."""
    for attempt in range(retries + 1):
        try:
            cleaned = _extract_json(text)
            raw = json.loads(cleaned)
            if isinstance(raw, list):
                return [_normalize_idea_dict(item) for item in raw if isinstance(item, dict)]
            return []
        except json.JSONDecodeError:
            if attempt == retries:
                logger.error("JSON parse failed after %d attempts: %s", retries + 1, text[:200])
                return []
    return []


def _summarize_knowledge(bundle: InputBundle, max_docs: int = 3, max_chars: int = 500) -> str:
    """지식 문서를 프롬프트용 요약 텍스트로 변환."""
    if not bundle.knowledge:
        return "관련 지식 없음"
    parts = []
    for doc in bundle.knowledge[:max_docs]:
        parts.append(f"[{doc.source}] {doc.content[:max_chars]}")
    return "\n".join(parts)


# ──────────────────────────────────────────────
# Prompt Templates (오버라이드 가능)
# ──────────────────────────────────────────────

_DIVERGENCE_SYSTEM = """\
ROLE: 창의적 아이디어 생성기
ABBREV: sd=source_domains conn=connections

{n}개 아이디어 생성. 품질판단 금지. 접근법 모두 달라야 함. 상식→파격 스펙트럼. sd 필수.

<out>JSON 배열만 (타 텍스트 없이)
[{{"content":"...","rationale":"...","source_domains":["분야"],"connections":["개념"]}}]</out>"""

_DIVERGENCE_USER = """\
goal:{goal}|const:{constraints}
ctx:{context_summary}|know:{knowledge_summary}
→{n}개 JSON"""

_CROSS_DOMAIN_SYSTEM = """\
ROLE: 크로스도메인 연결 전문가
도메인 간 유추로 새 아이디어 {n}개 생성. source_domains에 연결된 두 도메인 모두 포함.

<ex>군사전략→비즈전략|생태계→포트폴리오|게임디자인→교육동기|면역→사이버보안</ex>
<out>JSON 배열만. 반드시 "content" 키 사용 ("title" 금지):
[{{"content":"...","rationale":"...","source_domains":["도메인A","도메인B"],"connections":["연결개념"]}}]</out>"""

_CROSS_DOMAIN_USER = """\
goal:{goal}|const:{constraints}
<ideas>
{ideas_summary}
</ideas>
<signals>
{signals_text}
</signals>
→{n}개 크로스도메인 JSON"""

_RELAXER_SYSTEM = """\
ROLE: 제약 해체 전문가
목표: 제약 해제 아님. 해제 시 보이는 가능성 본질 추출 → 원래 제약 안 구현 아이디어 생성.

<out>JSON 배열만
[{{"content":"원래 제약 안 아이디어","rationale":"해제 시 인사이트","source_domains":["역발상"],"connections":["키워드"]}}]</out>"""

_RELAXER_USER = """\
goal:{goal}
const:
{constraints}
→역발상 JSON"""

_SERENDIPITY_SYSTEM = """\
ROLE: 우연적 아이디어 생성기
ABBREV: sd=source_domains conn=connections

무관해 보이는 도메인을 문제에 강제 연결해 예상치 못한 아이디어를 생성.
논리적 연결보다 직관적·우연적 연상을 우선. 실현가능성 판단 금지.

<out>JSON 배열만
[{{"content":"...","rationale":"...","source_domains":["랜덤도메인","문제도메인"],"connections":["연결개념"]}}]</out>"""

_SERENDIPITY_USER = """\
goal:{goal}|const:{constraints}
random_domains:{random_domains}
serendipity:{serendipity}

→위 랜덤 도메인을 문제에 강제 연결해 {n}개 아이디어 JSON"""

_SCORER_SYSTEM = """\
ROLE: 아이디어 평가기
ABBREV: ns=novelty_score(0-1) fs=feasibility_score(0-1)

<rubric>
score|ns 기준|fs 기준
0.0|뻔한 해법|제약위반/불가
0.5|맥락 신선|도전적 가능
1.0|전혀 새 접근|즉시 실행
</rubric>

<out>JSON 배열만
[{{"id":"...","novelty_score":0.0,"feasibility_score":0.0}}]</out>"""

_SCORER_USER = """\
goal:{goal}|const:{constraints}
<ideas>
{ideas_text}
</ideas>
→각 아이디어 평가 JSON"""

_PROMPT_DEFAULTS: dict[str, str] = {
    "diverge": _DIVERGENCE_SYSTEM,
    "cross_link": _CROSS_DOMAIN_SYSTEM,
    "relax": _RELAXER_SYSTEM,
    "serendipity": _SERENDIPITY_SYSTEM,
    "scorer": _SCORER_SYSTEM,
}


# ──────────────────────────────────────────────
# 1. Divergence Generator
# ──────────────────────────────────────────────

class DivergenceGenerator:
    def __init__(
        self, client: BaseLLMClient | None = None, config: EngineConfig | None = None
    ) -> None:
        cfg = config or EngineConfig()
        self._client = client or ClaudeClient(model=cfg.model)
        self._config = cfg
        self._system = cfg.prompt_overrides.get("diverge", _DIVERGENCE_SYSTEM)

    def run(self, bundle: InputBundle) -> list[Idea]:
        n = bundle.problem.divergence_n
        system = self._system.format(n=n)
        user = _DIVERGENCE_USER.format(
            goal=bundle.problem.goal,
            constraints=", ".join(bundle.problem.constraints) or "없음",
            context_summary=bundle.context_summary or "없음",
            knowledge_summary=_summarize_knowledge(
                bundle, self._config.max_knowledge_docs, self._config.max_chars
            ),
            n=n,
        )
        text = self._client.call(system, user, self._config.connection_max_tokens)
        raw = _parse_ideas_json(text)
        return [Idea(**item) for item in raw if isinstance(item, dict)]


# ──────────────────────────────────────────────
# 2. Cross-domain Linker
# ──────────────────────────────────────────────

class CrossDomainLinker:
    def __init__(
        self, client: BaseLLMClient | None = None, config: EngineConfig | None = None
    ) -> None:
        cfg = config or EngineConfig()
        self._client = client or ClaudeClient(model=cfg.model)
        self._config = cfg
        self._system_tpl = cfg.prompt_overrides.get("cross_link", _CROSS_DOMAIN_SYSTEM)

    def run(self, bundle: InputBundle, existing_ideas: list[Idea]) -> list[Idea]:
        n = max(3, bundle.problem.divergence_n // 3)
        ideas_summary = "content|sd\n" + "\n".join(
            f"{idea.content}|{idea.source_domains}"
            for idea in existing_ideas[:5]
        )
        signals_text = "\n".join(
            f"- [{s.signal_type}] {s.content}" for s in bundle.signals
        ) or "없음"

        system = self._system_tpl.format(n=n)
        user = _CROSS_DOMAIN_USER.format(
            goal=bundle.problem.goal,
            constraints=", ".join(bundle.problem.constraints) or "없음",
            ideas_summary=ideas_summary or "없음",
            signals_text=signals_text,
            n=n,
        )
        text = self._client.call(system, user, self._config.connection_max_tokens)
        raw = _parse_ideas_json(text)
        return [Idea(**item) for item in raw if isinstance(item, dict)]


# ──────────────────────────────────────────────
# 3. Constraint Relaxer
# ──────────────────────────────────────────────

class ConstraintRelaxer:
    def __init__(
        self, client: BaseLLMClient | None = None, config: EngineConfig | None = None
    ) -> None:
        cfg = config or EngineConfig()
        self._client = client or ClaudeClient(model=cfg.model)
        self._config = cfg
        self._system = cfg.prompt_overrides.get("relax", _RELAXER_SYSTEM)

    def run(self, bundle: InputBundle) -> list[Idea]:
        if not bundle.problem.constraints:
            return []

        user = _RELAXER_USER.format(
            goal=bundle.problem.goal,
            constraints="\n".join(f"- {c}" for c in bundle.problem.constraints),
        )
        text = self._client.call(self._system, user, self._config.connection_max_tokens)
        raw = _parse_ideas_json(text)
        return [Idea(**item) for item in raw if isinstance(item, dict)]


# ──────────────────────────────────────────────
# 4. Serendipity Generator
# ──────────────────────────────────────────────

class SerendipityGenerator:
    """
    우연 자극 기반 아이디어 생성기.
    serendipity=0.0이면 즉시 빈 리스트 반환.
    """

    def __init__(
        self,
        client: BaseLLMClient | None = None,
        config: EngineConfig | None = None,
    ) -> None:
        cfg = config or EngineConfig()
        self._client = client or ClaudeClient(model=cfg.model)
        self._config = cfg
        self._system = cfg.prompt_overrides.get("serendipity", _SERENDIPITY_SYSTEM)
        self._domains = cfg.serendipity_domains

    def run(self, bundle: InputBundle) -> list[Idea]:
        serendipity = bundle.problem.serendipity
        if serendipity <= 0.0:
            return []

        domain_count = max(1, round(serendipity * 4))
        n = max(1, round(serendipity * bundle.problem.divergence_n * 0.4))

        random_domains = random.sample(
            self._domains, min(domain_count, len(self._domains))
        )

        user = _SERENDIPITY_USER.format(
            goal=bundle.problem.goal,
            constraints=", ".join(bundle.problem.constraints) or "없음",
            random_domains=", ".join(random_domains),
            serendipity=serendipity,
            n=n,
        )
        text = self._client.call(self._system, user, self._config.connection_max_tokens)
        raw = _parse_ideas_json(text)
        ideas = [Idea(**item) for item in raw if isinstance(item, dict)]
        logger.info(
            "SerendipityGenerator(strength=%.2f) domains=%s → %d ideas",
            serendipity, random_domains, len(ideas),
        )
        return ideas


# ──────────────────────────────────────────────
# 5. Novelty Scorer
# ──────────────────────────────────────────────

def _calculate_final_score(idea: Idea, weights: dict | None = None) -> float:
    w = weights or {"novelty": 0.6, "feasibility": 0.4}
    score = idea.novelty_score * w["novelty"] + idea.feasibility_score * w["feasibility"]
    return round(min(max(score, 0.0), 1.0), 4)


class NoveltyScorer:
    def __init__(
        self, client: BaseLLMClient | None = None, config: EngineConfig | None = None
    ) -> None:
        cfg = config or EngineConfig()
        self._client = client or ClaudeClient(model=cfg.model)
        self._config = cfg
        self._system = cfg.prompt_overrides.get("scorer", _SCORER_SYSTEM)

    def run(
        self,
        ideas: list[Idea],
        problem_goal: str,
        problem_constraints: list[str],
        score_weights: dict | None = None,
    ) -> list[Idea]:
        if not ideas:
            return ideas

        weights = score_weights or self._config.score_weights
        ideas_text = "id|content\n" + "\n".join(
            f"{idea.id}|{idea.content}" for idea in ideas
        )
        user = _SCORER_USER.format(
            goal=problem_goal,
            constraints=", ".join(problem_constraints) or "없음",
            ideas_text=ideas_text,
        )
        text = self._client.call(self._system, user, self._config.connection_max_tokens)
        raw = _parse_ideas_json(text)

        score_map: dict[str, dict] = {}
        for item in raw:
            if isinstance(item, dict) and "id" in item:
                score_map[item["id"]] = item

        for idea in ideas:
            scores = score_map.get(idea.id, {})
            idea.novelty_score = float(scores.get("novelty_score", 0.5))
            idea.feasibility_score = float(scores.get("feasibility_score", 0.5))
            idea.final_score = _calculate_final_score(idea, weights)

        return ideas


# ──────────────────────────────────────────────
# 6. Convergence Ranker
# ──────────────────────────────────────────────

def _diverse_top_k(ideas: list[Idea], k: int) -> list[Idea]:
    """다양성 보정: source_domains가 겹치지 않는 아이디어 우선 선별."""
    if not ideas:
        return []

    sorted_ideas = sorted(ideas, key=lambda x: x.final_score, reverse=True)
    selected = [sorted_ideas[0]]

    for idea in sorted_ideas[1:]:
        if len(selected) >= k:
            break
        is_diverse = not any(
            set(idea.source_domains) & set(s.source_domains)
            for s in selected
        )
        if is_diverse:
            selected.append(idea)

    if len(selected) < k:
        remaining = [i for i in sorted_ideas if i not in selected]
        selected.extend(remaining[: k - len(selected)])

    return selected


class ConvergenceRanker:
    def __init__(self, use_diverse_ranking: bool = True) -> None:
        self.use_diverse_ranking = use_diverse_ranking

    def run(self, ideas: list[Idea], top_k: int) -> list[Idea]:
        if not ideas:
            return []

        if self.use_diverse_ranking:
            result = _diverse_top_k(ideas, top_k)
        else:
            sorted_ideas = sorted(ideas, key=lambda x: x.final_score, reverse=True)
            result = sorted_ideas[:top_k]

        if len(result) < top_k:
            logger.warning("ConvergenceRanker: got %d ideas but top_k=%d", len(result), top_k)
        return result


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

class ConnectionEngine:
    """
    LangGraph 기반 아이디어 생성 파이프라인.

    EngineConfig를 통해 LLM 클라이언트, 활성 제너레이터, 스코어 가중치,
    우연 도메인 풀, 프롬프트 등을 서비스별로 교체할 수 있음.
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()
        self._client = self._config.llm_client or ClaudeClient(model=self._config.model)

        # 제너레이터 인스턴스 생성 (DI)
        self._divergence_gen = DivergenceGenerator(self._client, self._config)
        self._cross_linker = CrossDomainLinker(self._client, self._config)
        self._constraint_relaxer = ConstraintRelaxer(self._client, self._config)
        self._serendipity_gen = SerendipityGenerator(self._client, self._config)
        self._novelty_scorer = NoveltyScorer(self._client, self._config)
        self._ranker = ConvergenceRanker(self._config.use_diverse_ranking)

        self._graph = self._build_graph()

    def _build_graph(self):
        enabled = set(self._config.enabled_generators)
        extra = self._config.extra_generators

        graph = StateGraph(ConnectionState)

        # ── 노드 클로저 (self 캡처) ──
        def diverge_node(state: ConnectionState) -> dict:
            ideas = self._divergence_gen.run(state["bundle"])
            logger.info("DivergenceGenerator produced %d ideas", len(ideas))
            return {"diverged_ideas": ideas}

        def cross_link_node(state: ConnectionState) -> dict:
            ideas = self._cross_linker.run(
                state["bundle"], state.get("diverged_ideas", [])
            )
            logger.info("CrossDomainLinker produced %d ideas", len(ideas))
            return {"linked_ideas": ideas}

        def relax_node(state: ConnectionState) -> dict:
            ideas = self._constraint_relaxer.run(state["bundle"])
            logger.info("ConstraintRelaxer produced %d ideas", len(ideas))
            return {"relaxed_ideas": ideas}

        def serendipity_node(state: ConnectionState) -> dict:
            ideas = self._serendipity_gen.run(state["bundle"])
            return {"serendipity_ideas": ideas}

        def extra_node(state: ConnectionState) -> dict:
            if not extra:
                return {"extra_ideas": []}
            all_extra: list[Idea] = []
            for gen in extra:
                try:
                    all_extra.extend(gen.run(state["bundle"]))
                except Exception as e:
                    logger.warning("extra_generator %s failed: %s", gen, e)
            return {"extra_ideas": all_extra}

        def merge_node(state: ConnectionState) -> dict:
            all_ideas = (
                state.get("diverged_ideas", [])
                + state.get("linked_ideas", [])
                + state.get("relaxed_ideas", [])
                + state.get("serendipity_ideas", [])
                + state.get("extra_ideas", [])
            )
            logger.info("merge_node: total %d ideas", len(all_ideas))
            return {"all_ideas": all_ideas}

        def score_node(state: ConnectionState) -> dict:
            bundle = state["bundle"]
            scored = self._novelty_scorer.run(
                state.get("all_ideas", []),
                problem_goal=bundle.problem.goal,
                problem_constraints=bundle.problem.constraints,
            )
            return {"scored_ideas": scored}

        def rank_node(state: ConnectionState) -> dict:
            bundle = state["bundle"]
            ideas = state.get("scored_ideas", [])
            top_ideas = self._ranker.run(ideas, top_k=bundle.problem.top_k)

            divergence_log = [
                f"{idea.source_domains} → {idea.connections}"
                for idea in ideas
                if len(idea.source_domains) > 1
            ]
            idea_set = IdeaSet(
                problem=bundle.problem,
                all_ideas=ideas,
                top_ideas=top_ideas,
                divergence_log=divergence_log,
            )
            return {"idea_set": idea_set}

        # ── 노드 등록 ──
        graph.add_node("diverge", diverge_node)
        if "cross_link" in enabled:
            graph.add_node("cross_link", cross_link_node)
        if "relax" in enabled:
            graph.add_node("relax", relax_node)
        if "serendipity" in enabled:
            graph.add_node("serendipity", serendipity_node)
        if extra:
            graph.add_node("extra", extra_node)
        graph.add_node("merge", merge_node)
        graph.add_node("score", score_node)
        graph.add_node("rank", rank_node)

        # ── 엣지 연결 ──
        graph.set_entry_point("diverge")
        for name in ("cross_link", "relax", "serendipity"):
            if name in enabled:
                graph.add_edge("diverge", name)
                graph.add_edge(name, "merge")
        if extra:
            graph.add_edge("diverge", "extra")
            graph.add_edge("extra", "merge")
        # diverge → merge 직접 연결 (다른 노드 없을 때 대비)
        if not (enabled & {"cross_link", "relax", "serendipity"}) and not extra:
            graph.add_edge("diverge", "merge")

        graph.add_edge("merge", "score")
        graph.add_edge("score", "rank")
        graph.add_edge("rank", END)

        return graph.compile()

    def run(self, bundle: InputBundle) -> IdeaSet:
        initial_state: ConnectionState = {
            "bundle": bundle,
            "diverged_ideas": [],
            "linked_ideas": [],
            "relaxed_ideas": [],
            "serendipity_ideas": [],
            "extra_ideas": [],
            "all_ideas": [],
            "scored_ideas": [],
            "idea_set": IdeaSet(problem=bundle.problem),
        }
        final_state = self._graph.invoke(initial_state)
        return final_state["idea_set"]
