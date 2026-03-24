# Creativity Engine

**도메인 무관 창의적 문제해결 AI 에이전트 프레임워크**

어떤 분야의 문제든 동일한 엔진으로 처리합니다.  
법률 검토, 마케팅 기획, 코드 설계, 제품 아이디어 — 도메인 어댑터 하나만 추가하면 됩니다.

---

## 핵심 아이디어

창의성 = **다양한 Input** × **새로운 Connection** × **반성적 Output**

이 프레임워크는 Steve Jobs의 "창의성은 연결이다"를 AI 에이전트 파이프라인으로 구현합니다.

```
문제 입력
   ↓
[Input Engine]      ← 지식 수집, 컨텍스트 구성, 약한 신호 감지
   ↓
[Connection Engine] ← 아이디어 발산 → 크로스도메인 연결 → 수렴·선별
   ↓
[Output Engine]     ← 솔루션 포맷팅, 실행, 자기반성
   ↓
[Domain Adapter]    ← 도메인별 입출력 변환 (플러그인)
```

---

## 빠른 시작

### 1. 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력
```

### 3. 바로 실행

```python
from creativity_engine import CreativityEngine
from creativity_engine.adapters import GeneralAdapter

engine = CreativityEngine(adapter=GeneralAdapter())

result = engine.run(
    goal="원격 근무자의 집중력 저하 문제를 해결하고 싶다",
    constraints=["예산 50만원 이하", "앱 개발 불가"],
    context={"team_size": 5, "industry": "스타트업"}
)

print(result.solution)
print(result.ideas)       # 생성된 모든 아이디어 목록
print(result.reflection)  # 에이전트 자기평가
```

### 4. 새 도메인 적용

```python
from creativity_engine.adapters.base import DomainAdapter

class MyDomainAdapter(DomainAdapter):
    def format_problem(self, raw: dict) -> CreativityProblem:
        # 도메인 입력 → 표준 포맷 변환
        ...

    def render_solution(self, solution: Solution) -> dict:
        # 표준 출력 → 도메인 포맷 변환
        ...

engine = CreativityEngine(adapter=MyDomainAdapter())
```

---

## 프로젝트 구조

```
creativity-engine/
├── README.md                   ← 지금 이 파일
├── requirements.txt
├── .env.example
│
├── docs/
│   ├── ARCHITECTURE.md         ← 전체 아키텍처 상세 설명
│   ├── DATA_CONTRACTS.md       ← 레이어 간 데이터 인터페이스
│   ├── CONNECTION_ENGINE.md    ← Connection Engine 내부 로직
│   └── DOMAIN_ADAPTERS.md      ← 어댑터 작성 가이드 + 예시 3종
│
├── src/
│   └── creativity_engine/
│       ├── __init__.py
│       ├── engine.py           ← CreativityEngine 메인 클래스
│       ├── core/
│       │   ├── models.py       ← 데이터 계약 (Pydantic)
│       │   ├── input_engine.py
│       │   ├── connection_engine.py
│       │   └── output_engine.py
│       ├── adapters/
│       │   ├── base.py         ← DomainAdapter 추상 클래스
│       │   ├── general.py      ← 범용 어댑터 (기본값)
│       │   ├── legal.py        ← 법률 어댑터 예시
│       │   ├── marketing.py    ← 마케팅 어댑터 예시
│       │   └── software.py     ← 소프트웨어 어댑터 예시
│       └── tools/
│           ├── retriever.py    ← RAG 도구
│           └── web_search.py   ← 웹 검색 도구
│
└── examples/
    ├── general_example.py
    ├── legal_example.py
    └── custom_adapter_example.py
```

---

## 다른 프로젝트에 이식하기

이 엔진은 독립 패키지로 설계되어 있습니다.

```bash
# 방법 1: 디렉토리 복사
cp -r creativity-engine/src/creativity_engine your_project/

# 방법 2: pip 로컬 설치
pip install -e ./creativity-engine

# 방법 3: (배포 후) pip install
pip install creativity-engine
```

이식 후 필요한 것은 `DomainAdapter` 구현 하나뿐입니다.

---

## 문서 읽는 순서

1. `docs/ARCHITECTURE.md` — 전체 구조 이해
2. `docs/DATA_CONTRACTS.md` — 데이터 흐름 파악
3. `docs/CONNECTION_ENGINE.md` — 핵심 엔진 로직
4. `docs/DOMAIN_ADAPTERS.md` — 어댑터 작성 및 예시
5. `docs/CLAUDE_CODE_GUIDE.md` — Claude Code 개발 가이드
