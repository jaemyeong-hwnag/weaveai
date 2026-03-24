# Connection Engine

이 문서가 이 프레임워크의 핵심입니다.
**발산 → 크로스도메인 연결 → 우연 자극 → 수렴** 로직을 정의합니다.

---

## 전체 구조

```
InputBundle
    │
    ▼
DIVERGE 페이즈 (병렬 실행)
    ├── DivergenceGenerator    → 아이디어 N개 생성
    ├── CrossDomainLinker      → 도메인 간 유추 연결
    ├── ConstraintRelaxer      → 가정 해체·역발상
    ├── SerendipityGenerator   → 무관 도메인 우연 자극  (serendipity=0이면 스킵)
    └── [extra_generators]     → 커스텀 제너레이터      (config에 있을 때만)
    │
    ▼ (모든 아이디어 합산 — merge_node)
CONVERGE 페이즈 (순차)
    ├── NoveltyScorer          → 각 아이디어 점수화
    └── ConvergenceRanker      → 상위 K개 선별
    │
    ▼
IdeaSet
```

---

## LangGraph State

```python
class ConnectionState(TypedDict):
    bundle: InputBundle
    diverged_ideas: list[Idea]
    linked_ideas: list[Idea]
    relaxed_ideas: list[Idea]
    serendipity_ideas: list[Idea]
    extra_ideas: list[Idea]
    all_ideas: list[Idea]
    scored_ideas: list[Idea]
    idea_set: IdeaSet
```

---

## 1. Divergence Generator

**역할:** 주어진 문제에 대해 가능한 한 많고 다양한 아이디어를 생성합니다.
품질보다 **수량·다양성**이 목표입니다. 판단하지 않습니다.

### 프롬프트 (ai-token-optimize 적용)

```
ROLE: 창의적 아이디어 생성기
ABBREV: sd=source_domains conn=connections

{n}개 아이디어 생성. 품질판단 금지. 접근법 모두 달라야 함. 상식→파격 스펙트럼. sd 필수.

<out>JSON 배열만
[{"content":"...","rationale":"...","source_domains":["분야"],"connections":["개념"]}]</out>
```

### 입력 컨텍스트

```
goal:{goal}|const:{constraints}
ctx:{context_summary}|know:{knowledge_summary}
→{n}개 JSON
```

`knowledge_summary`는 `InputBundle.knowledge`에서 추출합니다.
`EngineConfig.max_knowledge_docs` (기본 3)개, `max_chars` (기본 500자) 제한.

---

## 2. Cross-domain Linker

**역할:** Divergence Generator가 생성한 아이디어를 보고,
**서로 다른 도메인 간의 숨겨진 유추**를 찾아 새로운 연결 아이디어를 만듭니다.

### 작동 원리

```
"게임의 레벨업 시스템" + "집중력 저하 문제"
  → "집중 시간에 XP를 부여하는 진행도 시스템"

"군사 전략의 포위 전술" + "마케팅 경쟁"
  → "경쟁사 고객을 단계적으로 전환하는 포위 캠페인"
```

### 아이디어 수 결정

```python
n = max(3, bundle.problem.divergence_n // 3)
```

`InputBundle.signals`(약한 신호)를 크로스도메인 재료로 활용합니다.

---

## 3. Constraint Relaxer

**역할:** 제약 조건을 의도적으로 제거하거나 뒤집어서 새로운 가능성을 탐색합니다.
제약이 없을 때 `[]`를 즉시 반환합니다.

### 작동 원리

```
제약 "예산 50만원 이하"
  → "예산이 무제한이라면?" → 아이디어 탐색
  → 인사이트 추출 → 원래 제약 안에서 적용 가능한 아이디어

제약 "앱 개발 불가"
  → "앱을 만든다면 어떤 기능이 핵심인가?"
  → 그 기능을 앱 없이 구현하는 방법
```

---

## 4. Serendipity Generator

**역할:** 문제와 **무관한 랜덤 도메인**을 강제로 문제에 연결해 예상치 못한 아이디어를 생성합니다.

### serendipity 파라미터에 따른 동작

| serendipity | domain_count | idea_count |
|---|---|---|
| 0.0 | 즉시 `[]` 반환 (LLM 호출 없음) | - |
| 0.25 | 1개 도메인 | divergence_n × 0.1 |
| 0.5 | 2개 도메인 | divergence_n × 0.2 |
| 0.75 | 3개 도메인 | divergence_n × 0.3 |
| 1.0 | 4개 도메인 | divergence_n × 0.4 |

```python
domain_count = max(1, round(serendipity * 4))
n = max(1, round(serendipity * bundle.problem.divergence_n * 0.4))
random_domains = random.sample(config.serendipity_domains, domain_count)
```

### 기본 도메인 풀 (24개)

```python
DEFAULT_SERENDIPITY_DOMAINS = [
    "요리", "음악", "고고학", "우주항공", "패션", "원예",
    "마술", "스포츠", "신화", "지질학", "해양생물", "건축",
    "철학", "만화", "의학", "종교", "경제학", "수학",
    "영화", "곤충학", "기후학", "언어학", "무용", "항해",
]
```

