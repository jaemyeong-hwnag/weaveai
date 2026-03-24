from __future__ import annotations

from typing import Any

from ..core.models import CreativityProblem, Solution
from .base import DomainAdapter


class MarketingAdapter(DomainAdapter):
    """
    마케팅 도메인 어댑터.
    캠페인 기획, 성장 전략, 브랜드 포지셔닝 등에 사용.

    사용 예시:
        engine = CreativityEngine(adapter=MarketingAdapter())
        result = engine.run({
            "product": "B2B SaaS 프로젝트 관리 툴",
            "target_audience": "50인 이하 스타트업 CTO",
            "challenge": "경쟁사 대비 인지도가 낮고 무료 전환율이 5%에 그침",
            "budget": "월 300만원",
            "channels_available": ["LinkedIn", "콘텐츠 마케팅", "커뮤니티"],
            "kpi": "3개월 내 무료 가입 500명",
        })
    """

    def format_problem(self, raw: dict | str) -> CreativityProblem:
        if isinstance(raw, str):
            return CreativityProblem(goal=raw, domain_hint="marketing")

        product = raw.get("product", "")
        audience = raw.get("target_audience", "")
        challenge = raw.get("challenge", "")
        kpi = raw.get("kpi", "")

        goal = (
            f"제품: {product}\n"
            f"타겟: {audience}\n"
            f"해결할 문제: {challenge}\n"
            f"목표 KPI: {kpi}"
        )

        constraints: list[str] = []
        if raw.get("budget"):
            constraints.append(f"예산: {raw['budget']}")
        if raw.get("channels_available"):
            channels = ", ".join(raw["channels_available"])
            constraints.append(f"사용 가능 채널: {channels}")
        constraints.extend(raw.get("constraints", []))

        return CreativityProblem(
            goal=goal,
            constraints=constraints,
            context={
                "product": product,
                "kpi": kpi,
                "channels": raw.get("channels_available", []),
            },
            domain_hint="marketing",
            divergence_n=12,
            top_k=3,
        )

    def render_solution(self, solution: Solution) -> dict[str, Any]:
        concepts = []
        for i, idea in enumerate(solution.idea_set.top_ideas):
            concepts.append({
                "rank": i + 1,
                "concept_name": _extract_concept_name(idea.content),
                "description": idea.content,
                "channel_fit": _map_to_channels(
                    idea.source_domains,
                    solution.problem.context.get("channels", []),
                ),
                "creativity_score": idea.novelty_score,
                "execution_ease": idea.feasibility_score,
            })

        return {
            "campaign_concepts": concepts,
            "execution_plan": solution.solution_text,
            "expected_impact": solution.reflection,
            "inspiration_sources": list({
                domain
                for idea in solution.idea_set.top_ideas
                for domain in idea.source_domains
            }),
        }


def _extract_concept_name(content: str) -> str:
    """첫 문장을 캠페인 이름으로 사용."""
    return content.split(".")[0].strip()


def _map_to_channels(source_domains: list[str], available: list[str]) -> list[str]:
    """아이디어 출처 도메인을 사용 가능한 채널에 매핑 (단순 예시)."""
    return available[:2] if available else ["미정"]
