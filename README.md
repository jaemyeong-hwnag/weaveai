# Creativity Engine

**도메인 무관 창의적 문제해결 AI 에이전트 프레임워크**

어떤 분야의 문제든 동일한 엔진으로 처리합니다.
법률 검토, 마케팅 기획, 코드 설계, 게임 아이디어 — `DomainAdapter` 하나만 추가하면 됩니다.

---

## 핵심 아이디어

> 창의성 = **다양한 Input** × **새로운 Connection** × **반성적 Output**

```
문제 입력
   ↓
[Input Engine]       ← 지식 수집(RAG), 컨텍스트 구성, 약한 신호 감지
   ↓
[Connection Engine]  ← 아이디어 발산 → 크로스도메인 연결 → 수렴·선별
   ↓
[Output Engine]      ← 솔루션 포맷팅, 실행, 자기반성
   ↓
[Domain Adapter]     ← 도메인별 입출력 변환 (플러그인)
```

---

## 설치

```bash
git clone https://github.com/jaemyeong-hwnag/weaveai.git
cd weaveai
pip install -r requirements.txt
```

### 환경변수

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

```env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...   # 웹 검색 사용 시 (선택)
```

---

## 빠른 시작

### 1. 기본 사용

```python
import sys
sys.path.insert(0, "src")  # pip install -e . 후 생략 가능

from creativity_engine import CreativityEngine

engine = CreativityEngine()

result = engine.run(
    goal="원격 근무자의 집중력 저하 문제를 해결하고 싶다",
    constraints=["예산 50만원 이하", "앱 개발 불가"],
    context={"team_size": 5, "industry": "스타트업"},
    divergence_n=5,
    top_k=3,
    max_reflection_rounds=1,
    serendipity=0.3,   # 우연적 연결 강도 (0.0 ~ 1.0)
)

print(result["solution"])
print(result["top_ideas"])
print(result["confidence"])
```

**반환값 (`dict`):**

```python
{
    "solution": "구체적 솔루션 텍스트",
    "top_ideas": [
        {
            "content": "아이디어 내용",
            "score": 0.78,
            "from_domains": ["심리학", "게임디자인"]
        },
        ...
    ],
    "reflection": "강점: ...\n한계: ...",
    "confidence": 0.82
}
```

### 2. Solution 객체 직접 접근 (`run_raw`)

```python
solution = engine.run_raw(
    "팀 커뮤니케이션 과부하 문제",
    divergence_n=5,
    top_k=2,
    max_reflection_rounds=0,
)

# 모든 생성 아이디어
for idea in solution.idea_set.all_ideas:
    print(f"[{idea.final_score:.2f}] {idea.content}")
    print(f"  출처: {idea.source_domains}")

# 최종 선별
print(solution.selected_idea.content)
print(solution.reflection)
print(solution.confidence)
```

### 3. 예제 파일 실행

```bash
python examples/general_example.py
python examples/legal_example.py
python examples/software_example.py
```

---

## EngineConfig — 서비스별 동작 완전 제어

```python
from creativity_engine import CreativityEngine
from creativity_engine.config import EngineConfig

config = EngineConfig(
    # LLM 교체 (Claude 외 다른 공급자 주입 가능)
    llm_client=MyCustomLLMClient(),

    # 활성 제너레이터 선택
    enabled_generators=["diverge", "cross_link"],  # serendipity, relax 제외

    # 스코어 가중치 (novelty + feasibility = 1.0 권장)
    score_weights={"novelty": 0.3, "feasibility": 0.7},  # 실현가능성 중시

    # 우연 도메인 풀 교체
    serendipity_domains=["양자역학", "신화학", "건축"],

    # 프롬프트 오버라이드 (컴포넌트별)
    prompt_overrides={"diverge": "CUSTOM SYSTEM PROMPT {n}"},

    # 커스텀 제너레이터 추가
    extra_generators=[MyDomainSpecificGenerator()],

    # 입력/출력 한도
    max_knowledge_docs=6,
    max_chars=2000,
)

engine = CreativityEngine(adapter=LegalAdapter(), config=config)
```

### EngineConfig 전체 파라미터

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `llm_client` | `None` (ClaudeClient 자동 생성) | `BaseLLMClient` 구현체 주입 |
| `model` | `"claude-sonnet-4-6"` | LLM 모델명 |
| `enabled_generators` | 모두 활성 | 사용할 노드 목록 |
| `extra_generators` | `[]` | 추가 제너레이터 리스트 |
| `score_weights` | `{novelty: 0.6, feasibility: 0.4}` | 최종 점수 가중치 |
| `use_diverse_ranking` | `True` | 도메인 다양성 보정 |
| `serendipity_domains` | 24개 기본 도메인 | 우연 자극 도메인 풀 |
| `connection_max_tokens` | `4096` | 아이디어 생성 최대 토큰 |
| `output_max_tokens` | `512` | 솔루션/반성 최대 토큰 |
| `max_knowledge_docs` | `3` | RAG 문서 최대 수 |
| `max_chars` | `500` | 문서당 최대 글자 수 |
| `prompt_overrides` | `{}` | 컴포넌트별 시스템 프롬프트 교체 |

---

## LLM 공급자 교체

```python
from creativity_engine.llm.base import BaseLLMClient

class MyOpenAIClient(BaseLLMClient):
    def call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        # OpenAI / Gemini / 로컬 LLM 등
        ...

config = EngineConfig(llm_client=MyOpenAIClient())
engine = CreativityEngine(config=config)
```

