# Connection Engine

이 문서가 이 프레임워크의 핵심입니다.  
기존 오픈소스(LangGraph, CrewAI 등)가 제공하지 않는 **창의적 조합 로직**을 정의합니다.

---

## 전체 구조

```
InputBundle
    │
    ▼
DIVERGE 페이즈 (병렬)
    ├── Divergence Generator   → 아이디어 N개 생성
    ├── Cross-domain Linker    → 도메인 간 유추 연결
    └── Constraint Relaxer     → 가정 해체·역발상
    │
    ▼ (모든 아이디어 합산)
CONVERGE 페이즈 (순차)
    ├── Novelty Scorer         → 각 아이디어 점수화
    └── Convergence Ranker     → 상위 K개 선별
    │
    ▼
IdeaSet
```

---

## 1. Divergence Generator

**역할:** 주어진 문제에 대해 가능한 한 많은 아이디어를 생성합니다.  
품질보다 **수량·다양성**이 목표입니다. 판단하지 않습니다.

### 프롬프트 전략

```python
DIVERGENCE_SYSTEM = """
당신은 창의적 아이디어 생성 전문가입니다.
주어진 문제에 대해 {n}개의 서로 다른 아이디어를 생성하세요.

규칙:
- 각 아이디어는 완전히 다른 접근 방식을 사용해야 합니다.
- 실현 가능성을 지금 판단하지 마세요. 일단 생성합니다.
- 상식적인 것부터 파격적인 것까지 스펙트럼을 넓게 가져가세요.
- 각 아이디어에 영감을 준 분야(source_domain)를 반드시 명시하세요.

출력 형식: JSON 배열
[
  {{
    "content": "아이디어 내용",
    "rationale": "왜 이 접근 방식인가",
    "source_domains": ["분야1", "분야2"],
    "connections": ["핵심 개념1", "핵심 개념2"]
  }},
  ...
]
"""

DIVERGENCE_USER = """
목표: {goal}
제약: {constraints}
컨텍스트: {context_summary}
참고 지식: {knowledge_summary}

{n}개의 아이디어를 JSON으로 출력하세요.
"""
```

### 구현 노트

```python
class DivergenceGenerator:
    def run(self, bundle: InputBundle) -> list[Idea]:
        n = bundle.problem.divergence_n

        # Claude API 호출 (tools 없이 순수 생성)
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            system=DIVERGENCE_SYSTEM.format(n=n),
            messages=[{
                "role": "user",
                "content": DIVERGENCE_USER.format(
                    goal=bundle.problem.goal,
                    constraints=bundle.problem.constraints,
                    context_summary=bundle.context_summary,
                    knowledge_summary=_summarize(bundle.knowledge),
                    n=n
                )
            }]
        )

        raw = json.loads(response.content[0].text)
        return [Idea(id=uuid4(), **item) for item in raw]
```

---

## 2. Cross-domain Linker

**역할:** Divergence Generator가 생성한 아이디어들을 검토하고,  
**서로 다른 도메인 개념 사이의 숨겨진 패턴·유추**를 찾아 새로운 연결을 만듭니다.

### 작동 원리

"게임의 레벨업 시스템" + "집중력 저하 문제" = "집중 시간에 포인트를 부여하는 진행도 시스템"  
이처럼 관계없어 보이는 두 영역을 연결해 새로운 아이디어를 만듭니다.

### 프롬프트 전략

```python
CROSS_DOMAIN_SYSTEM = """
당신은 서로 다른 분야의 패턴을 연결하는 전문가입니다.
주어진 아이디어 목록을 보고, 서로 다른 도메인 간의 유추(analogy)를 찾아
기존에 없는 새로운 아이디어를 {n}개 추가로 만들어내세요.

좋은 크로스도메인 연결의 예시:
- 군사 전략 → 비즈니스 경쟁 전략
- 생태계 다양성 → 포트폴리오 관리
- 게임 디자인 → 교육 동기 부여
- 생물 면역 시스템 → 사이버보안

출력 형식: 위 Divergence와 동일한 JSON 배열
각 아이디어의 source_domains에 연결된 두 도메인을 모두 포함하세요.
"""
```

### 구현 노트

```python
class CrossDomainLinker:
    # Signal Collector의 약한 신호를 크로스도메인 재료로 활용
    def run(self, bundle: InputBundle, existing_ideas: list[Idea]) -> list[Idea]:
        signals_text = "\n".join(
            f"- [{s.signal_type}] {s.content}" for s in bundle.signals
        )
        ideas_summary = "\n".join(
            f"- {idea.content} (출처: {idea.source_domains})"
            for idea in existing_ideas[:5]  # 너무 많으면 컨텍스트 낭비
        )
        # Claude API 호출 ...
```

---

## 3. Constraint Relaxer

**역할:** 제약 조건을 하나씩 **의도적으로 제거하거나 뒤집어서** 새로운 가능성을 탐색합니다.

### 작동 원리

제약 "예산 50만원 이하" → "예산이 무제한이라면?" → 아이디어 생성 → 다시 제약 안으로 수렴  
제약 "앱 개발 불가" → "앱을 만든다면 오히려 어떻게 되나?" → 역발상 아이디어

### 프롬프트 전략

