from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm.base import BaseLLMClient

# 기본 우연 도메인 풀 (서비스별 오버라이드 가능)
DEFAULT_SERENDIPITY_DOMAINS: list[str] = [
    "요리", "음악", "고고학", "우주항공", "패션", "원예", "마술", "스포츠",
    "신화", "지질학", "해양생물", "건축", "철학", "만화", "의학", "종교",
    "경제학", "수학", "영화", "곤충학", "기후학", "언어학", "무용", "항해",
]

# 기본 활성 제너레이터 (LangGraph 노드 이름과 일치)
DEFAULT_GENERATORS: list[str] = ["diverge", "cross_link", "relax", "serendipity"]


@dataclass
class EngineConfig:
    """
    서비스별 엔진 설정. 모든 파라미터를 오버라이드해 다른 서비스에 적용 가능.

    사용 예:
        # 기본 설정
        config = EngineConfig()

        # 법률 서비스 — diverge 집중, serendipity 제외
        config = EngineConfig(
            enabled_generators=["diverge", "cross_link"],
            score_weights={"novelty": 0.3, "feasibility": 0.7},
        )

        # 다른 LLM 공급자 주입
        config = EngineConfig(llm_client=MyOpenAIClient())
    """

    # ── LLM ──────────────────────────────────────────────────────────────
    # None이면 ClaudeClient(model=model) 자동 생성
    llm_client: BaseLLMClient | None = None
    model: str = "claude-sonnet-4-6"

    # ── 제너레이터 파이프라인 ───────────────────────────────────────────
    # 사용할 노드 이름 목록. 순서는 graph topology에 영향 없음 (병렬 실행)
    enabled_generators: list[str] = field(
        default_factory=lambda: list(DEFAULT_GENERATORS)
    )
    # 추가 제너레이터 (BaseGenerator 구현체 리스트)
    extra_generators: list = field(default_factory=list)

    # ── 스코어링 ─────────────────────────────────────────────────────────
    score_weights: dict[str, float] = field(
        default_factory=lambda: {"novelty": 0.6, "feasibility": 0.4}
    )
    use_diverse_ranking: bool = True

    # ── 우연(Serendipity) ────────────────────────────────────────────────
    serendipity_domains: list[str] = field(
        default_factory=lambda: list(DEFAULT_SERENDIPITY_DOMAINS)
    )

    # ── 토큰 한도 ────────────────────────────────────────────────────────
    connection_max_tokens: int = 4096
    output_max_tokens: int = 512

    # ── 입력 한도 ────────────────────────────────────────────────────────
    max_knowledge_docs: int = 3
    max_chars: int = 500

    # ── 프롬프트 오버라이드 ───────────────────────────────────────────────
    # 키: 컴포넌트 이름 ("diverge", "cross_link", "relax", "serendipity",
    #                   "scorer", "formatter", "reflector")
    # 값: system prompt 전체 오버라이드 문자열
    prompt_overrides: dict[str, str] = field(default_factory=dict)
