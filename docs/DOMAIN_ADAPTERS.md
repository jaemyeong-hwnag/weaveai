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
- 어댑터에서 Claude API 직접 호출 (엔진이 담당)

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
engine = CreativityEngine(adapter=LegalAdapter())

result = engine.run({
    "case_type": "계약 분쟁",
    "facts": "A사가 납품 기한을 3일 초과했고 B사는 전액 위약금을 요구 중",
    "client_position": "A사 (납품사)",
    "jurisdiction": "대한민국",
    "desired_outcome": "위약금 감액 또는 면제",
    "constraints": ["소송 비용 최소화", "거래 관계 유지 희망"],
})

# 출력: 법률 전략 문서 포맷
print(result["legal_strategies"])
print(result["risk_assessment"])
print(result["recommended_approach"])
```

### 구현

```python
# src/creativity_engine/adapters/legal.py

class LegalAdapter(DomainAdapter):

    def format_problem(self, raw: dict | str) -> CreativityProblem:
        if isinstance(raw, str):
            return CreativityProblem(goal=raw, domain_hint="legal")

        # 법률 입력 → 표준 포맷
        facts = raw.get("facts", "")
        client_position = raw.get("client_position", "")
        desired_outcome = raw.get("desired_outcome", "")

        goal = (
            f"법적 상황: {facts}\n"
            f"의뢰인 입장: {client_position}\n"
            f"목표: {desired_outcome}"
        )

        constraints = raw.get("constraints", [])
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
            divergence_n=8,   # 법률은 너무 파격적인 아이디어보다 실현가능한 전략 중심
            top_k=3,
        )

    def render_solution(self, solution: Solution) -> dict:
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
```

---

## 예시 2: 마케팅 어댑터 (MarketingAdapter)

### 사용 시나리오

```python
engine = CreativityEngine(adapter=MarketingAdapter())

result = engine.run({
    "product": "B2B SaaS 프로젝트 관리 툴",
    "target_audience": "50인 이하 스타트업 CTO",
    "challenge": "경쟁사 대비 인지도가 낮고 무료 전환율이 5%에 그침",
    "budget": "월 300만원",
    "channels_available": ["LinkedIn", "콘텐츠 마케팅", "커뮤니티"],
    "kpi": "3개월 내 무료 가입 500명",
})

print(result["campaign_concepts"])    # 캠페인 아이디어
print(result["execution_plan"])       # 실행 계획
print(result["expected_impact"])      # 예상 효과
```

### 구현

```python
# src/creativity_engine/adapters/marketing.py

class MarketingAdapter(DomainAdapter):

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

        constraints = []
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
            divergence_n=12,  # 마케팅은 창의적 발상이 핵심
            top_k=3,
        )

    def render_solution(self, solution: Solution) -> dict:
        concepts = []
        for i, idea in enumerate(solution.idea_set.top_ideas):
            concepts.append({
                "rank": i + 1,
                "concept_name": _extract_concept_name(idea.content),
                "description": idea.content,
                "channel_fit": _map_to_channels(
                    idea.source_domains,
                    solution.problem.context.get("channels", [])
                ),
                "creativity_score": idea.novelty_score,
                "execution_ease": idea.feasibility_score,
            })

        return {
            "campaign_concepts": concepts,
            "execution_plan": solution.solution_text,
            "expected_impact": solution.reflection,
            "inspiration_sources": list(set(
                domain
                for idea in solution.idea_set.top_ideas
                for domain in idea.source_domains
            )),
        }


def _extract_concept_name(content: str) -> str:
    """첫 문장을 캠페인 이름으로 사용."""
    return content.split(".")[0].strip()


def _map_to_channels(source_domains: list[str], available: list[str]) -> list[str]:
    """아이디어 출처 도메인을 사용 가능한 채널에 매핑 (단순 예시)."""
    return available[:2] if available else ["미정"]
```

---

## 예시 3: 소프트웨어 설계 어댑터 (SoftwareAdapter)

### 사용 시나리오

```python
engine = CreativityEngine(adapter=SoftwareAdapter())

result = engine.run({
    "problem": "마이크로서비스 간 데이터 일관성 보장이 어렵다",
    "current_stack": ["Python", "FastAPI", "PostgreSQL", "RabbitMQ"],
    "scale": "DAU 10만",
    "nfr": ["99.9% 가용성", "응답시간 200ms 이하"],
    "team_size": 4,
    "constraints": ["기존 DB 교체 불가", "6주 내 구현"],
})

print(result["design_options"])       # 설계 옵션들
print(result["recommended_design"])   # 추천 설계
print(result["trade_offs"])           # 트레이드오프 분석
print(result["implementation_hints"]) # 구현 힌트
```

### 구현

```python
# src/creativity_engine/adapters/software.py

class SoftwareAdapter(DomainAdapter):

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
            max_reflection_rounds=2,  # 기술 설계는 반성 루프 더 돌림
        )

    def render_solution(self, solution: Solution) -> dict:
        options = []
        for idea in solution.idea_set.top_ideas:
            options.append({
                "pattern": idea.content,
                "rationale": idea.rationale,
                "inspired_by": idea.source_domains,
                "complexity": 1 - idea.feasibility_score,   # 쉬울수록 복잡도 낮음
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
```

---

## 어댑터 체크리스트

새 어댑터를 만들 때 확인하세요.

```
[ ] DomainAdapter를 상속했는가?
[ ] format_problem 이 항상 CreativityProblem을 반환하는가?
[ ] render_solution 이 Solution만 입력으로 받는가?
[ ] 엔진 내부 클래스를 import하거나 수정하지 않았는가?
[ ] 어댑터 안에서 Claude API를 직접 호출하지 않는가?
[ ] domain_hint를 설정했는가? (선택이지만 권장)
[ ] validate_problem 에 도메인 특화 검증을 추가했는가? (선택)
[ ] 예시 입력/출력을 docstring에 기록했는가?
```

---

## 어댑터 등록 및 관리

```python
# src/creativity_engine/adapters/__init__.py

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

def get_adapter(domain: str) -> DomainAdapter:
    cls = ADAPTER_REGISTRY.get(domain)
    if not cls:
        raise ValueError(f"Unknown domain: {domain}. Available: {list(ADAPTER_REGISTRY)}")
    return cls()
```

```python
# 사용 예시
from creativity_engine.adapters import get_adapter

engine = CreativityEngine(adapter=get_adapter("legal"))
```
