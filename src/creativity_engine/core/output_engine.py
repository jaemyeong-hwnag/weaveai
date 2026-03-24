from __future__ import annotations

import logging
import re

from ..config import EngineConfig
from ..llm.base import BaseLLMClient
from ..llm.claude import ClaudeClient
from .models import Action, ActionType, Idea, IdeaSet, Solution

logger = logging.getLogger(__name__)

_DEFAULT_CONFIDENCE = 0.5


# ──────────────────────────────────────────────
# Prompt Templates
# ──────────────────────────────────────────────

_FORMATTER_SYSTEM = """\
ROLE: 아이디어→솔루션 변환기
구체적·실행가능 솔루션을 핵심단계+기대효과 포함해 작성."""

_FORMATTER_USER = """\
goal:{goal}|const:{constraints}
idea:{idea_content}|why:{rationale}|sd:{source_domains}
→300자 이내 솔루션"""

_REFLECTOR_SYSTEM = """\
ROLE: 솔루션 평가 비평가
ABBREV: ns=novelty_score fs=feasibility_score
강점·한계·개선방향 간결 평가 + 신뢰도(0.0~1.0) 제시.

<out>
평가: [내용]
신뢰도: [숫자]</out>"""

_REFLECTOR_USER = """\
goal:{goal}|const:{constraints}
sol:{solution_text}
idea:{idea_content}|ns:{novelty_score}|fs:{feasibility_score}
→평가+신뢰도"""


# ──────────────────────────────────────────────
# Solution Formatter
# ──────────────────────────────────────────────

class SolutionFormatter:
    def __init__(
        self, client: BaseLLMClient | None = None, config: EngineConfig | None = None
    ) -> None:
        cfg = config or EngineConfig()
        self._client = client or ClaudeClient(model=cfg.model)
        self._config = cfg
        self._system = cfg.prompt_overrides.get("formatter", _FORMATTER_SYSTEM)

    def format(self, idea_set: IdeaSet) -> tuple[Idea, str]:
        selected = idea_set.top_ideas[0] if idea_set.top_ideas else (
            idea_set.all_ideas[0] if idea_set.all_ideas else None
        )

        if selected is None:
            return (
                Idea(content="솔루션을 생성할 수 없습니다.", rationale="아이디어 없음"),
                "솔루션을 생성할 수 없습니다.",
            )

        problem = idea_set.problem
        user = _FORMATTER_USER.format(
            goal=problem.goal,
            constraints=", ".join(problem.constraints) or "없음",
            idea_content=selected.content,
            rationale=selected.rationale,
            source_domains=", ".join(selected.source_domains),
        )
        try:
            solution_text = self._client.call(
                self._system, user, self._config.output_max_tokens
            ).strip()
        except Exception as e:
            logger.warning("SolutionFormatter call failed: %s", e)
            solution_text = selected.content

        return selected, solution_text


# ──────────────────────────────────────────────
# Executor
# ──────────────────────────────────────────────

class Executor:
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

class Reflector:
    def __init__(
        self, client: BaseLLMClient | None = None, config: EngineConfig | None = None
    ) -> None:
        cfg = config or EngineConfig()
        self._client = client or ClaudeClient(model=cfg.model)
        self._config = cfg
        self._system = cfg.prompt_overrides.get("reflector", _REFLECTOR_SYSTEM)

    def reflect(
        self,
        solution_text: str,
        selected_idea: Idea,
        idea_set: IdeaSet,
        rounds: int,
    ) -> tuple[str | None, float]:
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
            raw = self._client.call(
                self._system, user, self._config.output_max_tokens
            ).strip()
        except Exception as e:
            logger.warning("Reflector call failed: %s", e)
            return None, _DEFAULT_CONFIDENCE

        reflection, confidence = _parse_reflection(raw)
        return reflection, confidence


def _parse_reflection(text: str) -> tuple[str, float]:
    reflection = text
    confidence = _DEFAULT_CONFIDENCE

    match = re.search(r"신뢰도[:\s]*([0-9.]+)", text)
    if match:
        try:
            confidence = float(match.group(1))
            confidence = min(max(confidence, 0.0), 1.0)
        except ValueError:
            pass

    lines = [line for line in text.splitlines() if not line.strip().startswith("신뢰도")]
    reflection = "\n".join(lines).strip()

    return reflection, confidence


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

class OutputEngine:
    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()
        self._client = self._config.llm_client or ClaudeClient(model=self._config.model)
        self._formatter = SolutionFormatter(self._client, self._config)
        self._executor = Executor()
        self._reflector = Reflector(self._client, self._config)

    def run(self, idea_set: IdeaSet) -> Solution:
        problem = idea_set.problem

        selected_idea, solution_text = self._formatter.format(idea_set)

        actions = [Action(type=ActionType.TEXT, payload={"text": solution_text})]
        actions = self._executor.execute(actions)

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
            metadata={"model": self._config.model},
        )
