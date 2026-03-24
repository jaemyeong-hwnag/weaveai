# Claude Code 개발 가이드

이 문서는 Claude Code로 이 프로젝트를 구현할 때 사용합니다.  
각 단계를 순서대로 Claude Code에 지시하세요.

---

## 개발 순서 및 Claude Code 프롬프트

### Step 1. 의존성 설치

```bash
pip install anthropic langgraph pydantic python-dotenv \
            llama-index-core llama-index-readers-web \
            tavily-python
```

---

### Step 2. 데이터 모델 구현

**Claude Code 지시:**
```
docs/DATA_CONTRACTS.md 를 읽고
src/creativity_engine/core/models.py 를 구현해줘.

- 모든 클래스는 Pydantic BaseModel 상속
- 파일 상단에 from __future__ import annotations 추가
- 각 필드에 Field(description="...") 로 설명 추가
- 순환 참조 없도록 주의 (Solution이 IdeaSet 참조, IdeaSet이 Idea 참조)
```

---

### Step 3. 범용 어댑터 구현

**Claude Code 지시:**
```
docs/DOMAIN_ADAPTERS.md 의 "범용 어댑터" 섹션을 읽고
src/creativity_engine/adapters/base.py 와
src/creativity_engine/adapters/general.py 를 구현해줘.

base.py: DomainAdapter 추상 클래스
general.py: GeneralAdapter 구현체
```

---

### Step 4. Connection Engine 구현 (핵심)

**Claude Code 지시:**
```
docs/CONNECTION_ENGINE.md 전체를 읽고
src/creativity_engine/core/connection_engine.py 를 구현해줘.

요구사항:
- DivergenceGenerator, CrossDomainLinker, ConstraintRelaxer 각각 별도 클래스
- NoveltyScorer, ConvergenceRanker 구현
- LangGraph StateGraph로 전체 파이프라인 연결
- 각 Claude API 호출은 anthropic 라이브러리 직접 사용 (claude-sonnet-4-6)
- JSON 파싱 실패 시 재시도 로직 포함 (최대 2회)
- 환경변수 ANTHROPIC_API_KEY 사용
```

---

### Step 5. Input Engine 구현

**Claude Code 지시:**
```
docs/ARCHITECTURE.md 의 Input Engine 섹션을 참고해서
src/creativity_engine/core/input_engine.py 를 구현해줘.

- KnowledgeRetriever: LlamaIndex SimpleDirectoryReader 또는 웹 검색 (tavily)
- ContextBuilder: CreativityProblem을 LLM 프롬프트용 요약 텍스트로 변환
- SignalCollector: 제약 조건에서 엣지케이스·역발상 신호 추출
- 모두 실패해도 빈 InputBundle 반환 (에러로 전체 중단 X)
```

---

### Step 6. Output Engine 구현

**Claude Code 지시:**
```
docs/ARCHITECTURE.md 의 Output Engine 섹션과
docs/DATA_CONTRACTS.md 의 Solution 모델을 참고해서
src/creativity_engine/core/output_engine.py 를 구현해줘.

- SolutionFormatter: IdeaSet → Solution 변환
- Reflector: Solution을 Claude로 자기평가, reflection 텍스트 생성
  - confidence 점수 포함
  - max_reflection_rounds 초과하면 중단
- Executor: 지금은 TEXT 타입 Action만 구현 (나머지는 stub)
```

---

### Step 7. CreativityEngine 메인 클래스

**Claude Code 지시:**
```
src/creativity_engine/engine.py 를 구현해줘.

class CreativityEngine:
    def __init__(self, adapter: DomainAdapter = None):
        # adapter 없으면 GeneralAdapter() 사용

    def run(self, raw: dict | str, **kwargs) -> Any:
        # 1. adapter.format_problem(raw)
        # 2. adapter.validate_problem(problem) → 경고 출력
        # 3. InputEngine.run(problem) → InputBundle
        # 4. ConnectionEngine.run(bundle) → IdeaSet
        # 5. OutputEngine.run(idea_set) → Solution
        # 6. adapter.render_solution(solution)
        # 7. 반환

    def run_raw(self, raw: dict | str) -> Solution:
        # render_solution 없이 Solution 객체 그대로 반환
        # 디버깅·테스트용
```

---

### Step 8. 도메인 어댑터 3종 구현

**Claude Code 지시:**
```
docs/DOMAIN_ADAPTERS.md 의 예시 1, 2, 3을 읽고
각각 구현해줘:

- src/creativity_engine/adapters/legal.py     (LegalAdapter)
- src/creativity_engine/adapters/marketing.py (MarketingAdapter)
- src/creativity_engine/adapters/software.py  (SoftwareAdapter)

docs의 코드를 그대로 옮기되, import 경로만 수정해줘.
```

---

### Step 9. 예시 파일 작성

**Claude Code 지시:**
```
examples/ 디렉토리에 3개의 예시 파일을 만들어줘.

각 파일은:
1. 어댑터 선택
2. engine.run() 호출
3. 결과 출력 (pretty print)
4. 실행 가능한 완성 코드

examples/general_example.py     - 원격근무 집중력 문제
examples/legal_example.py       - 계약 분쟁 시나리오
examples/software_example.py    - 마이크로서비스 데이터 일관성 문제
```

---

## 디버깅 명령어

```python
# 중간 결과 확인
solution = engine.run_raw("문제 입력")

print("=== 전체 아이디어 ===")
for idea in solution.idea_set.all_ideas:
    print(f"[{idea.final_score:.2f}] {idea.content[:80]}...")
    print(f"  출처: {idea.source_domains}")

print("\n=== 선택된 아이디어 ===")
print(solution.selected_idea.content)

print("\n=== 자기평가 ===")
print(solution.reflection)
```

---

## 테스트 방법

```bash
# 전체 파이프라인 빠른 테스트 (divergence_n=3으로 줄여서)
python -c "
from creativity_engine import CreativityEngine
engine = CreativityEngine()
result = engine.run_raw({'goal': '테스트 문제', 'divergence_n': 3, 'top_k': 1})
print('OK:', result.selected_idea.content[:100])
"
```

---

## 자주 발생하는 문제

### JSON 파싱 오류
Claude가 JSON 외 텍스트를 포함할 때.  
→ `connection_engine.py`의 각 Generator에 재시도 로직 추가 (Step 4에 명시됨).

### 토큰 초과
`divergence_n`이 클 때 `knowledge_summary`가 길어짐.  
→ `InputEngine`에서 knowledge를 최대 3개, 각 500자로 자름.

### 어댑터 누락
`get_adapter("unknown")` 호출 시.  
→ `ADAPTER_REGISTRY`에 등록 여부 확인. 없으면 `GeneralAdapter` fallback.
