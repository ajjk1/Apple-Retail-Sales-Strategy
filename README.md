---
title: Apple Retail Sales Strategy API
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Apple 리테일 대시보드

FastAPI(백엔드) + Next.js(프론트엔드) 기반 대시보드입니다. 모델 서버의 **예측·매출·재고·추천** 로직을 API로 제공하고, 웹에서 **수요·매출·안전재고·상점별 추천**을 표시합니다.

---

## 이 문서의 구성 (논리 순서)

| 섹션 | 제목 | 내용 |
|------|------|------|
| §1 | 구조 | 디렉터리와 **데이터 흐름**(단일 로드 → 4개 모듈 공유 → API → UI). |
| §2 | 데이터 | **로컬 vs 배포**에서 쓸 SQL 폴더(01.data / 02.Database for dashboard), **어떤 파일을 둘지**. |
| §3 | 실행 | 서버 띄우기(권장: start.ps1), 접속 주소, env. |
| §4 | 대시보드 | 수요·매출·안전재고·추천 **네 가지**의 경로, 로직 위치, API, 기능 요약. |
| §5 | API 참조 | 엔드포인트와 담당 모듈 매핑 표. |
| §6 | 점검·문제 해결 | 확인 순서 → 체크리스트 → 증상별 해결. |
| §7 | 참조 | 주요 파일, 다음 작업, 관련 문서. |
| §8 | 안정화 요약 | 역할 분리, 매출/추천 안정화, 최근 작업. |
| §9 | 기술 스택 | 프론트·백엔드·모델 서버·인프라 명세. |

---

## 1. 프로젝트 구조

```
ajjk1/
├── model-server/                    # 데이터·모델 (Python)
│   ├── 01.data/                    # SQL/CSV 데이터
│   ├── 03.prediction model/        # ARIMA(arima_model.joblib), 수요 예측
│   ├── 04.Sales analysis/          # 매장·분기별 매출 등
│   ├── 05.Inventory Optimization/  # 안전재고 대시보드 로직
│   └── 06.Real-time execution and performance dashboard/  # 추천·매출 예측
├── web-development/
│   ├── backend/                    # FastAPI (main.py) — 포트 8000
│   ├── frontend/                   # Next.js — 포트 3000
│   ├── start.ps1                   # ★ 백엔드+프론트 한 번에 실행 (권장)
│   └── README.md                   # 이 파일
```

**데이터 연동 흐름 (논리적 순서)**

1. **단일 진입점**: 백엔드 기동 시 `model-server/load_sales_data.py`가 로드되며, `load_sales_dataframe()`과 `get_data_source_info()`가 모든 데이터 요청의 진입점이 됩니다.
2. **데이터 소스 결정**: 로더는 **환경에 따라** 아래와 같이 사용할 SQL 폴더를 결정합니다.  
   - **로컬**: `01.data/*.sql` 우선 → 없으면 `02.Database for dashboard/*.sql` → 없으면 CSV.  
   - **배포** (`USE_DASHBOARD_SQL=1` 설정 시): `02.Database for dashboard/*.sql` 우선 → 없으면 01.data.  
   → 자세한 정책과 준비 방법은 **§2 데이터** 참고.
3. **공통 DataFrame**: 위에서 한 번 로드한 DataFrame을 예측(03)·매출(04)·안전재고(05)·추천(06) 모듈이 **동일하게** 사용합니다. 즉, 대시보드 간 데이터 불일치가 나지 않도록 단일 소스가 보장됩니다.
4. **API·UI**: FastAPI(`main.py`)는 위 모듈의 함수만 호출해 `/api/*` 응답을 만들고, 프론트엔드(Next.js)가 해당 API를 호출해 수요·매출·안전재고·추천 화면을 표시합니다.

**확인**: `GET /api/data-source`에서 현재 사용 중인 소스(`source`, `data_dir`, `sql_file_count`)를 확인할 수 있습니다.

---

## 2. 데이터 (소스 정책과 준비)

대시보드용 판매 데이터는 **한 곳(`load_sales_data.py`)에서만** 로드되며, **환경(로컬 vs 배포)에 따라 사용할 SQL 폴더가 달라집니다.** 아래 정책에 맞게 파일만 준비하면 됩니다.

### 2.1 소스 정책 (로컬 vs 배포)

