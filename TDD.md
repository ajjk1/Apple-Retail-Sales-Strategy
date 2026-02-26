# TDD(테스트 주도 개발) 설명서

이 문서는 **TDD(Test-Driven Development, 테스트 주도 개발)** 개념과 본 프로젝트(ajjk1)에 적용하는 방법을 설명합니다.

---

## 1. TDD란?

**TDD**는 기능을 구현하기 **전에** 먼저 테스트를 작성하고, 그 테스트를 통과하도록 코드를 작성하는 개발 방식입니다.

### 1.1 Red – Green – Refactor 사이클

| 단계 | 설명 |
|------|------|
| **Red** | 실패하는 테스트를 먼저 작성한다. (아직 구현이 없으므로 실패) |
| **Green** | 테스트가 통과할 만큼만 **최소한으로** 구현한다. |
| **Refactor** | 통과한 상태를 유지하면서 코드 품질을 개선한다. (중복 제거, 가독성 등) |

이 사이클을 반복하면서 기능을 점진적으로 추가합니다.

### 1.2 TDD의 장점

- **요구사항 명확화**: 테스트가 “무엇을 만족해야 하는지”를 문서처럼 정의한다.
- **회귀 방지**: 나중에 수정 시 기존 동작이 깨졌는지 바로 확인할 수 있다.
- **설계 유도**: 테스트하기 쉬운 구조(작은 함수, 의존성 주입 등)로 이끈다.
- **리팩터링 용이**: 테스트가 있으면 안전하게 코드를 정리할 수 있다.

---

## 2. 본 프로젝트에서의 적용 범위

| 영역 | 위치 | 권장 도구 | 비고 |
|------|------|-----------|------|
| **백엔드·모델 로직** | `web-development/backend/`, `model-server/` | **pytest** | API·비즈니스 로직·유틸 함수 |
| **프론트엔드** | `web-development/frontend/` | **Jest** + **React Testing Library** | 컴포넌트·훅·유틸 |
| **API 연동 검증** | 백엔드 | **pytest** + **TestClient**(FastAPI) | 엔드포인트 요청/응답 |
| **통합·스모크** | 프로젝트 루트 | `main.py --integration-check` 등 | 모듈 로드·연동 여부 |

현재 프로젝트에는 **엄격한 단위·API 테스트**가 도입되어 있습니다. 백엔드는 **pytest** (커버리지 45% 이상 필수), 프론트는 **Jest** (lib/country 등 커버리지 임계값 적용). 상세는 아래 **8. 엄격 테스트 스위트** 참고.

---

## 3. 백엔드(Python)에서의 TDD 예시

### 3.1 환경 준비

```powershell
# 가상환경 사용 시 (프로젝트 루트)
.\.venv\Scripts\python.exe -m pip install pytest pytest-cov httpx

# 또는 backend 기준
cd web-development\backend
pip install -r requirements.txt
pip install pytest pytest-cov httpx
```

### 3.2 테스트 파일 위치 규칙

- `model-server/` 내 모듈: 각 모듈과 같은 디렉터리 또는 `tests/` 에 `test_*.py`
- FastAPI: `web-development/backend/tests/` 에 `test_*.py`

예:

```
model-server/05.Inventory Optimization/
├── Inventory Optimization.py
└── test_inventory_optimization.py   # 또는 tests/test_inventory_optimization.py

web-development/backend/
├── main.py
└── tests/
    └── test_api_safety_stock.py
```

### 3.3 Red: 실패하는 테스트 먼저 작성

예시 – 안전재고 API가 200과 특정 키를 반환하는지 검증:

```python
# web-development/backend/tests/test_api_safety_stock.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_safety_stock_returns_200_and_has_data():
    response = client.get("/api/safety-stock")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data or "items" in data  # 실제 API 스키마에 맞게 수정
```

처음에는 구현이 없거나 스키마가 다르면 **실패(Red)** 합니다.

### 3.4 Green: 최소 구현으로 통과

`/api/safety-stock` 이 200을 반환하고 필요한 키를 담도록 구현하거나 수정합니다. 테스트가 **통과(Green)** 할 때까지만 수정합니다.

### 3.5 Refactor

통과한 상태를 유지하면서 중복 제거, 함수 분리, 네이밍 정리 등을 합니다. 수정 후 테스트를 다시 실행해 회귀가 없는지 확인합니다.

### 3.6 테스트 실행

```powershell
# 백엔드 디렉터리에서
cd web-development\backend
.\.venv\Scripts\python.exe -m pytest tests/ -v

# 또는 프로젝트 루트에서
.\.venv\Scripts\python.exe -m pytest web-development/backend/tests/ -v

# 커버리지까지 보고 싶을 때
.\.venv\Scripts\python.exe -m pytest web-development/backend/tests/ -v --cov=.
```

---

## 4. 프론트엔드(Next.js)에서의 TDD 예시

### 4.1 환경 준비

