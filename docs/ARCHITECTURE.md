# Architecture

## 설계 철학

### 원칙 1: 레이어는 계약만 안다

각 레이어는 **인접 레이어의 인터페이스(데이터 구조)만** 알고, 내부 구현은 모릅니다.
Input Engine은 Connection Engine이 LangGraph인지 다른 무언가인지 모릅니다.
교체·업그레이드·테스트가 레이어 단위로 독립적으로 가능합니다.

### 원칙 2: 도메인 로직은 Adapter 밖으로 나오지 않는다

법률 용어, 마케팅 KPI, 게임 규칙 — 모두 `DomainAdapter` 두 메서드 안에만 존재합니다.
엔진 본체에 도메인 조건문(`if domain == "legal"`)이 생기는 순간 설계가 오염됩니다.

### 원칙 3: Connection Engine이 이 프레임워크의 존재 이유

Input·Output 레이어는 다른 라이브러리로 채울 수 있습니다.
**발산 → 크로스도메인 연결 → 우연 자극 → 수렴** 로직은 이 프레임워크의 핵심입니다.

### 원칙 4: 모든 의존성은 주입 가능하다

LLM 클라이언트, 프롬프트, 제너레이터 목록, 스코어 가중치 — 모두 `EngineConfig`로 외부에서 주입합니다.
서비스별로 엔진을 수정하지 않고 설정만 교체합니다.

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
│  │  KnowledgeRetriever  │   │  RAG / 문서 직접 주입
│  │  ContextBuilder      │   │  목표·제약 구조화
│  │  SignalCollector      │   │  웹 검색, 약한 신호 감지
│  └──────────────────────┘   │
└──────────┬──────────────────┘
           │ InputBundle
           ▼
┌──────────────────────────────────────────┐
│           Connection Engine              │
│                                          │
│  DIVERGE (병렬)                          │
│  ├─ DivergenceGenerator  → N개 아이디어  │
│  ├─ CrossDomainLinker    → 도메인 연결   │
│  ├─ ConstraintRelaxer    → 역발상        │
│  └─ SerendipityGenerator → 우연 자극     │  serendipity=0이면 스킵
│  └─ [extra_generators]   → 커스텀       │
│                                          │
│  CONVERGE (순차)                         │
│  ├─ NoveltyScorer        → 점수화        │
│  └─ ConvergenceRanker    → 상위 K개 선별 │
└──────────┬───────────────────────────────┘
           │ IdeaSet
           ▼
┌─────────────────────────────┐
│       Output Engine         │
│  ┌──────────────────────┐   │
│  │  SolutionFormatter   │   │  IdeaSet → Solution 변환
│  │  Executor            │   │  액션 실행 (TEXT/SEARCH/CODE/API)
│  │  Reflector           │   │  자기평가, 신뢰도 계산
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
| KnowledgeRetriever | RAG 문서 수집 또는 외부 텍스트 수용 | 내용 해석, 아이디어 생성 |
| ContextBuilder | goal/constraints 구조화 요약 | 제약 완화, 창의적 판단 |
| SignalCollector | 웹 검색으로 엣지케이스·트렌드 감지 | 신호 중요도 평가 |

### Connection Engine

| 컴포넌트 | 책임 | 책임 아닌 것 |
|---|---|---|
| DivergenceGenerator | N개 아이디어 발산 생성 | 품질 판단 |
| CrossDomainLinker | 도메인 간 유추·패턴 연결 | 도메인 지식 축적 |
| ConstraintRelaxer | 제약 해체, 역발상 아이디어 | 최종 선택 |
| SerendipityGenerator | 무관 도메인에서 우연 자극 생성 | serendipity=0이면 즉시 스킵 |
| NoveltyScorer | 참신성·실현가능성 수치화 | 순위 결정 |
| ConvergenceRanker | 점수·다양성 기반 상위 K개 선별 | 실행 |

### Output Engine

| 컴포넌트 | 책임 | 책임 아닌 것 |
|---|---|---|
| SolutionFormatter | 선택된 아이디어 → 솔루션 텍스트 | 도메인 렌더링 |
| Executor | 액션 실행 (TEXT 구현, 나머지 stub) | 결과 평가 |
| Reflector | 자기평가 텍스트 + 신뢰도 계산 | 새 아이디어 생성 |