```python
RELAXER_SYSTEM = """
당신은 창의적 제약 해체 전문가입니다.
주어진 제약 조건들을 하나씩 완화하거나 뒤집어서,
그 상태에서 가능한 아이디어를 탐색한 후
원래 제약 안에서 적용 가능한 핵심 인사이트를 추출하세요.

제약을 "해제하는 것"이 목표가 아닙니다.
제약을 해제했을 때 보이는 가능성의 본질을 추출하는 것이 목표입니다.

출력 형식:
[
  {{
    "relaxed_constraint": "완화된 제약",
    "insight": "이 가정을 해제하면 보이는 것",
    "content": "원래 제약 안에서 구현 가능한 아이디어",
    "rationale": "...",
    "source_domains": ["역발상"],
    "connections": ["..."]
  }}
]
"""
```

---

## 4. Novelty Scorer

**역할:** 각 아이디어에 `novelty_score`와 `feasibility_score`를 부여합니다.  
이 두 값으로 `final_score`를 계산합니다.

### 점수 계산 공식

```python
# 기본 공식 (조정 가능)
def calculate_final_score(idea: Idea, weights: dict = None) -> float:
    w = weights or {"novelty": 0.6, "feasibility": 0.4}
    return idea.novelty_score * w["novelty"] + idea.feasibility_score * w["feasibility"]
```

**novelty 가중치를 높게(0.6)** 가져가는 이유:  
이미 알려진 해법은 쉽게 찾을 수 있습니다. 이 엔진의 존재 이유는 **새로운 조합**입니다.

### 프롬프트 전략

```python
SCORER_SYSTEM = """
다음 아이디어를 두 가지 기준으로 평가하세요.

1. novelty_score (0.0~1.0): 얼마나 참신한가?
   - 0.0: 누구나 떠올리는 뻔한 해법
   - 0.5: 알려져 있지만 이 맥락에서는 신선한 적용
   - 1.0: 이 분야에서 전혀 시도된 적 없는 접근

2. feasibility_score (0.0~1.0): 주어진 제약 안에서 실현 가능한가?
   - 0.0: 제약 위반 또는 현실 불가능
   - 0.5: 도전적이지만 가능
   - 1.0: 즉시 실행 가능

각 점수에 대한 근거를 한 문장으로 제시하세요.
출력: JSON
"""
```

---

## 5. Convergence Ranker

**역할:** 점수가 매겨진 모든 아이디어를 정렬하고, 상위 K개를 `top_ideas`로 선별합니다.

### 단순 구현

```python
class ConvergenceRanker:
    def run(self, ideas: list[Idea], top_k: int) -> list[Idea]:
        # 점수 계산
        for idea in ideas:
            idea.final_score = calculate_final_score(idea)

        # 정렬 후 상위 K개
        sorted_ideas = sorted(ideas, key=lambda x: x.final_score, reverse=True)
        return sorted_ideas[:top_k]
```

### 다양성 보정 (선택)

상위 K개가 비슷한 아이디어로 몰리는 걸 방지합니다.

```python
def diverse_top_k(ideas: list[Idea], k: int) -> list[Idea]:
    selected = [ideas[0]]  # 1위는 무조건 포함
    for idea in ideas[1:]:
        if len(selected) >= k:
            break
        # 이미 선택된 아이디어와 source_domains가 다른 것 우선
        is_diverse = not any(
            set(idea.source_domains) & set(s.source_domains)
            for s in selected
        )
        if is_diverse:
            selected.append(idea)

    # 다양성 기준으로 부족하면 점수 순으로 채움
    if len(selected) < k:
        remaining = [i for i in ideas if i not in selected]
        selected.extend(remaining[:k - len(selected)])

    return selected
```

---

## LangGraph 연결

Connection Engine 전체를 LangGraph 그래프로 연결합니다.

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class ConnectionState(TypedDict):
    bundle: InputBundle
    diverged_ideas: list[Idea]
    linked_ideas: list[Idea]
    relaxed_ideas: list[Idea]
    all_ideas: list[Idea]
    scored_ideas: list[Idea]
    idea_set: IdeaSet

def build_connection_graph() -> StateGraph:
    graph = StateGraph(ConnectionState)

    graph.add_node("diverge", diverge_node)
    graph.add_node("cross_link", cross_link_node)
    graph.add_node("relax", relax_node)
    graph.add_node("merge", merge_node)       # 세 결과 합산
    graph.add_node("score", score_node)
    graph.add_node("rank", rank_node)

    graph.set_entry_point("diverge")

    # 발산 3개는 병렬 실행 (LangGraph fan-out)
    graph.add_edge("diverge", "cross_link")
    graph.add_edge("diverge", "relax")
    graph.add_edge("cross_link", "merge")
    graph.add_edge("relax", "merge")
    graph.add_edge("merge", "score")
    graph.add_edge("score", "rank")
    graph.add_edge("rank", END)

    return graph.compile()
```

---

## 파라미터 튜닝 가이드

| 파라미터 | 기본값 | 높이면 | 낮추면 |
|---|---|---|---|
| `divergence_n` | 10 | 더 창의적, 비용↑ | 빠름, 덜 창의적 |
| `top_k` | 3 | 더 많은 옵션 | 집중된 결과 |
| `novelty_weight` | 0.6 | 파격적 아이디어 우선 | 안전한 아이디어 우선 |
| `max_reflection_rounds` | 2 | 더 정교한 결과 | 빠른 결과 |

---

## 확장 포인트

```python
class ConnectionEngine:
    def __init__(
        self,
        extra_generators: list[BaseGenerator] = [],
        # 사용자 정의 발산 전략 추가 가능
        score_weights: dict = None,
        # novelty/feasibility 가중치 조정
        use_diverse_ranking: bool = True,
        # 다양성 보정 활성화 여부
    ): ...
```