`EngineConfig.serendipity_domains`로 서비스별 도메인 풀 교체 가능.

---

## 5. Novelty Scorer

**역할:** 모든 아이디어에 `novelty_score`와 `feasibility_score`를 부여합니다.

### 점수 계산 공식

```python
final_score = novelty_score * w["novelty"] + feasibility_score * w["feasibility"]
# 기본 가중치: novelty=0.6, feasibility=0.4
# EngineConfig.score_weights로 조정 가능
```

novelty 가중치를 높게(0.6) 가져가는 이유:
이미 알려진 해법은 쉽게 찾을 수 있습니다. 이 엔진의 존재 이유는 **새로운 조합**입니다.

### 평가 루브릭 (프롬프트)

```
score | novelty_score 기준          | feasibility_score 기준
0.0   | 뻔한 해법                    | 제약 위반 / 현실 불가능
0.5   | 알려졌지만 이 맥락에서 신선  | 도전적이지만 가능
1.0   | 전혀 새로운 접근             | 즉시 실행 가능
```

---

## 6. Convergence Ranker

**역할:** 점수가 매겨진 아이디어를 정렬하고 상위 K개를 `top_ideas`로 선별합니다.

### 다양성 보정 (기본 활성)

상위 K개가 비슷한 도메인의 아이디어로 몰리는 것을 방지합니다.

```python
def _diverse_top_k(ideas, k):
    selected = [sorted_ideas[0]]  # 1위는 무조건 포함
    for idea in sorted_ideas[1:]:
        if len(selected) >= k:
            break
        # source_domains가 겹치지 않는 아이디어 우선
        is_diverse = not any(
            set(idea.source_domains) & set(s.source_domains)
            for s in selected
        )
        if is_diverse:
            selected.append(idea)
    # 다양성 기준으로 부족하면 점수 순으로 채움
    ...
```

`EngineConfig.use_diverse_ranking=False`로 단순 점수 정렬로 전환 가능.

---

## ConnectionEngine API

```python
class ConnectionEngine:
    def __init__(self, config: EngineConfig | None = None) -> None:
        """
        config=None이면 기본 EngineConfig() 사용.
        config.llm_client=None이면 ClaudeClient 자동 생성.
        그래프는 config.enabled_generators 기반으로 동적 빌드.
        """

    def run(self, bundle: InputBundle) -> IdeaSet:
        ...
```

### 사용 예시

```python
from creativity_engine.config import EngineConfig
from creativity_engine.core.connection_engine import ConnectionEngine

# 기본 사용
engine = ConnectionEngine()

# 설정 주입
config = EngineConfig(
    enabled_generators=["diverge", "cross_link"],
    score_weights={"novelty": 0.3, "feasibility": 0.7},
    extra_generators=[MyDomainGenerator()],
)
engine = ConnectionEngine(config=config)
idea_set = engine.run(bundle)
```

---

## 파라미터 튜닝 가이드

| 파라미터 | 기본값 | 높이면 | 낮추면 |
|---|---|---|---|
| `divergence_n` | 10 | 더 창의적, 비용↑ | 빠름, 덜 다양함 |
| `top_k` | 3 | 더 많은 옵션 | 집중된 결과 |
| `score_weights.novelty` | 0.6 | 파격적 아이디어 우선 | 안전한 아이디어 우선 |
| `serendipity` | 0.0 | 무관 도메인 연결 강해짐 | 0.0 = 비활성 |
| `max_reflection_rounds` | 2 | 더 정교한 솔루션 | 빠른 결과 |
| `max_knowledge_docs` | 3 | RAG 컨텍스트 풍부 | 프롬프트 간결 |

---

## 확장 포인트

### 커스텀 제너레이터 추가

```python
class MyDomainGenerator:
    """DivergenceGenerator와 동일한 인터페이스."""
    def run(self, bundle: InputBundle) -> list[Idea]:
        # 도메인 특화 아이디어 생성 로직
        return [Idea(content="...", source_domains=["my_domain"])]

config = EngineConfig(extra_generators=[MyDomainGenerator()])
engine = ConnectionEngine(config=config)
```

### 프롬프트 전체 교체

```python
config = EngineConfig(
    prompt_overrides={
        "diverge":      "CUSTOM DIVERGE SYSTEM {n}",
        "cross_link":   "CUSTOM CROSS DOMAIN SYSTEM {n}",
        "relax":        "CUSTOM RELAXER SYSTEM",
        "serendipity":  "CUSTOM SERENDIPITY SYSTEM",
        "scorer":       "CUSTOM SCORER SYSTEM",
    }
)
```

### 활성 제너레이터 선택

```python
# 법률 서비스: 파격적 발상보다 논리적 연결만
config = EngineConfig(enabled_generators=["diverge", "cross_link"])

# 브레인스토밍: 우연성 극대화
config = EngineConfig(
    enabled_generators=["diverge", "serendipity"],
    serendipity_domains=["신화", "고고학", "곤충학", "마술"],
)
```