### Domain Adapter

| 메서드 | 책임 |
|---|---|
| `format_problem(raw)` | 도메인 입력 → CreativityProblem 변환 |
| `render_solution(solution)` | Solution → 도메인 출력 포맷 변환 |
| `validate_problem(problem)` | 도메인 특화 입력 검증 (선택, 경고만 반환) |

---

## EngineConfig — 의존성 주입 허브

모든 서비스별 설정을 한 곳에서 관리합니다.
엔진 코드를 수정하지 않고 설정만 교체해서 다른 서비스에 적용합니다.

```
EngineConfig
├── llm_client          → BaseLLMClient (Claude / OpenAI / 로컬 등)
├── model               → LLM 모델명
├── enabled_generators  → 활성 노드 목록 ["diverge", "cross_link", ...]
├── extra_generators    → 추가 제너레이터 리스트
├── score_weights       → novelty/feasibility 가중치
├── serendipity_domains → 우연 도메인 풀 (서비스별 교체)
├── prompt_overrides    → 컴포넌트별 시스템 프롬프트
├── max_knowledge_docs  → RAG 문서 수 한도
├── max_chars           → 문서 잘림 한도
├── connection_max_tokens
└── output_max_tokens
```

---

## LLM 추상화 레이어

```
BaseLLMClient (ABC)
└── call(system, user, max_tokens) → str

ClaudeClient(BaseLLMClient)    ← 기본 구현체 (anthropic)
OpenAIClient(BaseLLMClient)    ← OpenAI GPT (선택: pip install openai)
GeminiClient(BaseLLMClient)    ← Google Gemini (선택: pip install google-genai)
OllamaClient(BaseLLMClient)    ← Ollama 로컬 LLM (선택: pip install ollama)
CustomClient(BaseLLMClient)    ← 사용자 정의 구현
```

모든 제너레이터와 OutputEngine 컴포넌트는 `BaseLLMClient`를 통해서만 LLM을 호출합니다.
각 공급자 SDK에 직접 의존하는 코드는 해당 클라이언트 파일 하나뿐입니다.
OpenAI/Gemini/Ollama는 선택 의존성으로 패키지가 없어도 임포트 시 에러가 발생하지 않습니다.

---

## 의존성 구조

```
CreativityEngine
├── EngineConfig                  ← 모든 설정 허브
├── InputEngine(config)
│   ├── KnowledgeRetriever
│   ├── ContextBuilder
│   └── SignalCollector (WebSearchTool / Tavily)
├── ConnectionEngine(config)
│   ├── BaseLLMClient             ← config.llm_client 또는 ClaudeClient 자동 생성
│   ├── DivergenceGenerator(client, config)
│   ├── CrossDomainLinker(client, config)
│   ├── ConstraintRelaxer(client, config)
│   ├── SerendipityGenerator(client, config)
│   ├── NoveltyScorer(client, config)
│   ├── ConvergenceRanker(config)
│   ├── [extra_generators]        ← config.extra_generators
│   └── LangGraph(StateGraph)     ← config.enabled_generators 기반 동적 빌드
├── OutputEngine(config)
│   ├── BaseLLMClient             ← 동일 client 공유
│   ├── SolutionFormatter(client, config)
│   ├── Executor
│   └── Reflector(client, config)
└── DomainAdapter                 ← 사용자 구현
```

**중요:** `ConnectionEngine`과 `OutputEngine`이 `EngineConfig`를 통해 동일한 `BaseLLMClient` 인스턴스를 공유합니다. LLM 클라이언트 싱글턴이 보장됩니다.

---

## LangGraph 그래프 구조

```
[diverge] ──→ [cross_link] ──→ [merge]
           ──→ [relax]      ──→ [merge]
           ──→ [serendipity]──→ [merge]
           ──→ [extra]      ──→ [merge]  (extra_generators 있을 때)
                                [merge] → [score] → [rank] → END
```

`EngineConfig.enabled_generators`에 없는 노드는 그래프에서 제거됩니다.
`diverge`는 항상 포함됩니다 (진입점).
