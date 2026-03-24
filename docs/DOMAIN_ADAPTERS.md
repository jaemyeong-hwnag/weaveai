# Domain Adapters

어댑터는 이 프레임워크를 새로운 도메인에 이식하는 유일한 접점입니다.
**엔진을 건드리지 않고 어댑터 파일 하나만 추가하면** 새 도메인이 지원됩니다.

---

## 어댑터 작성 규칙

### 해야 할 것

- `format_problem(raw)` 에서 도메인 입력을 `CreativityProblem`으로 변환
- `render_solution(solution)` 에서 `Solution`을 도메인 출력으로 변환
- 도메인 특화 로직은 **이 두 메서드 안에만** 작성

### 하지 말아야 할 것

- 엔진 내부 클래스(`ConnectionEngine`, `InputEngine` 등) 수정
- 다른 어댑터의 코드에 의존
- 어댑터에서 LLM API 직접 호출 (엔진이 담당)

---

## 기본 추상 클래스

```python
# src/creativity_engine/adapters/base.py

from abc import ABC, abstractmethod
from typing import Any
from ..core.models import CreativityProblem, Solution


class DomainAdapter(ABC):

    @abstractmethod
    def format_problem(self, raw: dict | str) -> CreativityProblem:
        """도메인 입력 → CreativityProblem"""
        ...

    @abstractmethod
    def render_solution(self, solution: Solution) -> Any:
        """Solution → 도메인 출력"""
        ...

    def validate_problem(self, problem: CreativityProblem) -> list[str]:
        """도메인 특화 입력 검증 (선택 구현). 경고 메시지 목록 반환."""
        return []

    def get_domain_name(self) -> str:
        """어댑터 이름. 로깅·디버깅용."""
        return self.__class__.__name__
```

---

## 범용 어댑터 (기본값)

도메인 힌트 없이 바로 쓸 수 있는 어댑터입니다.

```python
# src/creativity_engine/adapters/general.py

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
            serendipity=raw.get("serendipity", 0.0),
        )

    def render_solution(self, solution: Solution) -> dict:
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
```

---

## 예시 1: 법률 어댑터 (LegalAdapter)

### 사용 시나리오

```python
from creativity_engine import CreativityEngine
from creativity_engine.adapters import LegalAdapter

engine = CreativityEngine(adapter=LegalAdapter())

result = engine.run({
    "case_type": "계약 분쟁",
    "facts": "A사가 납품 기한을 3일 초과했고 B사는 전액 위약금을 요구 중",
    "client_position": "A사 (납품사)",
    "jurisdiction": "대한민국",
    "desired_outcome": "위약금 감액 또는 면제",
    "constraints": ["소송 비용 최소화", "거래 관계 유지 희망"],
})

print(result["legal_strategies"])
print(result["recommended_approach"])
print(result["risk_assessment"])
```

### 핵심 설정

```python
return CreativityProblem(
    ...
    divergence_n=8,     # 법률은 파격보다 실현가능한 전략 중심
    top_k=3,
    serendipity=0.0,    # 법률 문제에서 우연성은 기본적으로 비활성
)
```

---

## 예시 2: 마케팅 어댑터 (MarketingAdapter)

### 사용 시나리오

```python
from creativity_engine.adapters import MarketingAdapter

engine = CreativityEngine(adapter=MarketingAdapter())

result = engine.run({
    "product": "B2B SaaS 프로젝트 관리 툴",
    "target_audience": "50인 이하 스타트업 CTO",
    "challenge": "경쟁사 대비 인지도가 낮고 무료 전환율이 5%에 그침",
    "budget": "월 300만원",
    "channels_available": ["LinkedIn", "콘텐츠 마케팅", "커뮤니티"],
    "kpi": "3개월 내 무료 가입 500명",
})

print(result["campaign_concepts"])
print(result["execution_plan"])
print(result["expected_impact"])
```

### 핵심 설정

```python
return CreativityProblem(
    ...
    divergence_n=12,    # 마케팅은 창의적 발상이 핵심
    top_k=3,
)
```

---

## 예시 3: 소프트웨어 설계 어댑터 (SoftwareAdapter)

### 사용 시나리오

