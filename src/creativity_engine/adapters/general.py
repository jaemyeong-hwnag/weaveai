from __future__ import annotations

from typing import Any

from ..core.models import CreativityProblem, Solution
from .base import DomainAdapter


class GeneralAdapter(DomainAdapter):

    def format_problem(self, raw: dict | str) -> CreativityProblem:
        if isinstance(raw, str):
            return CreativityProblem(goal=raw)

        return CreativityProblem(
            goal=raw.get("goal", raw.get("problem", str(raw))),
            constraints=raw.get("constraints", []),
            context=raw.get("context", {}),
            divergence_n=raw.get("divergence_n", 10),
            top_k=raw.get("top_k", 3),
            max_reflection_rounds=raw.get("max_reflection_rounds", 2),
        )

    def render_solution(self, solution: Solution) -> dict[str, Any]:
        return {
            "solution": solution.solution_text,
            "top_ideas": [
                {
                    "content": idea.content,
                    "score": idea.final_score,
                    "from_domains": idea.source_domains,
                }
                for idea in solution.idea_set.top_ideas
            ],
            "reflection": solution.reflection,
            "confidence": solution.confidence,
        }
