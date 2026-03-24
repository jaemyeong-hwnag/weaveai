# Architecture

## 설계 철학

### 원칙 1: 레이어는 계약만 안다

각 레이어는 **인접 레이어의 인터페이스(데이터 구조)만** 알고, 내부 구현은 모릅니다.  
Input Engine은 Connection Engine이 LangGraph인지, GPT-4인지 모릅니다.  
교체·업그레이드·테스트가 레이어 단위로 독립적으로 가능합니다.

### 원칙 2: 도메인 로직은 Adapter 밖으로 나오지 않는다

법률 용어, 마케팅 KPI, 코드 컨벤션 — 모두 `DomainAdapter` 두 메서드 안에만 존재합니다.  
엔진 본체에 도메인 조건문(`if domain == "legal"`)이 생기는 순간 설계가 오염됩니다.

### 원칙 3: Connection Engine이 이 프레임워크의 존재 이유

Input·Output 레이어는 LlamaIndex, LangGraph 등으로 채울 수 있습니다.  
**발산 → 크로스도메인 연결 → 수렴** 로직은 기존 오픈소스에 이 형태로 없습니다.  
이 부분이 직접 설계해야 하는 핵심입니다.

---

## 전체 데이터 흐름

```
외부 입력 (raw dict / string)
         │
         ▼
   DomainAdapter.format_problem()
         │
         ▼
   CreativityProblem          ← 표준 입력 포맷
         │
         ▼
┌─────────────────────────────┐
│       Input Engine          │
│  ┌──────────────────────┐   │
│  │  Knowledge Retriever │   │  RAG / 웹검색 / 문서
│  │  Context Builder     │   │  히스토리, 제약 파싱
│  │  Signal Collector    │   │  엣지케이스, 약한 신호
│  └──────────────────────┘   │
└──────────┬──────────────────┘
           │ InputBundle
           ▼
┌─────────────────────────────┐
│     Connection Engine       │
│                             │
│  DIVERGE                    │
│  ├─ Divergence Generator    │  N개 아이디어 병렬 생성
│  ├─ Cross-domain Linker     │  도메인 간 유추·패턴 매핑
│  └─ Constraint Relaxer      │  가정 해체, 역발상         │
│                             │
│  CONVERGE                   │
│  ├─ Convergence Ranker      │  참신성 × 실현가능성 평가
│  └─ Novelty Scorer          │  최종 상위 K개 선별
└──────────┬──────────────────┘
           │ IdeaSet
           ▼
┌─────────────────────────────┐
│       Output Engine         │
│  ┌──────────────────────┐   │
│  │  Solution Formatter  │   │  IdeaSet → Solution 변환
│  │  Executor            │   │  툴 호출, 액션 실행
│  │  Reflector           │   │  자기평가, 재시도 결정
│  └──────────────────────┘   │
└──────────┬──────────────────┘
           │ Solution
           ▼
   DomainAdapter.render_solution()
         │
         ▼
   외부 출력 (도메인별 포맷)
```

---

## 레이어별 책임 경계

### Input Engine

| 컴포넌트 | 책임 | 책임 아닌 것 |
|---|---|---|
| Knowledge Retriever | 관련 문서·데이터 수집 | 내용 해석, 아이디어 생성 |
| Context Builder | goal/constraints 구조화 | 제약 완화, 창의적 판단 |
| Signal Collector | 엣지케이스·트렌드 감지 | 신호의 중요도 평가 |

### Connection Engine

| 컴포넌트 | 책임 | 책임 아닌 것 |
|---|---|---|
| Divergence Generator | 다수 아이디어 생성 (유창성) | 품질 판단 |
| Cross-domain Linker | 도메인 간 패턴 연결 | 도메인 지식 축적 |
| Constraint Relaxer | 가정 해체, 역발상 | 최종 선택 |
| Convergence Ranker | 점수 기반 순위 결정 | 실행 |
| Novelty Scorer | 참신성·실현가능성 수치화 | 순위 결정 |

### Output Engine

| 컴포넌트 | 책임 | 책임 아닌 것 |
|---|---|---|
| Solution Formatter | IdeaSet → Solution 구조화 | 도메인 렌더링 |
| Executor | 외부 툴 호출, 액션 실행 | 결과 평가 |
| Reflector | 자기평가, 재시도 여부 결정 | 새 아이디어 생성 |

### Domain Adapter

| 메서드 | 책임 |
|---|---|
| `format_problem(raw)` | 도메인 입력 → CreativityProblem 변환 |
| `render_solution(solution)` | Solution → 도메인 출력 포맷 변환 |

---

## Claude Code 개발 전략

### 개발 순서 (권장)

```
1단계: 데이터 계약 확정     core/models.py
2단계: GeneralAdapter 구현  adapters/general.py
3단계: Connection Engine    core/connection_engine.py  ← 핵심
4단계: Input/Output Engine  core/input_engine.py, output_engine.py
5단계: CreativityEngine 조립 engine.py
6단계: 도메인 어댑터 추가   adapters/*.py
```

### Claude Code 활용 팁

각 단계를 Claude Code에 아래처럼 지시합니다:

```
"docs/DATA_CONTRACTS.md 의 Pydantic 모델을 기반으로
 src/creativity_engine/core/models.py 를 구현해줘.
 변경 없이 그대로 코드로 옮기면 돼."
```

```
"docs/CONNECTION_ENGINE.md 의 Divergence Generator 섹션을 읽고
 해당 클래스를 LangGraph 노드로 구현해줘."
```

### 테스트 전략

```python
# 각 레이어를 독립적으로 테스트 가능
from creativity_engine.core.connection_engine import ConnectionEngine
from creativity_engine.core.models import InputBundle

bundle = InputBundle(knowledge=[], context={"goal": "test"}, signals=[])
engine = ConnectionEngine()
idea_set = engine.run(bundle)
assert len(idea_set.ideas) > 0
```

---

## 의존성 구조

```
CreativityEngine
├── InputEngine
│   ├── KnowledgeRetriever  (LlamaIndex / 직접 구현)
│   ├── ContextBuilder      (Pydantic 파싱)
│   └── SignalCollector     (웹 검색 도구)
├── ConnectionEngine
│   ├── DivergenceGenerator (Claude API 직접 호출)
│   ├── CrossDomainLinker   (Claude API 직접 호출)
│   ├── ConstraintRelaxer   (Claude API 직접 호출)
│   ├── ConvergenceRanker   (Claude API 직접 호출)
│   └── NoveltyScorer       (Claude API 직접 호출)
├── OutputEngine
│   ├── SolutionFormatter   (Pydantic 변환)
│   ├── Executor            (툴 라이브러리)
│   └── Reflector           (Claude API 직접 호출)
└── DomainAdapter           (사용자 구현)
```

Connection Engine의 모든 컴포넌트는 **Claude API를 직접 호출**합니다.  
LangGraph는 이 컴포넌트들을 노드로 묶는 오케스트레이터 역할입니다.
