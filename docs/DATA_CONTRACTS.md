# Data Contracts

레이어 간에 주고받는 모든 데이터 구조를 정의합니다.  
이 파일이 확정되면 각 레이어를 **병렬로 개발·교체**할 수 있습니다.

---

## 전체 흐름 한눈에

```
raw input (dict)
    → CreativityProblem   [DomainAdapter.format_problem]
    → InputBundle         [InputEngine.run]
    → IdeaSet             [ConnectionEngine.run]
    → Solution            [OutputEngine.run]
    → any (dict/str/...)  [DomainAdapter.render_solution]
```

---

## 1. CreativityProblem

외부 입력을 표준화한 엔진 입력 포맷.  
`DomainAdapter.format_problem()`이 반환합니다.

```python
from pydantic import BaseModel
from typing import Any

class CreativityProblem(BaseModel):
    goal: str
    # 달성하려는 목표를 한 문장으로.
    # 예: "원격 근무자의 집중력 저하 문제를 해결하고 싶다"

    constraints: list[str] = []
    # 반드시 지켜야 할 제약 조건 목록.
    # 예: ["예산 50만원 이하", "앱 개발 불가"]

    context: dict[str, Any] = {}
    # 추가 맥락 정보 (자유 형식).
    # 예: {"team_size": 5, "industry": "스타트업", "deadline": "2주"}

    domain_hint: str | None = None
    # 엔진이 참고할 도메인 힌트 (선택).
    # 예: "legal", "marketing", "software"
    # None이면 엔진이 범용 전략으로 처리.

    divergence_n: int = 10
    # Divergence Generator가 생성할 아이디어 수.
    # 많을수록 창의적, 적을수록 빠름. 기본값 10.

    top_k: int = 3
    # Convergence Ranker가 최종 선별할 아이디어 수.
    # 기본값 3.

    max_reflection_rounds: int = 2
    # Reflector가 재시도하는 최대 횟수.
    # 0이면 반성 루프 없이 1회만 실행.
```

---

## 2. Document / Signal (InputEngine 내부)

```python
class Document(BaseModel):
    content: str
    source: str           # "web", "rag", "user_upload" 등
    relevance: float      # 0.0 ~ 1.0
    metadata: dict = {}

class Signal(BaseModel):
    content: str
    signal_type: str      # "edge_case", "trend", "counter_example"
    strength: float       # 0.0 ~ 1.0  (약한 신호일수록 낮음)
```

---

## 3. InputBundle

`InputEngine`이 반환하는 표준 묶음.  
`ConnectionEngine`의 입력이 됩니다.

```python
class InputBundle(BaseModel):
    problem: CreativityProblem

    knowledge: list[Document] = []
    # Knowledge Retriever가 수집한 관련 문서들.

    context_summary: str = ""
    # Context Builder가 정제한 컨텍스트 요약 (LLM 프롬프트에 직접 삽입).

    signals: list[Signal] = []
    # Signal Collector가 감지한 약한 신호들.
    # 크로스도메인 연결의 재료가 됩니다.

    metadata: dict = {}
    # 처리 시간, 소스 수 등 디버깅용 메타데이터.
```

---

## 4. Idea

`ConnectionEngine` 내부에서 다루는 단일 아이디어 단위.

```python
class Idea(BaseModel):
    id: str                       # UUID
    content: str                  # 아이디어 본문
    rationale: str                # 왜 이 아이디어인가
    source_domains: list[str]     # 영감을 준 도메인들
    # 예: ["심리학", "게임디자인"] → 집중력 문제에 게임화 적용
    connections: list[str]        # 연결된 개념 키워드들
    novelty_score: float          # 0.0 ~ 1.0  (참신성)
    feasibility_score: float      # 0.0 ~ 1.0  (실현가능성)
    final_score: float            # 종합 점수 (Ranker가 계산)
```

---

## 5. IdeaSet

