from __future__ import annotations

import json
import logging
import os
import re
from typing import TypedDict

import anthropic
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from .models import Idea, IdeaSet, InputBundle

load_dotenv()
logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
_MODEL = "claude-sonnet-4-6"


# ──────────────────────────────────────────────
# LangGraph State
# ──────────────────────────────────────────────

class ConnectionState(TypedDict):
    bundle: InputBundle
    diverged_ideas: list[Idea]
    linked_ideas: list[Idea]
    relaxed_ideas: list[Idea]
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


def _call_claude(system: str, user: str, retries: int = 2) -> str:
    """Claude API 호출 with 재시도."""
    for attempt in range(retries + 1):
        try:
            response = _client.messages.create(
                model=_MODEL,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except Exception as e:
            if attempt == retries:
                raise
            logger.warning("Claude API attempt %d failed: %s", attempt + 1, e)
    return ""


def _parse_ideas_json(text: str, retries: int = 2) -> list[dict]:
    """JSON 파싱 with 재시도 (코드 펜스 제거 포함)."""
    for attempt in range(retries + 1):
        try:
            cleaned = _extract_json(text)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt == retries:
                logger.error("JSON parse failed after %d attempts: %s", retries + 1, text[:200])
                return []
    return []


def _summarize_knowledge(bundle: InputBundle) -> str:
    """지식 문서를 프롬프트용 요약 텍스트로 변환 (최대 3개, 각 500자)."""
    if not bundle.knowledge:
        return "관련 지식 없음"
    parts = []
    for doc in bundle.knowledge[:3]:
        parts.append(f"[{doc.source}] {doc.content[:500]}")
    return "\n".join(parts)


# ──────────────────────────────────────────────
# 1. Divergence Generator
# ──────────────────────────────────────────────

_DIVERGENCE_SYSTEM = """\
당신은 창의적 아이디어 생성 전문가입니다.
주어진 문제에 대해 {n}개의 서로 다른 아이디어를 생성하세요.

규칙:
- 각 아이디어는 완전히 다른 접근 방식을 사용해야 합니다.
- 실현 가능성을 지금 판단하지 마세요. 일단 생성합니다.
- 상식적인 것부터 파격적인 것까지 스펙트럼을 넓게 가져가세요.
- 각 아이디어에 영감을 준 분야(source_domains)를 반드시 명시하세요.

출력 형식: JSON 배열만 출력 (다른 텍스트 없이)
[
  {{
    "content": "아이디어 내용",
    "rationale": "왜 이 접근 방식인가",
    "source_domains": ["분야1", "분야2"],
    "connections": ["핵심 개념1", "핵심 개념2"]
  }}
]"""

_DIVERGENCE_USER = """\
목표: {goal}
제약: {constraints}
컨텍스트: {context_summary}
참고 지식: {knowledge_summary}

{n}개의 아이디어를 JSON으로 출력하세요."""


class DivergenceGenerator:
    def run(self, bundle: InputBundle) -> list[Idea]:
        n = bundle.problem.divergence_n
        system = _DIVERGENCE_SYSTEM.format(n=n)
        user = _DIVERGENCE_USER.format(
            goal=bundle.problem.goal,
            constraints=", ".join(bundle.problem.constraints) or "없음",
            context_summary=bundle.context_summary or "없음",
            knowledge_summary=_summarize_knowledge(bundle),
            n=n,
        )
        text = _call_claude(system, user)
        raw = _parse_ideas_json(text)
        return [Idea(**item) for item in raw if isinstance(item, dict)]


# ──────────────────────────────────────────────
# 2. Cross-domain Linker
# ──────────────────────────────────────────────

_CROSS_DOMAIN_SYSTEM = """\
당신은 서로 다른 분야의 패턴을 연결하는 전문가입니다.
주어진 아이디어 목록을 보고, 서로 다른 도메인 간의 유추(analogy)를 찾아
기존에 없는 새로운 아이디어를 {n}개 추가로 만들어내세요.

좋은 크로스도메인 연결의 예시:
- 군사 전략 → 비즈니스 경쟁 전략
- 생태계 다양성 → 포트폴리오 관리
- 게임 디자인 → 교육 동기 부여
- 생물 면역 시스템 → 사이버보안

출력 형식: JSON 배열만 출력 (다른 텍스트 없이)
각 아이디어의 source_domains에 연결된 두 도메인을 모두 포함하세요."""

_CROSS_DOMAIN_USER = """\
문제: {goal}
제약: {constraints}

기존 아이디어 (참고용):
{ideas_summary}

약한 신호 (재료):
{signals_text}

{n}개의 크로스도메인 아이디어를 JSON으로 출력하세요."""


class CrossDomainLinker:
    def run(self, bundle: InputBundle, existing_ideas: list[Idea]) -> list[Idea]:
        n = max(3, bundle.problem.divergence_n // 3)
        ideas_summary = "\n".join(
            f"- {idea.content} (출처: {idea.source_domains})"
            for idea in existing_ideas[:5]
        )
        signals_text = "\n".join(
            f"- [{s.signal_type}] {s.content}" for s in bundle.signals
        ) or "없음"

        system = _CROSS_DOMAIN_SYSTEM.format(n=n)
        user = _CROSS_DOMAIN_USER.format(
            goal=bundle.problem.goal,
            constraints=", ".join(bundle.problem.constraints) or "없음",
            ideas_summary=ideas_summary or "없음",
            signals_text=signals_text,
            n=n,
        )
        text = _call_claude(system, user)
        raw = _parse_ideas_json(text)
        return [Idea(**item) for item in raw if isinstance(item, dict)]


# ──────────────────────────────────────────────
# 3. Constraint Relaxer
# ──────────────────────────────────────────────

_RELAXER_SYSTEM = """\
당신은 창의적 제약 해체 전문가입니다.
주어진 제약 조건들을 하나씩 완화하거나 뒤집어서,
그 상태에서 가능한 아이디어를 탐색한 후
원래 제약 안에서 적용 가능한 핵심 인사이트를 추출하세요.

제약을 "해제하는 것"이 목표가 아닙니다.
제약을 해제했을 때 보이는 가능성의 본질을 추출하는 것이 목표입니다.

출력 형식: JSON 배열만 출력
[
  {{
    "content": "원래 제약 안에서 구현 가능한 아이디어",
    "rationale": "이 가정을 해제하면 보이는 것",
    "source_domains": ["역발상"],
    "connections": ["완화된 제약 키워드"]
  }}
]"""

_RELAXER_USER = """\
문제: {goal}
제약 조건들: {constraints}

각 제약을 뒤집어 역발상 아이디어를 생성하세요. JSON으로 출력하세요."""


class ConstraintRelaxer:
    def run(self, bundle: InputBundle) -> list[Idea]:
        if not bundle.problem.constraints:
            return []

        system = _RELAXER_SYSTEM
        user = _RELAXER_USER.format(
            goal=bundle.problem.goal,
            constraints="\n".join(f"- {c}" for c in bundle.problem.constraints),
        )
        text = _call_claude(system, user)
        raw = _parse_ideas_json(text)
        return [Idea(**item) for item in raw if isinstance(item, dict)]


# ──────────────────────────────────────────────
# 4. Novelty Scorer
# ──────────────────────────────────────────────

_SCORER_SYSTEM = """\
다음 아이디어를 두 가지 기준으로 평가하세요.

1. novelty_score (0.0~1.0): 얼마나 참신한가?
   - 0.0: 누구나 떠올리는 뻔한 해법
   - 0.5: 알려져 있지만 이 맥락에서는 신선한 적용
   - 1.0: 이 분야에서 전혀 시도된 적 없는 접근

2. feasibility_score (0.0~1.0): 주어진 제약 안에서 실현 가능한가?
   - 0.0: 제약 위반 또는 현실 불가능
   - 0.5: 도전적이지만 가능
   - 1.0: 즉시 실행 가능

출력: JSON 배열만 출력
[
  {{
    "id": "아이디어 ID",
    "novelty_score": 0.0~1.0,
    "feasibility_score": 0.0~1.0
  }}
]"""

_SCORER_USER = """\
문제: {goal}
제약: {constraints}

평가할 아이디어:
{ideas_text}

각 아이디어를 평가해 JSON으로 출력하세요."""


def _calculate_final_score(idea: Idea, weights: dict | None = None) -> float:
    w = weights or {"novelty": 0.6, "feasibility": 0.4}
    score = idea.novelty_score * w["novelty"] + idea.feasibility_score * w["feasibility"]
    return round(min(max(score, 0.0), 1.0), 4)


class NoveltyScorer:
    def run(
        self,
        ideas: list[Idea],
        problem_goal: str,
        problem_constraints: list[str],
        score_weights: dict | None = None,
    ) -> list[Idea]:
        if not ideas:
            return ideas

        ideas_text = "\n".join(
            f"ID: {idea.id}\n내용: {idea.content}"
            for idea in ideas
        )
        user = _SCORER_USER.format(
            goal=problem_goal,
            constraints=", ".join(problem_constraints) or "없음",
            ideas_text=ideas_text,
        )
        text = _call_claude(_SCORER_SYSTEM, user)
        raw = _parse_ideas_json(text)

        # id → scores 매핑
        score_map: dict[str, dict] = {}
        for item in raw:
            if isinstance(item, dict) and "id" in item:
                score_map[item["id"]] = item

        for idea in ideas:
            scores = score_map.get(idea.id, {})
            idea.novelty_score = float(scores.get("novelty_score", 0.5))
            idea.feasibility_score = float(scores.get("feasibility_score", 0.5))
            idea.final_score = _calculate_final_score(idea, score_weights)

        return ideas


# ──────────────────────────────────────────────
# 5. Convergence Ranker
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

    # 다양성 기준으로 부족하면 점수 순으로 채움
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
            logger.warning(
                "ConvergenceRanker: got %d ideas but top_k=%d", len(result), top_k
            )
        return result


# ──────────────────────────────────────────────
# LangGraph 노드 함수 (모듈 레벨)
# ──────────────────────────────────────────────

_divergence_gen = DivergenceGenerator()
_cross_linker = CrossDomainLinker()
_constraint_relaxer = ConstraintRelaxer()
_novelty_scorer = NoveltyScorer()


def diverge_node(state: ConnectionState) -> dict:
    bundle = state["bundle"]
    ideas = _divergence_gen.run(bundle)
    logger.info("DivergenceGenerator produced %d ideas", len(ideas))
    return {"diverged_ideas": ideas}


def cross_link_node(state: ConnectionState) -> dict:
    bundle = state["bundle"]
    existing = state.get("diverged_ideas", [])
    ideas = _cross_linker.run(bundle, existing)
    logger.info("CrossDomainLinker produced %d ideas", len(ideas))
    return {"linked_ideas": ideas}


def relax_node(state: ConnectionState) -> dict:
    bundle = state["bundle"]
    ideas = _constraint_relaxer.run(bundle)
    logger.info("ConstraintRelaxer produced %d ideas", len(ideas))
    return {"relaxed_ideas": ideas}


def merge_node(state: ConnectionState) -> dict:
    all_ideas = (
        state.get("diverged_ideas", [])
        + state.get("linked_ideas", [])
        + state.get("relaxed_ideas", [])
    )
    logger.info("merge_node: total %d ideas", len(all_ideas))
    return {"all_ideas": all_ideas}


def score_node(state: ConnectionState) -> dict:
    bundle = state["bundle"]
    ideas = state.get("all_ideas", [])
    scored = _novelty_scorer.run(
        ideas,
        problem_goal=bundle.problem.goal,
        problem_constraints=bundle.problem.constraints,
    )
    return {"scored_ideas": scored}


def rank_node(state: ConnectionState) -> dict:
    bundle = state["bundle"]
    ideas = state.get("scored_ideas", [])
    ranker = ConvergenceRanker()
    top_ideas = ranker.run(ideas, top_k=bundle.problem.top_k)

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


# ──────────────────────────────────────────────
# Graph Builder
# ──────────────────────────────────────────────

def build_connection_graph():
    graph = StateGraph(ConnectionState)

    graph.add_node("diverge", diverge_node)
    graph.add_node("cross_link", cross_link_node)
    graph.add_node("relax", relax_node)
    graph.add_node("merge", merge_node)
    graph.add_node("score", score_node)
    graph.add_node("rank", rank_node)

    graph.set_entry_point("diverge")
    graph.add_edge("diverge", "cross_link")
    graph.add_edge("diverge", "relax")
    graph.add_edge("cross_link", "merge")
    graph.add_edge("relax", "merge")
    graph.add_edge("merge", "score")
    graph.add_edge("score", "rank")
    graph.add_edge("rank", END)

    return graph.compile()


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

class ConnectionEngine:
    def __init__(
        self,
        extra_generators: list = [],
        score_weights: dict | None = None,
        use_diverse_ranking: bool = True,
    ) -> None:
        self._score_weights = score_weights
        self._use_diverse_ranking = use_diverse_ranking
        self._graph = build_connection_graph()

    def run(self, bundle: InputBundle) -> IdeaSet:
        initial_state: ConnectionState = {
            "bundle": bundle,
            "diverged_ideas": [],
            "linked_ideas": [],
            "relaxed_ideas": [],
            "all_ideas": [],
            "scored_ideas": [],
            "idea_set": IdeaSet(problem=bundle.problem),
        }
        final_state = self._graph.invoke(initial_state)
        return final_state["idea_set"]