| 환경 | 사용 폴더 | 조건 | 목적 |
|------|-----------|------|------|
| **로컬** | `01.data/` 우선 | 해당 폴더에 `*.sql` 있음 | 개발·테스트용 전체 데이터. 없으면 `02.Database for dashboard/*.sql` → CSV 순. |
| **배포** | `02.Database for dashboard/` 우선 | 환경 변수 `USE_DASHBOARD_SQL=1` 설정 | 경량 SQL만 올려도 되므로 배포 안정. Dockerfile에 이미 설정됨. |

- **배포에서 02만 쓰는 이유**: 01.data는 대용량일 수 있어, HF Space 등에서는 **02 폴더 경량 SQL만** 올리고 `USE_DASHBOARD_SQL=1`로 그쪽만 로드하면 문제 없이 동작합니다.
- **정리**: 로컬 = 01.data 두고 개발, 배포 = 02만 포함하고 `USE_DASHBOARD_SQL=1` 유지.

### 2.2 준비 (어떤 파일을 어디에 둘지)

- **로컬**: `model-server/01.data/` 에 `Apple_Retail_Sales_Dataset_Modified_01.sql` ~ `_10.sql`(또는 동일 스키마 SQL)을 두면 자동 우선 사용. 없으면 02 폴더·CSV 순으로 폴백.
- **배포**: `model-server/02.Database for dashboard/` 에 `dashboard_sales_data.sql` 등 `*.sql`만 포함. 01.data 대용량 SQL은 업로드하지 않아도 됨.

데이터는 **한 번만** 읽히고, 수요·매출·안전재고·추천 **모든 API가 동일한 DataFrame**을 참조합니다.

---

## 3. 실행 방법

### 방법 1: start.ps1 사용 (권장)

```powershell
cd d:\82.CLASS\88.PROJECT\01.assignment\ajjk1\web-development
.\start.ps1
```

- **순서**: 포트 8000/8001 정리 → 백엔드(8000) 기동 → Health 체크 → 프론트(3000) 기동
- API 404 시: 포트 8000 사용 프로세스 정리 후 `start.ps1` 다시 실행

### 방법 2: 수동 실행

