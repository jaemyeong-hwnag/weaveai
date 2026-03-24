from __future__ import annotations

from typing import Any

from ..core.models import ActionType, CreativityProblem, Solution
from .base import DomainAdapter


class SoftwareAdapter(DomainAdapter):
    """
    소프트웨어 설계 도메인 어댑터.
    아키텍처 설계, 기술 선택, 시스템 설계 문제에 사용.

    사용 예시:
        engine = CreativityEngine(adapter=SoftwareAdapter())
        result = engine.run({
            "problem": "마이크로서비스 간 데이터 일관성 보장이 어렵다",
            "current_stack": ["Python", "FastAPI", "PostgreSQL", "RabbitMQ"],
            "scale": "DAU 10만",
            "nfr": ["99.9% 가용성", "응답시간 200ms 이하"],
            "team_size": 4,
            "constraints": ["기존 DB 교체 불가", "6주 내 구현"],
        })
    """

    def format_problem(self, raw: dict | str) -> CreativityProblem:
        if isinstance(raw, str):
            return CreativityProblem(goal=raw, domain_hint="software")

        problem = raw.get("problem", "")
        stack = raw.get("current_stack", [])
        nfr = raw.get("nfr", [])
        scale = raw.get("scale", "")

        goal = (
            f"기술적 문제: {problem}\n"
            f"현재 스택: {', '.join(stack)}\n"
            f"규모: {scale}\n"
            f"비기능 요구사항: {', '.join(nfr)}"
        )

        constraints = list(raw.get("constraints", []))
        if raw.get("team_size"):
            constraints.append(f"팀 규모: {raw['team_size']}명")

        return CreativityProblem(
            goal=goal,
            constraints=constraints,
            context={
                "stack": stack,
                "nfr": nfr,
                "scale": scale,
                "team_size": raw.get("team_size"),
            },
            domain_hint="software",
            divergence_n=8,
            top_k=3,
            max_reflection_rounds=2,
        )

    def render_solution(self, solution: Solution) -> dict[str, Any]:
        options = []
        for idea in solution.idea_set.top_ideas:
            options.append({
                "pattern": idea.content,
                "rationale": idea.rationale,
                "inspired_by": idea.source_domains,
                "complexity": round(1 - idea.feasibility_score, 4),
                "novelty": idea.novelty_score,
                "key_concepts": idea.connections,
            })

        return {
            "design_options": options,
            "recommended_design": solution.solution_text,
            "trade_offs": solution.reflection,
            "implementation_hints": [
                action.result
                for action in solution.actions
                if action.type == ActionType.TEXT and action.result
            ],
            "confidence": solution.confidence,
        }