---

## RAG — 외부 문서를 지식으로 주입

```python
from creativity_engine.config import EngineConfig
from creativity_engine.core.connection_engine import ConnectionEngine
from creativity_engine.core.models import CreativityProblem, InputBundle
from creativity_engine.tools.retriever import KnowledgeRetriever

# 문서를 챕터별로 분할
with open("my_framework.md") as f:
    chapters = [s.strip() for s in f.read().split("---") if s.strip()]

# Document로 변환
retriever = KnowledgeRetriever()
docs = retriever.retrieve_from_texts(chapters, source="framework")

# InputBundle에 직접 주입
problem = CreativityProblem(
    goal="문서 기반 아이디어 생성",
    constraints=["조건1", "조건2"],
    divergence_n=6,
    top_k=3,
)
bundle = InputBundle(
    problem=problem,
    knowledge=docs,
    context_summary="외부 프레임워크 기반 아이디어 생성",
)

# ConnectionEngine만 직접 실행 (InputEngine 우회)
config = EngineConfig(max_knowledge_docs=6, max_chars=2000)
engine = ConnectionEngine(config=config)
idea_set = engine.run(bundle)
```

---

## 새 도메인 어댑터 추가

```python
from creativity_engine.adapters.base import DomainAdapter
from creativity_engine.core.models import CreativityProblem, Solution

class PuzzleAdapter(DomainAdapter):
    def format_problem(self, raw: dict | str) -> CreativityProblem:
        if isinstance(raw, str):
            return CreativityProblem(goal=raw, divergence_n=8, serendipity=0.4)
        return CreativityProblem(
            goal=raw["goal"],
            constraints=raw.get("constraints", []),
            divergence_n=raw.get("divergence_n", 8),
            serendipity=raw.get("serendipity", 0.4),
        )

    def render_solution(self, solution: Solution) -> dict:
        return {
            "game_concept": solution.solution_text,
            "inspired_by": [
                idea.source_domains for idea in solution.idea_set.top_ideas
            ],
            "confidence": solution.confidence,
        }

engine = CreativityEngine(adapter=PuzzleAdapter(), config=config)
result = engine.run({"goal": "새 숫자 퍼즐 게임", "serendipity": 0.5})
```

---

## serendipity — 우연적 연결 강도

문제와 무관한 랜덤 도메인에서 아이디어를 강제 생성하는 파라미터.

| 값 | 동작 |
|---|---|
| `0.0` | 비활성 (기본값). SerendipityGenerator 완전 스킵 |
| `0.3` | 약한 우연 자극. 1~2개 랜덤 도메인에서 아이디어 추가 |
| `0.7` | 강한 자극. 3개 랜덤 도메인, 더 많은 아이디어 |
| `1.0` | 최대. 4개 도메인, divergence_n × 0.4개 아이디어 |

```python
# 런타임 조정 가능
engine.run("목표", serendipity=0.5, divergence_n=10)
```

---

## 프로젝트 구조

```
weaveai/
├── README.md
├── requirements.txt
├── .env.example
│
├── docs/
│   ├── ARCHITECTURE.md      ← 전체 아키텍처 및 설계 철학
│   ├── DATA_CONTRACTS.md    ← 레이어 간 Pydantic 데이터 계약
│   ├── CONNECTION_ENGINE.md ← Connection Engine 내부 로직
│   └── DOMAIN_ADAPTERS.md   ← 어댑터 작성 가이드 + 예시 3종
│
├── src/creativity_engine/
│   ├── __init__.py          ← 공개 API (CreativityEngine, EngineConfig, ...)
│   ├── engine.py            ← CreativityEngine 오케스트레이터
│   ├── config.py            ← EngineConfig dataclass
│   ├── llm/
│   │   ├── base.py          ← BaseLLMClient ABC
│   │   └── claude.py        ← ClaudeClient 구현체
│   ├── core/
│   │   ├── models.py        ← Pydantic 데이터 모델
│   │   ├── input_engine.py
│   │   ├── connection_engine.py
│   │   └── output_engine.py
│   ├── adapters/
│   │   ├── base.py          ← DomainAdapter ABC
│   │   ├── general.py       ← 범용 (기본값)
│   │   ├── legal.py
│   │   ├── marketing.py
│   │   └── software.py
│   └── tools/
│       ├── retriever.py     ← KnowledgeRetriever (RAG)
│       └── web_search.py    ← WebSearchTool (Tavily)
│
├── tests/                   ← pytest, 165개 테스트, 98% 커버리지
└── examples/
    ├── general_example.py
    ├── legal_example.py
    └── software_example.py
```

---

## 다른 프로젝트에 이식

```bash
# 방법 1: 로컬 pip 설치
pip install -e ./weaveai

# 방법 2: src 디렉토리 복사
cp -r weaveai/src/creativity_engine your_project/
```

이식 후 필요한 것: `DomainAdapter` 구현 + `EngineConfig` 설정(선택)

---

## 문서 읽는 순서

1. `docs/ARCHITECTURE.md` — 전체 구조 이해
2. `docs/DATA_CONTRACTS.md` — 데이터 흐름 파악
3. `docs/CONNECTION_ENGINE.md` — 핵심 엔진 로직
4. `docs/DOMAIN_ADAPTERS.md` — 어댑터 작성 및 예시
