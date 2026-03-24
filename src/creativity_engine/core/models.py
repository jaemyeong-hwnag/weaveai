from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    content: str = Field(description="문서 본문")
    source: str = Field(description="출처: 'web', 'rag', 'user_upload' 등")
    relevance: float = Field(default=1.0, ge=0.0, le=1.0, description="관련도 0.0~1.0")
    metadata: dict[str, Any] = Field(default_factory=dict)


class Signal(BaseModel):
    content: str = Field(description="신호 내용")
    signal_type: str = Field(description="'edge_case', 'trend', 'counter_example'")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="신호 강도 0.0~1.0")


class CreativityProblem(BaseModel):
    goal: str = Field(description="달성하려는 목표를 한 문장으로")
    constraints: list[str] = Field(default_factory=list, description="반드시 지켜야 할 제약 조건 목록")
    context: dict[str, Any] = Field(default_factory=dict, description="추가 맥락 정보 (자유 형식)")
    domain_hint: str | None = Field(default=None, description="엔진이 참고할 도메인 힌트 (선택)")
    divergence_n: int = Field(default=10, description="Divergence Generator가 생성할 아이디어 수")
    top_k: int = Field(default=3, description="Convergence Ranker가 최종 선별할 아이디어 수")
    max_reflection_rounds: int = Field(default=2, description="Reflector가 재시도하는 최대 횟수")


class Idea(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()), description="UUID")
    content: str = Field(description="아이디어 본문")
    rationale: str = Field(default="", description="왜 이 아이디어인가")
    source_domains: list[str] = Field(default_factory=list, description="영감을 준 도메인들")
    connections: list[str] = Field(default_factory=list, description="연결된 개념 키워드들")
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0, description="참신성 0.0~1.0")
    feasibility_score: float = Field(default=0.0, ge=0.0, le=1.0, description="실현가능성 0.0~1.0")
    final_score: float = Field(default=0.0, ge=0.0, le=1.0, description="종합 점수")


class IdeaSet(BaseModel):
    problem: CreativityProblem
    all_ideas: list[Idea] = Field(default_factory=list, description="전체 아이디어 목록")
    top_ideas: list[Idea] = Field(default_factory=list, description="상위 K개 아이디어")
    divergence_log: list[str] = Field(default_factory=list, description="크로스도메인 연결 시도 기록")


class InputBundle(BaseModel):
    problem: CreativityProblem
    knowledge: list[Document] = Field(default_factory=list, description="수집된 관련 문서들")
    context_summary: str = Field(default="", description="정제된 컨텍스트 요약")
    signals: list[Signal] = Field(default_factory=list, description="감지된 약한 신호들")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionType(str, Enum):
    TEXT = "text"
    SEARCH = "search"
    CODE = "code"
    API = "api"
    CUSTOM = "custom"


class Action(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: ActionType
    payload: dict[str, Any] = Field(default_factory=dict, description="액션별 파라미터")
    result: Any = Field(default=None, description="Executor가 채워넣음")


class Solution(BaseModel):
    problem: CreativityProblem
    idea_set: IdeaSet
    selected_idea: Idea
    solution_text: str = Field(description="선택된 아이디어를 자연어로 풀어쓴 솔루션")
    actions: list[Action] = Field(default_factory=list, description="실행된 액션과 결과들")
    reflection: str | None = Field(default=None, description="Reflector의 자기평가 텍스트")
    reflection_rounds: int = Field(default=0, description="실제로 반성 루프를 몇 번 돌았는지")
    confidence: float = Field(ge=0.0, le=1.0, description="에이전트의 솔루션 신뢰도 자기평가")
    metadata: dict[str, Any] = Field(default_factory=dict)
