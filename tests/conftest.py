"""pytest 공통 픽스처."""
import sys
import os

# src 경로를 패키지 경로로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from creativity_engine.llm.base import BaseLLMClient
from creativity_engine.core.models import (
    CreativityProblem,
    Document,
    Idea,
    IdeaSet,
    InputBundle,
    Signal,
    Solution,
    Action,
    ActionType,
)


class MockLLMClient(BaseLLMClient):
    """테스트용 LLM 클라이언트. call() 반환값을 직접 설정 가능."""

    def __init__(self, return_value: str = "[]") -> None:
        self._return_value = return_value
        self.calls: list[tuple[str, str]] = []

    def set_return(self, value: str) -> None:
        self._return_value = value

    def call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        self.calls.append((system, user))
        return self._return_value


@pytest.fixture
def mock_llm():
    """기본 MockLLMClient 픽스처."""
    return MockLLMClient()


@pytest.fixture
def basic_problem():
    return CreativityProblem(
        goal="원격 근무자의 집중력 저하 문제를 해결하고 싶다",
        constraints=["예산 50만원 이하", "앱 개발 불가"],
        context={"team_size": 5},
        divergence_n=3,
        top_k=2,
        max_reflection_rounds=0,
    )


@pytest.fixture
def sample_idea():
    return Idea(
        content="포모도로 기법 기반 집중 루틴 도입",
        rationale="시간 관리 심리학 기반",
        source_domains=["심리학", "생산성"],
        connections=["시간 관리", "집중력"],
        novelty_score=0.6,
        feasibility_score=0.8,
        final_score=0.68,
    )


@pytest.fixture
def sample_ideas(sample_idea):
    return [
        sample_idea,
        Idea(
            content="게임화된 집중도 추적 대시보드",
            rationale="게임 디자인의 보상 루프 적용",
            source_domains=["게임 디자인", "행동 경제학"],
            connections=["보상", "진행도"],
            novelty_score=0.8,
            feasibility_score=0.5,
            final_score=0.68,
        ),
        Idea(
            content="비동기 커뮤니케이션 원칙 도입",
            rationale="방해 요소 제거",
            source_domains=["조직 문화"],
            connections=["비동기", "딥워크"],
            novelty_score=0.4,
            feasibility_score=0.9,
            final_score=0.6,
        ),
    ]


@pytest.fixture
def sample_idea_set(basic_problem, sample_ideas):
    return IdeaSet(
        problem=basic_problem,
        all_ideas=sample_ideas,
        top_ideas=sample_ideas[:2],
    )


@pytest.fixture
def sample_bundle(basic_problem):
    return InputBundle(
        problem=basic_problem,
        knowledge=[
            Document(content="집중력 연구 결과", source="web", relevance=0.8)
        ],
        context_summary="목표: 원격 근무자 집중력 개선\n제약: 예산 50만원 이하, 앱 개발 불가",
        signals=[
            Signal(content="재택근무 집중력 저하 트렌드", signal_type="trend", strength=0.7)
        ],
    )
