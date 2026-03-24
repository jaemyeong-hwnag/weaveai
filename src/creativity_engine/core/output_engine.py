from __future__ import annotations

import logging
import os

import anthropic
from dotenv import load_dotenv

from .models import Action, ActionType, Idea, IdeaSet, Solution

load_dotenv()
logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
_MODEL = "claude-sonnet-4-6"

_DEFAULT_CONFIDENCE = 0.5


# ──────────────────────────────────────────────
# Solution Formatter
# ──────────────────────────────────────────────

_FORMATTER_SYSTEM = """\
당신은 아이디어를 실행 가능한 솔루션으로 정리하는 전문가입니다.
주어진 아이디어를 바탕으로 구체적이고 실행 가능한 솔루션을 자연어로 작성하세요.
명확하고 간결하게, 핵심 단계와 기대 효과를 포함하여 작성하세요."""

_FORMATTER_USER = """\
문제: {goal}
제약: {constraints}

선택된 아이디어: {idea_content}
아이디어 근거: {rationale}
영감 도메인: {source_domains}

위 아이디어를 바탕으로 구체적인 솔루션을 300자 이내로 작성하세요."""


class SolutionFormatter:
    def format(self, idea_set: IdeaSet) -> tuple[Idea, str]:
        """IdeaSet → (selected_idea, solution_text)"""
        selected = idea_set.top_ideas[0] if idea_set.top_ideas else (
            idea_set.all_ideas[0] if idea_set.all_ideas else None
        )

        if selected is None:
            return Idea(content="솔루션을 생성할 수 없습니다.", rationale="아이디어 없음"), "솔루션을 생성할 수 없습니다."

        problem = idea_set.problem
        user = _FORMATTER_USER.format(
            goal=problem.goal,
            constraints=", ".join(problem.constraints) or "없음",
            idea_content=selected.content,
            rationale=selected.rationale,
            source_domains=", ".join(selected.source_domains),
        )
        try:
            response = _client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=_FORMATTER_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            solution_text = response.content[0].text.strip()
        except Exception as e:
            logger.warning("SolutionFormatter Claude call failed: %s", e)
            solution_text = selected.content

        return selected, solution_text


# ──────────────────────────────────────────────
# Executor
# ──────────────────────────────────────────────

class Executor:
    """
    Action 실행기.
    현재 TEXT 타입만 구현. 나머지는 stub.
    """

    def execute(self, actions: list[Action]) -> list[Action]:
        for action in actions:
            if action.type == ActionType.TEXT:
                action.result = action.payload.get("text", "")
            else:
                action.result = {"status": "not_implemented", "type": action.type}
        return actions


# ──────────────────────────────────────────────
# Reflector
# ──────────────────────────────────────────────

_REFLECTOR_SYSTEM = """\
당신은 AI 솔루션의 품질을 객관적으로 평가하는 비평가입니다.
제시된 솔루션의 강점, 한계, 개선 방향을 간결하게 평가하고
신뢰도 점수(0.0~1.0)를 제시하세요.

출력 형식:
평가: [솔루션 평가 내용]
신뢰도: [0.0~1.0 숫자만]"""

_REFLECTOR_USER = """\
문제: {goal}
제약: {constraints}

솔루션: {solution_text}

선택된 아이디어:
- 내용: {idea_content}
- 참신성: {novelty_score}
- 실현가능성: {feasibility_score}

이 솔루션을 평가하고 신뢰도를 제시하세요."""


class Reflector:
    def reflect(
        self,
        solution_text: str,
        selected_idea: Idea,
        idea_set: IdeaSet,
        rounds: int,
    ) -> tuple[str | None, float]:
        """
        자기평가 실행.
        반환: (reflection_text, confidence)
        rounds=0이면 스킵, confidence=0.5 반환.
        """
        if rounds <= 0:
            return None, _DEFAULT_CONFIDENCE

        problem = idea_set.problem
        user = _REFLECTOR_USER.format(
            goal=problem.goal,
            constraints=", ".join(problem.constraints) or "없음",
            solution_text=solution_text,
            idea_content=selected_idea.content,
            novelty_score=selected_idea.novelty_score,
            feasibility_score=selected_idea.feasibility_score,
        )
        try:
            response = _client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=_REFLECTOR_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            raw = response.content[0].text.strip()
        except Exception as e:
            logger.warning("Reflector Claude call failed: %s", e)
            return None, _DEFAULT_CONFIDENCE

        reflection, confidence = _parse_reflection(raw)
        return reflection, confidence


def _parse_reflection(text: str) -> tuple[str, float]:
    """Reflector 출력에서 평가 텍스트와 신뢰도 추출."""
    import re

    reflection = text
    confidence = _DEFAULT_CONFIDENCE

    # 신뢰도 추출
    match = re.search(r"신뢰도[:\s]*([0-9.]+)", text)
    if match:
        try:
            confidence = float(match.group(1))
            confidence = min(max(confidence, 0.0), 1.0)
        except ValueError:
            pass

    # 평가 텍스트 추출 (신뢰도 줄 제거)
    lines = [line for line in text.splitlines() if not line.strip().startswith("신뢰도")]
    reflection = "\n".join(lines).strip()

    return reflection, confidence


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

class OutputEngine:
    def __init__(self) -> None:
        self._formatter = SolutionFormatter()
        self._executor = Executor()
        self._reflector = Reflector()

    def run(self, idea_set: IdeaSet) -> Solution:
        problem = idea_set.problem

        # 1. 솔루션 포맷팅
        selected_idea, solution_text = self._formatter.format(idea_set)

        # 2. 액션 실행 (기본: 텍스트 액션 1개 생성)
        actions = [
            Action(
                type=ActionType.TEXT,
                payload={"text": solution_text},
            )
        ]
        actions = self._executor.execute(actions)

        # 3. 자기평가 (reflection_rounds만큼 반복)
        reflection: str | None = None
        confidence: float = _DEFAULT_CONFIDENCE
        reflection_rounds = 0

        for _ in range(problem.max_reflection_rounds):
            r_text, r_conf = self._reflector.reflect(
                solution_text=solution_text,
                selected_idea=selected_idea,
                idea_set=idea_set,
                rounds=1,
            )
            if r_text:
                reflection = r_text
                confidence = r_conf
                reflection_rounds += 1

        return Solution(
            problem=problem,
            idea_set=idea_set,
            selected_idea=selected_idea,
            solution_text=solution_text,
            actions=actions,
            reflection=reflection,
            reflection_rounds=reflection_rounds,
            confidence=confidence,
            metadata={"model": _MODEL},
        )