```powershell
cd web-development\frontend
npm install -D jest @testing-library/react @testing-library/jest-dom jest-environment-jsdom
```

(Next.js 14 등에서는 `jest.config.js` 또는 `jest.config.mjs` 설정이 필요할 수 있습니다.)

### 4.2 테스트 파일 위치

- `__tests__/` 디렉터리 또는 `*.test.tsx`, `*.spec.tsx` 파일
- 예: `app/__tests__/page.test.tsx`, `components/SafetyStockCard.test.tsx`

### 4.3 Red → Green → Refactor 예시

- **Red**: 예를 들어 “안전재고 카드가 로딩 중일 때 스피너를 보여준다”는 테스트를 먼저 작성하고, 해당 UI가 없으면 실패하게 만든다.
- **Green**: 스피너를 넣어서 테스트가 통과하도록 한다.
- **Refactor**: 스타일이나 구조만 개선하고, 테스트를 다시 실행해 유지한다.

### 4.4 테스트 실행

```powershell
cd web-development\frontend
npm test
# 또는
npm run test:watch
```

(프로젝트에 `test` 스크립트가 없으면 `package.json` 에 `"test": "jest"` 등을 추가합니다.)

---

## 5. TDD 워크플로우 요약

1. **할 일 목록**에서 하나의 작은 기능/조건을 골라 “검증할 내용”을 정한다.
2. **테스트 작성**: 그 조건을 검증하는 테스트 코드를 먼저 쓴다. (Red)
3. **실행**: 테스트를 실행해 실패하는지 확인한다.
4. **구현**: 테스트가 통과할 만큼만 코드를 작성한다. (Green)
5. **리팩터**: 필요하면 코드를 정리하고, 테스트를 다시 실행해 유지한다. (Refactor)
6. 다음 조건으로 1~5를 반복한다.

---

## 6. 본 프로젝트 참고 사항

- **비즈니스·집계 로직**: `model-server/05.Inventory Optimization/Inventory Optimization.py` 등에는 **순수 함수**로 분리 가능한 부분을 우선 테스트하면, TDD 적용이 수월합니다.
- **API**: `web-development/backend/main.py` 의 엔드포인트는 FastAPI `TestClient`로 요청/응답만 검증해도 효과가 큽니다.
- **통합 점검**: 이미 있는 `python web-development/backend/main.py --integration-check` 는 “모듈 로드·연동” 수준의 스모크 테스트로 두고, 세부 동작은 pytest로 보완하는 구성을 권장합니다.

---

## 7. 관련 문서

- **실행·API**: `README.md`, `web-development/README.md`
- **기술 스택**: `README.md` 10장

---

## 8. 엄격 테스트 스위트 (현재 적용)

테스트를 **엄청 빡빡하게** 유지하기 위해 아래 규칙이 적용되어 있습니다.

### 8.1 백엔드 (pytest)

| 항목 | 내용 |
|------|------|
| **위치** | `web-development/backend/tests/` |
| **실행** | `cd web-development/backend` 후 `python -m pytest tests/ -v` (가상환경 권장) |
| **엄격 조건** | `pytest.ini`: `--strict-markers`, `-W default`, **커버리지 45% 미만 시 실패** (`--cov=main --cov-fail-under=45`) |
| **테스트 종류** | `test_api_health.py`, `test_api_data_source.py`, `test_api_safety_stock.py`, `test_api_edge_cases.py`, `test_api_sales_and_recommendation.py`, `test_load_sales_data.py` |
| **검증 수준** | 모든 API: 상태 코드 200, JSON, 필수 키·타입 검증. 엣지: 빈 파라미터, 한글/영문 필터, POST body 검증, limit 파라미터 등 |

### 8.2 프론트엔드 (Jest)

| 항목 | 내용 |
|------|------|
| **위치** | `web-development/frontend/lib/__tests__/country.test.ts` 등 |
| **실행** | `cd web-development/frontend` 후 `npm test` 또는 `npm run test:coverage` |
| **엄격 조건** | `jest.config.mjs`: **커버리지 임계값** (branches 45%, functions/lines/statements 50%) |
| **검증 수준** | `lib/country.ts` 전 export: 정상/빈 문자열/한글·영문 변환/엣지 케이스 전부 단위 테스트 |

### 8.3 새 기능 추가 시

- **백엔드**: 새 엔드포인트 추가 시 해당 라우트에 대한 `test_*.py`에서 상태 코드·스키마·타입을 반드시 추가하고, 커버리지 45% 이상 유지.
- **프론트**: 새 유틸/훅 추가 시 `__tests__/*.test.ts`에 케이스 추가 후 `npm test` 및 `npm run test:coverage` 통과 확인.

이 문서는 TDD 개념과 본 저장소에 적용하는 방법을 설명하는 **설명서**입니다. 실제 테스트 코드를 추가할 때는 위 예시와 디렉터리 규칙을 참고해 점진적으로 도입하면 됩니다.