`ConnectionEngine`이 반환하는 결과.  
`OutputEngine`의 입력이 됩니다.

```python
class IdeaSet(BaseModel):
    problem: CreativityProblem

    all_ideas: list[Idea]
    # Divergence Generator가 생성한 전체 아이디어 목록.

    top_ideas: list[Idea]
    # Convergence Ranker가 선별한 상위 K개.
    # len(top_ideas) == problem.top_k

    divergence_log: list[str] = []
    # 어떤 크로스도메인 연결이 시도됐는지 기록.
    # 디버깅·설명 가능성용.
```

---

## 6. Action

`OutputEngine`이 실행할 수 있는 단위 액션.

```python
class ActionType(str, Enum):
    TEXT    = "text"      # 텍스트 출력
    SEARCH  = "search"    # 웹 검색
    CODE    = "code"      # 코드 실행
    API     = "api"       # 외부 API 호출
    CUSTOM  = "custom"    # 어댑터 정의 액션

class Action(BaseModel):
    type: ActionType
    payload: dict         # 액션별 파라미터
    result: Any = None    # Executor가 채워넣음
```

---

## 7. Solution

`OutputEngine`이 반환하는 최종 결과.  
`DomainAdapter.render_solution()`의 입력이 됩니다.

```python
class Solution(BaseModel):
    problem: CreativityProblem
    idea_set: IdeaSet

    selected_idea: Idea
    # 최종 선택된 아이디어 (top_ideas[0] 또는 Reflector 재선택).

    solution_text: str
    # 선택된 아이디어를 자연어로 풀어쓴 솔루션.

    actions: list[Action] = []
    # 실행된 액션과 결과들.

    reflection: str | None = None
    # Reflector의 자기평가 텍스트.
    # "이 솔루션의 한계는 X이며, Y를 추가로 고려해야 한다."

    reflection_rounds: int = 0
    # 실제로 반성 루프를 몇 번 돌았는지.

    confidence: float
    # 0.0 ~ 1.0  (에이전트의 솔루션 신뢰도 자기평가).

    metadata: dict = {}
    # 처리 시간, 토큰 사용량 등.
```

---

## 8. DomainAdapter 인터페이스

```python
from abc import ABC, abstractmethod

class DomainAdapter(ABC):

    @abstractmethod
    def format_problem(self, raw: dict | str) -> CreativityProblem:
        """
        도메인 입력 → CreativityProblem 변환.

        raw가 str이면 goal로 처리하고 나머지는 기본값.
        raw가 dict이면 도메인별 키를 파싱해 매핑.

        이 메서드 안에서만 도메인 용어가 등장해야 합니다.
        """

    @abstractmethod
    def render_solution(self, solution: Solution) -> Any:
        """
        Solution → 도메인 출력 포맷 변환.

        반환 타입 제한 없음 (dict, str, 도메인 객체 등).
        이 메서드 안에서만 도메인 출력 로직이 존재해야 합니다.
        """

    def validate_problem(self, problem: CreativityProblem) -> list[str]:
        """
        (선택 구현) 도메인 특화 입력 유효성 검사.
        반환: 경고 메시지 목록 (빈 리스트면 이상 없음).
        """
        return []
```

---

## 불변 규칙

1. **엔진 레이어는 `CreativityProblem`, `InputBundle`, `IdeaSet`, `Solution`만 다룬다.**  
   도메인 특화 타입이 엔진 코드에 등장하면 설계 위반입니다.

2. **`domain_hint`는 힌트일 뿐, 분기 조건이 아니다.**  
   `if problem.domain_hint == "legal":` 같은 코드는 엔진에 절대 없어야 합니다.

3. **모든 모델은 Pydantic BaseModel을 상속한다.**  
   직렬화·역직렬화, 타입 검증, Claude Code 자동완성을 위해.

4. **score 필드는 항상 0.0 ~ 1.0 범위.**  
   백분율 아님. 0.7 = 70점.