**터미널 1 - 백엔드:**
```powershell
cd web-development\backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**터미널 2 - 프론트엔드 (Next.js):**
```powershell
cd web-development\frontend
npm install
npm run dev
```

프론트는 `/api/*` 를 8000으로 넘기므로 **백엔드를 먼저** 켜 두어야 합니다.

**Vue.js 프론트엔드 사용 시 (선택):**
```powershell
cd web-development\frontend-vue
npm install
npm run dev
```

**GitHub–Vercel 연동 오류 시:** 이 저장소는 모노레포이므로 Vercel에서 **Root Directory**를 꼭 설정해야 합니다. → **Settings** → **General** → **Root Directory**: `web-development/frontend`. 자세한 내용은 **`VERCEL_GITHUB_SETUP.md`** 참고.

### 접속 주소

| 용도 | 주소 |
|------|------|
| 대시보드 (Next.js) | http://localhost:3000 |
| 대시보드 (Vue.js) | http://localhost:3001 |
| API 문서 | http://localhost:8000/docs |
| API 상태 | http://localhost:8000/api/health |

**연결 안정화** (필요 시): `frontend/.env.local`  
- `BACKEND_URL=http://127.0.0.1:8000`  
- `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`

---

## 4. 대시보드 (워킹 노트)

대시보드는 **수요 → 매출 → 안전재고 → 추천** 순으로 정리했습니다.

### 수요 대시보드

- **경로**: 대시보드(3000) 메인 → 지도에서 대륙·국가·스토어·도시 선택 시 수요 박스 / 또는 **수요 대시보드 오버레이**
- **로직 위치**: **`model-server/03.prediction model/prediction model.py`** (`get_demand_dashboard_data`, `get_sales_quantity_forecast`, `get_predicted_demand_by_product` 등)
- **UI**: `frontend/app/page.tsx` (메인 페이지 내 수요 박스·수요 대시보드 오버레이)
- **API**: `GET /api/demand-dashboard`, `/api/sales-quantity-forecast`, `/api/predicted-demand-by-product`, `/api/store-markers`, `/api/city-category-pie` 등

| 기능 | 설명 |
|------|------|
| 지역별 총 수요 | 선택한 대륙·국가·스토어·도시의 연도별 판매 수량(총 수요) |
| 카테고리별 수요 | 전체 100% 기준 카테고리별 수요 비중 |
| 상품별 수요·2025 예측 | product_id별 2020~2024 실적 + 2025 예측 (ARIMA·선형 추세 폴백) |
| 2025 수량 예측 | `get_sales_quantity_forecast` 기반 연간 예측 수량 |

### 매출 대시보드 (Sales)

- **경로**: 대시보드(3000) → `/sales`
- **로직 위치**: **`model-server/04.Sales analysis/Sales analysis.py`** (수정은 이 파일만. `main.py`는 라우트·호출만)
- **UI**: `frontend/app/sales/page.tsx`
- **API**: `GET /api/sales-summary`, `/api/store-performance-grade`, `/api/sales-by-store`, `/api/sales-by-store-quarterly`, `/api/sales-by-store-quarterly-by-category`, `/api/sales-by-country-category`, `/api/region-category-pivot` 등
- **데이터**: `load_sales_dataframe()` → SQL(01.data) 또는 CSV. 연도별·분기별·매장별·국가별 매출 집계.

| 기능 | 설명 |
|------|------|
| 전체·연도별 매출 | 2020~2024 + 2025 예상, Top 스토어 |
| 매장 등급·달성률 | [3.4.1] 등급 분포, 연간 목표 대비 |
| 지역별 카테고리 피봇 | [3.4.2] 국가 선택 시 카테고리별 매출 |
| 매장별 매출 | 국가 선택 → 매장 바차트, **매장 클릭 시 3개월 단위 매출 추이** (라인·스캐터, 카테고리별 분기 추이) |

**안정화 요약**: API 호출은 `lib/api.ts`에서 **상대경로(프록시) 우선** 시도. 분기별 그래프는 `Sales analysis.py`에서 매장명 매칭 강화(대소문자·Apple/Apple Store 접두사·후보 확장)로 "소호(SoHo)" 등 클릭 시 데이터 정상 표시.

### 안전재고 대시보드 (Inventory Optimization)

- **경로**: 대시보드(3000) 메인 → **안전재고** 진입 시 오버레이 (Inventory Action Center)
- **로직 위치**: **`model-server/05.Inventory Optimization/Inventory Optimization.py`** 만 수정. `main.py`는 라우트에서 해당 함수만 호출.
- **UI**: `frontend/app/page.tsx` (안전재고 오버레이)
- **API**: `GET /api/safety-stock`, `/api/safety-stock-forecast-chart`, `/api/safety-stock-sales-by-store-period`, `/api/safety-stock-sales-by-product`, `/api/safety-stock-kpi`, `/api/safety-stock-inventory-list`, `/api/inventory-comments` (GET/POST)

| 기능 | 설명 |
|------|------|
| 카테고리별 판매대수 | 파이 차트, 연도 선택 |
| 상점별 3개월 판매 수량 | 연도·분기별 막대, 분기 클릭 시 상품별 차트 반영 |
| 상품별 판매 수량 | 가로 막대, 상품 클릭 시 수요 예측 차트 표시 |
| 수요 예측 & 적정 재고 | 2020년부터 분기별, **ARIMA(arima_model.joblib)** 전용 |
| 과잉·위험 품목 카드 | 과잉 재고 TOP 5(수량 기준), 위험 품목 Top 5(발주량·지출 기준) |

### 상점별 맞춤형 성장 전략 대시보드 (추천)

- **경로**: 대시보드(3000) → `/recommendation`
- **로직 위치**: **`model-server/06.Real-time execution and performance dashboard/Real-time execution and performance dashboard.py`**
- **UI**: `frontend/app/recommendation/page.tsx`
- **API**: `GET /api/store-list`, `/api/store-recommendations/{store_id}`, `/api/store-sales-forecast/{store_id}`, `/api/demand-dashboard?store_id=...&year=2024`, `/api/safety-stock-inventory-list?status_filter=Overstock`, `/api/sales-summary`, `/api/recommendation-summary`

| 기능 | 설명 |
|------|------|
| 상점 선택 | store-list(SQL) 기반 셀렉트 |
| 향후 30일 매출 예측 | 일별 실측 + 선형 회귀 예측 + 신뢰 구간 |
| 안전재고·매출·수요 연동 | 과잉 재고 Top 8, 매출 요약(상점 비중), 수요 대시보드(2025 카테고리/제품 예측) |
| 4대 추천 | 유사 상점, 연관 분석(Basket), 잠재 수요(SVD), 지역 트렌드 |
| 추천 폴백 | 결과 없을 때 **전체 매출 기준 상위 5개 품목** 표시 |

### 데이터·공통

- **데이터 소스**: `load_sales_data.py` → SQL(01.data) 또는 CSV. 컬럼 통일: `Store_Name`, `Product_Name`, `store_id` 등.
- **한글 인식**: `main.py` `_resolve_country_to_en`, `_resolve_continent_to_en` / 프론트 `lib/country.ts` 연동.

---

## 5. API 참조 (모델 서버 연동)

| API | 용도 | 모델 서버 |
|-----|------|-----------|
| `GET /api/data-source` | 데이터 소스(SQL/CSV) 정보 | load_sales_data.py |
| `GET /api/sales-quantity-forecast` | 2020~2024 실적 + 2025 예측 수량 | prediction model.py |
| `GET /api/predicted-demand-by-product` | 제품별 2025 예측 수요 | prediction model.py |
| `GET /api/demand-dashboard` | 수요 대시보드(지역·store_id·연도) | prediction model.py |
| `GET /api/store-markers`, `/api/city-category-pie` 등 | 지도·파이 | prediction model.py |
| `GET /api/sales-summary`, `/api/sales-box`, `/api/sales-by-store-quarterly`, `/api/sales-by-store-quarterly-by-category` | 매출 요약·박스·매장별 분기 | Sales analysis.py |
| `GET /api/safety-stock`, `/api/safety-stock-forecast-chart` 등 | 안전재고·수요 예측 차트 | Inventory Optimization.py |
| `GET /api/store-list`, `/api/store-recommendations/{store_id}` 등 | 추천·매출 예측 | Real-time execution and performance dashboard.py |
| `GET /api/recommendation-summary` | 추천 상품·카테고리 | Real-time execution and performance dashboard.py |

---

## 6. 점검·문제 해결

문제가 있을 때 **순서대로** 확인하면 원인을 빠르게 좁힐 수 있습니다.

### 6.1 확인 순서 (권장)

1. **1단계: 백엔드·데이터 소스**  
   - 브라우저에서 `http://127.0.0.1:8000/api/health` 호출 → JSON이 나오면 백엔드는 기동된 상태입니다.  
   - `GET /api/data-source` → `source`, `sql_file_count`로 **현재 어떤 소스(SQL/CSV)를 쓰는지** 확인. (로컬이면 01.data 또는 02, 배포면 02가 나와야 함.)
2. **2단계: 통합 진단 (한 번에 확인)**  
   - 터미널에서 `cd web-development/backend` 후 **`python main.py --integration-check`** 실행.  
   - 로더·데이터 행 수·4개 모듈(수요·매출·안전재고·추천) 로드 여부가 한 번에 출력됩니다.  
   - 서버를 띄울 때도 동일 진단이 자동 실행되므로, 백엔드 터미널 로그에서 `[Apple Retail API]` 메시지를 확인하면 됩니다.
3. **3단계: API·모듈 상세**  
   - `GET /api/quick-status` 또는 `GET /api/integration-status` → `modules_loaded`에서 prediction_model, sales_analysis, inventory_optimization, realtime_dashboard가 모두 true인지 확인.  
   - `http://127.0.0.1:8000/docs` Swagger UI로 개별 API를 직접 호출해 응답 여부 확인.

### 6.2 체크리스트 (기대값)

| 항목 | 기대값 | 확인 방법 |
|------|--------|-----------|
| 데이터 소스 | sql (또는 csv) | `GET /api/data-source` → `source`, `sql_file_count` |
| 로더 행 수 | 0 초과 (로컬 예: 501K+ 등) | `python main.py --integration-check` 또는 백엔드 로그 |
| 모듈 로딩 | 4개 모두 true | `GET /api/quick-status` 또는 `/api/integration-status` → `modules_loaded` |

**진단만 실행할 때 (서버 없이):**

```powershell
cd web-development\backend
python main.py --integration-check
```

**데이터 소스·행 수만 확인할 때:**

```powershell
cd web-development\backend
python -c "import main; print(main.get_data_source_info()); print('rows', len(main.load_sales_dataframe() or []))"
```

**데이터 흐름 요약**: (로컬) `01.data/*.sql` 또는 `02.Database for dashboard/*.sql` → `load_sales_dataframe()` → 단일 DataFrame → prediction/Sales/Inventory/Real-time 모듈 → main.py `/api/*` → 프론트엔드.

### 6.3 증상별 해결 (대시보드에 데이터가 안 나올 때)

- **"백엔드 확인 중..." 만 보임**  
  백엔드(8000)를 **먼저** 실행하세요. `http://127.0.0.1:8000/api/health` 에서 JSON 확인 후 프론트 재시작.

- **지도/차트만 비어 있음 (apple-data는 됨)**  
  예측 모델(prediction model.py) 미로드. 백엔드 터미널에서 `[Apple Retail API] 예측 모델: 로드됨/미로드` 확인. `model-server/03.prediction model/prediction model.py` 존재·에러 메시지 확인 후 `pip install pandas` 등 의존성 설치·재시작.

- **포트 충돌**  
  8000 사용 중이면 해당 프로세스 정리 후 `start.ps1` 재실행. 또는 백엔드를 `--port 8001` 로 띄우고 `.env.local` 에 `NEXT_PUBLIC_API_URL=http://127.0.0.1:8001` 설정.

- **모델 서버 미연동**  
  1. `cd web-development\backend` → `python main.py --integration-check` 실행  
  2. 백엔드 터미널 로그 확인 (`[Apple Retail API]` 메시지)  
  3. `http://127.0.0.1:8000/api/integration-status` 또는 `/api/quick-status` 에서 `modules_loaded` 확인  
  4. `http://127.0.0.1:8000/docs` Swagger UI로 API 직접 테스트  
  5. `model-server` 내 `load_sales_data.py`, `04.Sales analysis/` 등 경로 확인  

- **예측이 linear_trend만 나옴**  
  ARIMA 모델(`model-server/03.prediction model/arima_model.joblib`) 존재 여부 확인. 필요 시 `pip install statsmodels` 후 백엔드 재시작.

- **배포(HF Space)에서 데이터 없음**  
  배포용은 **02.Database for dashboard**만 사용하는지 확인. Dockerfile에 `ENV USE_DASHBOARD_SQL=1`이 있고, 해당 폴더에 `*.sql`이 포함되어 있는지 확인. `HF_SPACE_CHECK.md` 참고.

---

## 7. 참조 (주요 파일·다음 작업·관련 문서)

**주요 파일**

| 목적 | 파일 |
|------|------|
| 수요 예측·ARIMA | `model-server/03.prediction model/prediction model.py`, `arima_model.joblib` |
| 매출 집계·분기 | `model-server/04.Sales analysis/Sales analysis.py` |
| 안전재고·재고 파이프라인 | `model-server/05.Inventory Optimization/Inventory Optimization.py` |
| 추천·성장 전략 | `model-server/06.Real-time execution and performance dashboard/Real-time execution and performance dashboard.py` |
| API 라우트 | `web-development/backend/main.py` |
| 메인·수요·안전재고 UI | `frontend/app/page.tsx` |
| 매출·추천 UI | `frontend/app/sales/page.tsx`, `frontend/app/recommendation/page.tsx` |
| 실행·작업 순서 | `web-development/start.ps1` |

**다음에 이어서 할 수 있는 것**  
안전재고: 분기·폴백 조정, 새 API 시 `Inventory Optimization.py` 추가 후 `main.py` 라우트 등록. 추천: 4대 엔진·폴백 N개 조정. 수요: `prediction model.py` ↔ `/api/demand-dashboard` 연동 확인. **테스트**: `TDD.md` 참고(pytest·Jest 엄격 스위트).

**관련 문서**  
`web-development/README.md`(실행·대시보드 요약), `TDD.md`(테스트), `VERCEL_GITHUB_SETUP.md`(Vercel), `web-development/backend/HF_SPACE_CHECK.md`(HF 배포 점검).

---

## 8. 안정화 요약

전체적으로 안정화한 내용과 역할 분리·데이터 소스 정리를 한 번에 참고할 수 있도록 정리한 요약입니다. 상세 작업 순서는 **`start.ps1` 상단 [지금까지 작업 순서]** 주석을 참고하세요.

### 8.1 데이터·역할 분리 원칙

| 구분 | 위치 | 역할 |
|------|------|------|
| 데이터 로드 | `model-server/load_sales_data.py` | 로컬: 01.data 우선. 배포: USE_DASHBOARD_SQL=1 시 02.Database for dashboard 우선. 모든 모듈 동일 소스. |
| 예측 | `model-server/03.prediction model/` (arima_model.joblib 등) | 수요·매출 예측. |
| 매출 집계·분기·매장명 매칭 | `model-server/04.Sales analysis/Sales analysis.py` | 매출 대시보드 전용 로직. |
| 안전재고·수요 예측 차트 | `model-server/05.Inventory Optimization/Inventory Optimization.py` | 안전재고 대시보드 전용. |
| 추천·성과·퍼널 | `model-server/06.Real-time execution and performance dashboard/` | 추천 대시보드·피드백 루프. |
| API 라우트·폴백 | `web-development/backend/main.py` | 위 모듈 import 후 라우트만 제공. |

### 8.2 매출 대시보드 안정화

- **API 호출**: `frontend/lib/api.ts` — `apiGet`/`apiPost` 시 **항상 상대경로(`''`) 먼저** 시도 후 `NEXT_PUBLIC_API_URL`, `localhost:8000` 순. CORS 회피·매출/추천 로드 안정화.
- **로딩 타임아웃**: `app/sales/page.tsx` — 로딩 15초 초과 시 강제 해제 → "다시 시도" 표시.
- **3개월 단위 매출 추이**: `Sales analysis.py` — `get_sales_by_store_quarterly`, `get_sales_by_store_quarterly_by_category`에서 매장명 매칭 강화  
  - `_strip_apple_store_prefix()` 추가 (Apple Store / Apple 접두사 제거)  
  - `_extract_store_name_for_match()` 후보에 "Apple SoHo", "Store SoHo" 등 추가  
  - 대소문자 무시 비교로 "소호(SoHo)" 클릭 시 분기별·카테고리별 차트 정상 표시  

### 8.3 추천·안전재고·기타

- **추천 대시보드**: 상점 목록 12초 타임아웃·재시도·에러 시 "다시 불러오기". 샘플/시뮬레이션 구간은 카드 테두리·뱃지·설명으로 구분.
- **데이터 소스 표시**: 대시보드에서 "데이터: SQL · 예측: arima_model.joblib" 등 명시.
- **실행**: `web-development/start.ps1` 실행 → 백엔드(8000) → 프론트(3000). 작업 이력은 **start.ps1 상단 주석**에 순서대로 기록됨.

### 8.4 최근 작업 정리 (수요·안전재고 대시보드, 배포 점검)

- **가상환경 및 통합 점검**
  - 프로젝트 루트에 `.venv` 가상환경 생성 후, `web-development/backend/requirements.txt` 기준으로 백엔드 의존성을 설치했습니다.
  - `.\.venv\Scripts\python.exe web-development\backend\main.py --integration-check` 를 실행해 모델 서버 4개 모듈(수요·매출·안전재고·추천)과 데이터 로더 연동이 모두 정상임을 재확인했습니다.
  - `.gitignore`에 `.venv/` 가 이미 포함되어 있어, 가상환경 자체는 Git 커밋·배포 대상에 포함되지 않습니다.

- **수요 대시보드(예측 모델) 리팩토링·테스트 진입점**
  - `model-server/03.prediction model/prediction model.py` 하단에 스모크 테스트 엔트리포인트를 추가했습니다.
  - 사용법: `cd ajjk1` 후 `.\.venv\Scripts\python.exe "model-server\03.prediction model\prediction model.py"` 실행 시,  
    ① 2020~2024년 총 판매 수량, ② 2025년 예측 수량(ARIMA 또는 선형 추세), ③ `get_demand_dashboard_data()` 기준 `total_demand`를 콘솔에 출력합니다.
  - FastAPI 서버에서는 이 모듈을 **import만** 하므로, `if __name__ == "__main__":` 블록은 서버·HF Space 실행 시에는 동작하지 않고, 로컬 점검용으로만 사용됩니다.

- **안전재고 대시보드 UI 단순화 (Inventory Action Center)**
  - `web-development/frontend/app/page.tsx` 내 **안전재고 오버레이**에서 상단 KPI 카드 4개를 제거했습니다.  
    (총 잠긴 돈 / 예상 매출 / 과잉 품목 수 / 위험 품목 수)
  - 동일 오버레이 하단의 **매장별 재고 막대 그래프 카드**도 제거하고, 관리자 코멘트 카드만 전체 폭(`lg:col-span-3`)으로 유지해 레이아웃을 간결하게 정리했습니다.
  - `위험 품목 Top 5` 카드를 **과잉 재고 현황 카드와 유사한 라이트 테마**(흰색 배경·연한 회색 테두리, 상단 설명 + 뱃지 구조)로 재디자인하여, 동일 섹션 내 카드 스타일을 통일했습니다.

- **배포 영향 및 빌드 검증 (Vercel / Hugging Face)**
  - 프론트엔드: `web-development/frontend` 에서 `npm run build`(Next.js 14 프로덕션 빌드)를 실행해 타입·린트·정적 페이지 생성까지 모두 통과했습니다.  
    → Vercel에서 사용하는 빌드 파이프라인과 동일 수준으로 검증 완료.
  - 백엔드/HF Space: 오늘 변경된 코드는 prediction 모듈의 `__main__` 블록과 프론트 UI(`page.tsx`) 뿐이라,  
    기존 Hugging Face Space 워크플로(`.github/workflows/sync_to_hf.yml`)와 FastAPI 라우트 구조에는 영향이 없습니다.
  - 커밋 이력:
    - `chore: add prediction model smoke test entrypoint`
    - `style: simplify safety stock dashboard cards`

---

## 9. 기술 스택 및 구성 요소 명세

### 9.1 프론트엔드 (대시보드 UI)

- **프레임워크**
  - **Next.js 14 (`next@14.2.24`)**: App Router 기반, `app/` 디렉터리 구조.
  - **React 18 (`react@18.3.1`)**: 함수형 컴포넌트 + 훅 기반 상태 관리.
  - **TypeScript 5 (`typescript@^5`)**: 타입 안전성 확보 및 IDE 지원.
- **스타일링·레이아웃**
  - **Tailwind CSS 3 (`tailwindcss@3.4.1`)**: 유틸리티 클래스 기반 스타일링, 반응형 레이아웃 구현.
  - 기본 폰트·색은 Apple 스타일에 맞춰 커스텀(`text-[#1d1d1f]`, `#f5f5f7` 등).
- **차트·시각화**
  - **Recharts (`recharts@^3.7.0`)**: 막대/파이/콤포지트 차트, 안전재고·매출·수요 대시보드의 대부분 그래프에 사용.
  - **three / react-globe.gl**: 3D 지구본 기반 매장·지역 데이터 시각화에 사용.
- **품질 관리**
  - **ESLint 8 + `eslint-config-next`**: Next.js 권장 규칙 기반 린트, `npm run lint`.
  - **Type Checking**: `next build` 과정에서 TypeScript 타입 체크 자동 수행.
- **주요 명령**
  - 개발 서버: `cd web-development/frontend && npm install && npm run dev`
  - 프로덕션 빌드: `cd web-development/frontend && npm run build`

### 9.2 백엔드 API (FastAPI)

- **런타임 / 서버**
  - **Python (프로젝트 기준 3.13 호환)**: 가상환경 `.venv` 에서 동작.
  - **FastAPI (`fastapi>=0.109.0`)**: REST API 서버, `/api/*` 엔드포인트 정의 (`web-development/backend/main.py`).
  - **Uvicorn (`uvicorn[standard]>=0.27.0`)**: ASGI 서버, 로컬 실행 시 `uvicorn main:app --reload`.
- **의존성 / 데이터 처리**
  - **pandas (`pandas>=2.0.0`)**: SQL/CSV → DataFrame 로딩, 집계·피벗·시계열 처리 전반.
  - **joblib (`joblib>=1.3.0`)**: ARIMA 모델(`arima_model.joblib`) 로딩, 모델 캐싱.
  - **numpy**: 모델 서버 모듈(예측·재고·추천) 내부에서 수치 연산에 사용.
  - **scikit-learn**: 추천/시계열 모듈에서 `cosine_similarity`, `TruncatedSVD`, `LinearRegression` 등 사용.
- **구조**
  - `web-development/backend/main.py`  
    - `/api/sales-summary`, `/api/safety-stock`, `/api/store-recommendations/{store_id}` 등 API 라우트 정의.
    - 각 라우트는 `model-server/` 하위 모듈(수요·매출·안전재고·추천)을 import 해서 호출만 담당.
  - 공통 데이터 로더: `model-server/load_sales_data.py`  
    - **로컬**: `01.data/*.sql` 우선 → 없으면 `02.Database for dashboard/*.sql` 폴백.  
    - **배포**: `USE_DASHBOARD_SQL=1` 설정 시 **`02.Database for dashboard/*.sql` 우선** 사용(배포 시 문제 방지). 파싱해 `sales_data` 테이블을 DataFrame 으로 로드.
    - 모든 분석/대시보드 모듈이 **동일한 DataFrame**을 사용하도록 통일.

### 9.3 모델 서버 / 분석 모듈

- **수요 예측·수요 대시보드**
  - 모듈: `model-server/03.prediction model/prediction model.py`
  - 기능:
    - `get_sales_quantity_forecast()` — 2020~2024 실적 + 2025년 수량 예측 (ARIMA → 실패 시 선형 추세 폴백).
    - `get_demand_dashboard_data()` — 대륙/국가/스토어/도시·연도별 수요 대시보드 통합 데이터.
    - `get_predicted_demand_by_product`, `get_predicted_demand_by_category` — 2025년 예상 수요 테이블용 데이터.
  - 모델:
    - `arima_model.joblib` (statsmodels ARIMA 결과 객체) 를 `joblib.load()` 로 로딩.
    - 모델 파일이 없거나 실패 시, 선형 회귀 기반 폴백 로직 사용.

- **매출 분석·매출 대시보드**
  - 모듈: `model-server/04.Sales analysis/Sales analysis.py`
  - 기능:
    - `get_store_sales_summary()`, `get_sales_box_value()` — 메인·매출 대시보드 요약.
    - `get_sales_by_store`, `get_sales_by_store_by_year`, `get_sales_by_store_quarterly*` — 매장·분기·카테고리별 매출 차트용 데이터.
    - `get_store_performance_grade()` — 매장 등급/달성률 분석(예측 매출과 목표 대비).

- **안전재고 최적화·Inventory Action Center**
  - 모듈: `model-server/05.Inventory Optimization/Inventory Optimization.py`
  - 기능:
    - `run_inventory_pipeline()` — 안전재고(Safety_Stock), Inventory, Status(Danger/Normal/Overstock), Frozen_Money 계산.
    - `get_safety_stock_summary()`, `get_kpi_summary()`, `get_inventory_list()` — 안전재고 대시보드 상단 요약·리스트.
    - `get_overstock_status_by_region()`, `get_overstock_top5_by_quantity()`, `get_risky_items_top5()` — 과잉 재고·위험 품목 분석 카드용 데이터.
    - `get_demand_forecast_chart_data()` — ARIMA 기반 6분기 수요·재고 예측 차트 데이터.

- **추천 시스템·성장 전략 대시보드**
  - 모듈: `model-server/06.Real-time execution and performance dashboard/Real-time execution and performance dashboard.py`
  - 기능:
    - `get_recommendation_summary()`, `get_store_list()` — 추천 대시보드 메인 요약·상점 목록.
    - 4대 추천 엔진: `association_recommendations`, `similar_store_recommendations`, `latent_demand_recommendations`, `trend_recommendations`.
    - `get_store_recommendations()` — 상점별 추천 결과 통합.
    - `StoreGrowthStrategyEngine` / `get_store_growth_strategy_recommendations()` — 상점별 성장 전략 엔진 (브랜드/이익/재고 회전 가중치 기반).
    - 퍼널·성과 시뮬레이터: `get_customer_journey_funnel()`, `get_funnel_stage_weight()`, `get_performance_simulator()`.

### 9.4 인프라 / 배포 파이프라인

- **프론트엔드 (Vercel)**
  - 설정 파일: `web-development/frontend/vercel.json`
  - 빌드:
    - `"framework": "nextjs"`
    - `"buildCommand": "npm run build"`, `"installCommand": "npm install"`
  - API 연동:
    - rewrites: `/api/*`, `/docs/*`, `/openapi.json` → Hugging Face Space 백엔드로 프록시.

- **백엔드 (Hugging Face Space)**
  - Sync 워크플로: `.github/workflows/sync_to_hf.yml`
    - `main` 브랜치 푸시 시, Hugging Face Space `apple-retail-study/Apple-Retail-Sales-Strategy` 로 Git force-push.
    - 대용량/불필요 폴더(`model-server/00.old` 등)는 푸시 전 제거.
  - 실행 환경:
    - Space 내 `web-development/backend/main.py` 를 FastAPI 앱 엔트리포인트로 사용.
    - 모델 서버(`model-server/`)와 동일 디렉터리 구조를 유지해야 함.

- **환경 변수 / 기타**
  - 로컬 개발:
    - `web-development/frontend/.env.local` 에
      - `BACKEND_URL=http://127.0.0.1:8000`
      - `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`
  - 프로덕션(Vercel):
    - `BACKEND_URL`, `NEXT_PUBLIC_API_URL` 을 Hugging Face Space URL로 설정.
  - Git:
    - 기본 브랜치: `main`
    - Hugging Face 토큰: GitHub Secrets `HF_TOKEN` 에 저장, 워크플로에서만 사용.
