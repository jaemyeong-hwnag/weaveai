from __future__ import annotations

from typing import Any

from ..core.models import CreativityProblem, Solution
from .base import DomainAdapter


class LegalAdapter(DomainAdapter):
    """
    법률 도메인 어댑터.
    계약 분쟁, 법률 전략 수립 등에 사용.

    사용 예시:
        engine = CreativityEngine(adapter=LegalAdapter())
        result = engine.run({
            "case_type": "계약 분쟁",
            "facts": "A사가 납품 기한을 3일 초과...",
            "client_position": "A사 (납품사)",
            "jurisdiction": "대한민국",
            "desired_outcome": "위약금 감액 또는 면제",
            "constraints": ["소송 비용 최소화", "거래 관계 유지 희망"],
        })
    """

    def format_problem(self, raw: dict | str) -> CreativityProblem:
        if isinstance(raw, str):
            return CreativityProblem(goal=raw, domain_hint="legal")

        facts = raw.get("facts", "")
        client_position = raw.get("client_position", "")
        desired_outcome = raw.get("desired_outcome", "")

        goal = (
            f"법적 상황: {facts}\n"
            f"의뢰인 입장: {client_position}\n"
            f"목표: {desired_outcome}"
        )

        constraints = list(raw.get("constraints", []))
        if raw.get("jurisdiction"):
            constraints.append(f"관할: {raw['jurisdiction']} 법률 적용")
        if raw.get("case_type"):
            constraints.append(f"사건 유형: {raw['case_type']}")

        return CreativityProblem(
            goal=goal,
            constraints=constraints,
            context={
                "case_type": raw.get("case_type"),
                "jurisdiction": raw.get("jurisdiction"),
                "client_position": raw.get("client_position"),
            },
            domain_hint="legal",
            divergence_n=8,
            top_k=3,
        )

    def render_solution(self, solution: Solution) -> dict[str, Any]:
        strategies = []
        for idea in solution.idea_set.top_ideas:
            strategies.append({
                "strategy": idea.content,
                "legal_basis": idea.rationale,
                "novelty": idea.novelty_score,
                "feasibility": idea.feasibility_score,
                "cross_domain_inspiration": idea.source_domains,
            })

        return {
            "legal_strategies": strategies,
            "recommended_approach": solution.solution_text,
            "risk_assessment": solution.reflection or "반성 루프 미실행",
            "confidence": solution.confidence,
            "disclaimer": "이 결과는 AI 보조 도구이며 법률 전문가의 검토가 필요합니다.",
        }

    def validate_problem(self, problem: CreativityProblem) -> list[str]:
        warnings = []
        if "관할" not in str(problem.constraints):
            warnings.append("관할 정보가 없습니다. 결과의 정확도가 낮아질 수 있습니다.")
        return warnings