```python
from creativity_engine.adapters import SoftwareAdapter

engine = CreativityEngine(adapter=SoftwareAdapter())

result = engine.run({
    "problem": "마이크로서비스 간 데이터 일관성 보장이 어렵다",
    "current_stack": ["Python", "FastAPI", "PostgreSQL", "RabbitMQ"],
    "scale": "DAU 10만",
    "nfr": ["99.9% 가용성", "응답시간 200ms 이하"],
    "team_size": 4,
    "constraints": ["기존 DB 교체 불가", "6주 내 구현"],
})

print(result["design_options"])
print(result["recommended_design"])
print(result["trade_offs"])
```

### 핵심 설정

```python
return CreativityProblem(
    ...
    divergence_n=8,
    top_k=3,
    max_reflection_rounds=2,   # 기술 설계는 반성 루프 더 돌림
)
```

---

## 새 어댑터 빠르게 만들기

### 최소 구현

```python
from creativity_engine.adapters.base import DomainAdapter
from creativity_engine.core.models import CreativityProblem, Solution

class MyAdapter(DomainAdapter):

    def format_problem(self, raw: dict | str) -> CreativityProblem:
        if isinstance(raw, str):
            return CreativityProblem(goal=raw)
        return CreativityProblem(
            goal=raw["goal"],
            constraints=raw.get("constraints", []),
            divergence_n=raw.get("divergence_n", 10),
            serendipity=raw.get("serendipity", 0.0),
        )

    def render_solution(self, solution: Solution) -> dict:
        return {
            "result": solution.solution_text,
            "ideas": [idea.content for idea in solution.idea_set.top_ideas],
            "confidence": solution.confidence,
        }
```

### 검증 추가 (선택)

```python
    def validate_problem(self, problem: CreativityProblem) -> list[str]:
        warnings = []
        if not problem.constraints:
            warnings.append("제약 조건이 없습니다. 결과가 너무 광범위할 수 있습니다.")
        if problem.divergence_n < 3:
            warnings.append("divergence_n이 너무 작습니다. 최소 3 이상을 권장합니다.")
        return warnings
```

---

## 어댑터 등록 및 사용

```python
# src/creativity_engine/adapters/__init__.py 에 등록

from .general import GeneralAdapter
from .legal import LegalAdapter
from .marketing import MarketingAdapter
from .software import SoftwareAdapter

ADAPTER_REGISTRY = {
    "general": GeneralAdapter,
    "legal": LegalAdapter,
    "marketing": MarketingAdapter,
    "software": SoftwareAdapter,
}
```

```python
# 문자열로 어댑터 선택
from creativity_engine.adapters import get_adapter

engine = CreativityEngine(adapter=get_adapter("legal"))

# 없는 어댑터 → ValueError
engine = CreativityEngine(adapter=get_adapter("unknown"))
# ValueError: Unknown domain: unknown. Available: ['general', 'legal', ...]

# 기본값 사용 (없으면 GeneralAdapter)
from creativity_engine.adapters import get_adapter_or_default

engine = CreativityEngine(adapter=get_adapter_or_default("custom"))  # GeneralAdapter 반환
```

---

## EngineConfig와 어댑터 조합

어댑터는 **입출력 변환**을 담당하고, `EngineConfig`는 **엔진 동작**을 담당합니다.
둘은 독립적으로 조합할 수 있습니다.

```python
from creativity_engine import CreativityEngine
from creativity_engine.config import EngineConfig
from creativity_engine.adapters import LegalAdapter

# 법률 어댑터 + 실현가능성 중시 설정
config = EngineConfig(
    enabled_generators=["diverge", "cross_link"],
    score_weights={"novelty": 0.3, "feasibility": 0.7},
)

engine = CreativityEngine(adapter=LegalAdapter(), config=config)
```

---

## 어댑터 작성 체크리스트

```
[ ] DomainAdapter를 상속했는가?
[ ] format_problem 이 항상 CreativityProblem을 반환하는가?
[ ] render_solution 이 Solution만 입력으로 받는가?
[ ] 엔진 내부 클래스를 import하거나 수정하지 않았는가?
[ ] 어댑터 안에서 LLM API를 직접 호출하지 않는가?
[ ] str 입력 처리가 있는가? (raw가 str일 때)
[ ] serendipity를 format_problem에서 raw에서 읽어 전달하는가? (선택)
[ ] validate_problem 에 도메인 특화 검증을 추가했는가? (선택)
```
