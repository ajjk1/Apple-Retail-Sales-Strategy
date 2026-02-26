# Apple 리테일 대시보드 (web-development)

FastAPI(백엔드) + Next.js(프론트엔드) 기반 대시보드입니다. 모델 서버의 **예측·매출·재고·추천** 로직을 API로 제공하고, 웹에서 수요·매출·안전재고·상점별 추천을 표시합니다.  
**상위 설명서**: 프로젝트 루트의 **`README.md`** 에서 전체 구조·데이터 정책·기술 스택을 더 상세히 다룹니다. 이 파일은 **실행·데이터·대시보드 요약**에 집중합니다.

---

## 이 문서의 구성

| 섹션 | 내용 |
|------|------|
| §1 | 프로젝트 구조 (디렉터리·데이터 흐름) |
| §2 | 실행 방법 (start.ps1 권장, 수동, 접속 주소·env) |
| §3 | 데이터 소스 정책 (로컬 01.data / 배포 02.Database for dashboard, USE_DASHBOARD_SQL) |
| §4 | 워킹 노트 (대시보드별 로직·API·기능) |
| §5~7 | API 참조, 점검·문제 해결, 주요 파일 |
| §8~9 | 안정화 요약, Hugging Face 배포 |

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

**데이터 연동 흐름**

1. **단일 진입점**: `model-server/load_sales_data.py`의 `load_sales_dataframe()` / `get_data_source_info()`가 모든 데이터의 진입점.
2. **소스 결정**: **로컬**이면 `01.data/*.sql` 우선 → 없으면 `02.Database for dashboard/*.sql` → CSV. **배포**(`USE_DASHBOARD_SQL=1`)면 `02.Database for dashboard/*.sql` 우선. (상세는 §3 및 루트 `README.md` §3 참고.)
3. **공통 DataFrame** → 예측(03)·매출(04)·안전재고(05)·추천(06) 모듈이 동일 소스 사용 → `main.py`가 `/api/*` 제공 → 프론트엔드가 호출해 대시보드 표시.

현재 사용 중인 소스: `GET /api/data-source` 에서 `source`, `data_dir`, `sql_file_count` 확인.

---

## 2. 실행 방법

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

**Vercel·HF Space 연동** (프로덕션에서 데이터 보기):
- **대시보드**: https://apple-retail-sales-strategy-k1kp94g4f-ajjk1.vercel.app  
- **백엔드 API**: https://apple-retail-study-apple-retail-sales-strategy.hf.space  
Vercel 프로젝트 환경 변수에 `BACKEND_URL`, `NEXT_PUBLIC_API_URL` = 위 HF Space URL 로 설정 후 재배포하면 대시보드에 데이터가 표시됩니다. HF Space 루트 접속 시 브라우저에서는 "Vercel 대시보드 열기" 링크가 보입니다.

---

## 3. 데이터 소스 정책 및 준비

- **정책 요약**  
  - **로컬**: `model-server/01.data/` SQL 우선 → 없으면 `02.Database for dashboard/*.sql` → CSV.  
  - **배포**: **`02.Database for dashboard`** 만 사용하는 것이 권장됨. 환경 변수 **`USE_DASHBOARD_SQL=1`** 설정 시 해당 폴더 SQL을 우선 로드(Dockerfile에 이미 설정됨).  
  → 배포 시 01.data 대용량 SQL 없이 경량 SQL만 올리면 되므로 문제 없이 동작.
- **실제 준비**  
  - 로컬: `01.data/` 에 `Apple_Retail_Sales_Dataset_Modified_01.sql` ~ `_10.sql` 등 두면 자동 사용.  
  - 배포: `02.Database for dashboard/*.sql` 만 포함하고 `USE_DASHBOARD_SQL=1` 유지.

데이터는 `load_sales_data.py` 에서 **한 번만** 읽히며, 모든 대시보드 API가 **동일 DataFrame**을 참조합니다.

---

## 4. 워킹 노트 (대시보드별 요약)

대시보드는 **수요 → 매출 → 안전재고 → 추천** 순으로 정리했습니다. 상세는 루트 **`README.md` §5** 참고.

### 수요 대시보드

- **경로**: 메인(3000) → 지도에서 지역 선택 시 수요 박스 / 수요 대시보드 오버레이
- **로직**: `model-server/03.prediction model/prediction model.py`
- **UI**: `frontend/app/page.tsx` | **API**: `GET /api/demand-dashboard`, `/api/sales-quantity-forecast`, `/api/predicted-demand-by-product` 등

### 매출 대시보드 (Sales)

- **경로**: `/sales` | **로직**: `model-server/04.Sales analysis/Sales analysis.py`
- **UI**: `frontend/app/sales/page.tsx` | **API**: `GET /api/sales-summary`, `/api/sales-by-store-quarterly` 등

### 안전재고 대시보드 (Inventory Optimization)

- **경로**: 메인(3000) → 안전재고 오버레이 | **로직**: `model-server/05.Inventory Optimization/Inventory Optimization.py`
- **UI**: `frontend/app/page.tsx` | **API**: `GET /api/safety-stock`, `/api/safety-stock-forecast-chart`, `/api/safety-stock-inventory-list` 등

### 상점별 맞춤형 성장 전략 대시보드 (추천)

- **경로**: `/recommendation` | **로직**: `model-server/06.Real-time execution and performance dashboard/`
- **UI**: `frontend/app/recommendation/page.tsx` | **API**: `GET /api/store-list`, `/api/store-recommendations/{store_id}` 등

### 데이터·공통

- **데이터 소스**: `load_sales_data.py` → SQL(01.data) 또는 CSV. 컬럼 통일: `Store_Name`, `Product_Name`, `store_id` 등.
- **한글 인식**: `main.py` `_resolve_country_to_en`, `_resolve_continent_to_en` / 프론트 `lib/country.ts` 연동.

---

## 5. 대시보드 API (모델 서버 연동)

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

**확인 순서**: (1) `http://127.0.0.1:8000/api/health` 로 백엔드 기동 여부 확인 → (2) `cd web-development/backend` 후 `python main.py --integration-check` 로 로더·4개 모듈 연동 확인 → (3) `GET /api/quick-status` 또는 `/api/integration-status` 로 `modules_loaded` 확인. 상세한 증상별 해결은 루트 **`README.md` §7** 참고.

### 재점검 체크리스트

| 항목 | 기대값 | 확인 방법 |
|------|--------|-----------|
| 데이터 소스 | SQL 10개 또는 CSV | `GET /api/data-source` → `source`, `sql_file_count` |
| 로더 | 501K+ 행 | 백엔드 `load_sales_dataframe()` 반환 행 수 |
| 모듈 로딩 | 4개 스크립트 | `GET /api/quick-status` 또는 `/api/integration-status` → `modules_loaded` |

재점검 예 (백엔드 디렉터리):

```powershell
cd web-development\backend
python -c "import main; print(main.get_data_source_info()); print('rows', len(main.load_sales_dataframe() or []))"
```

또는 `python main.py --integration-check` 로 로더·데이터·모듈 상태 확인.

**연동 진단 (main.py 통합)**  
진단 로직은 `backend/main.py`에만 있습니다. 서버 기동 시 자동으로 `_run_integration_report()`가 실행되어 터미널에 진단 로그가 출력됩니다. 서버 없이 진단만 실행하려면 `cd web-development/backend` 후 `python main.py --integration-check`를 실행하세요.

| 항목 | 기대 상태 | 비고 |
|------|-----------|------|
| MODEL_SERVER | 존재 | `model-server/` |
| load_sales_data.py | OK | load_sales_dataframe, get_data_source_info |
| 데이터 소스 | sql | SQL 10개 파일 (01~10) |
| 로드 행 수 | 501,548행 | 정상 |
| prediction model | OK | get_demand_dashboard_data |
| Sales / Inventory / Real-time | 존재 | 04·05·06 폴더 내 해당 .py |

**API 연동 상태** (`GET /api/integration-status`): load_sales_data, prediction_model, sales_analysis, inventory_optimization, realtime_dashboard 로드 여부 및 스모크 값(forecast_total_quantity, sales_store_count 등) 확인.

**데이터 흐름**: `01.data/*.sql` → `load_sales_dataframe()` → DataFrame → prediction/Sales/Inventory/Real-time 모듈 → main.py API → 프론트엔드.

### 대시보드에 데이터가 안 나올 때

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

---

## 7. 주요 파일 빠른 참조

| 목적 | 파일 |
|------|------|
| 안전재고 로직·ARIMA·분기 집계 | `model-server/05.Inventory Optimization/Inventory Optimization.py` |
| 추천 4종·매출 예측·상위 5개 폴백 | `model-server/06.Real-time execution and performance dashboard/Real-time execution and performance dashboard.py` |
| 안전재고·추천·수요·매출 API | `web-development/backend/main.py` |
| 메인 대시보드·안전재고 오버레이 | `frontend/app/page.tsx` |
| 추천 대시보드 (상점별 성장 전략) | `frontend/app/recommendation/page.tsx` |
| 매출 대시보드 (연도·매장·분기별) | `frontend/app/sales/page.tsx` |
| **실행 스크립트·작업 순서 주석** | **`web-development/start.ps1`** |
| ARIMA 모델 | `model-server/03.prediction model/arima_model.joblib` |

---

## 8. 다음에 이어서 할 수 있는 것

- 안전재고: 분기 라벨·폴백 로직 조정, 새 API 시 `Inventory Optimization.py` 추가 후 `main.py` 라우트 등록
- 추천: 4대 엔진 파라미터 조정, 폴백 상위 N개 변경 시 `_get_top5_product_names`·`_fallback_*` 수정
- 수요 대시보드: `prediction model.py` ↔ `main.py` `/api/demand-dashboard` 연동 확인

이 문서는 작업하면서 필요 시 업데이트하면 됩니다.

---

## 9. 안정화 및 최근 작업 정리

전체적으로 안정화한 내용과 역할 분리·데이터 소스 정리를 한 번에 참고할 수 있도록 정리한 요약입니다. 상세 작업 순서는 **`start.ps1` 상단 [지금까지 작업 순서]** 주석을 참고하세요.

### 9.1 데이터·역할 분리 원칙

| 구분 | 위치 | 역할 |
|------|------|------|
| 데이터 로드 | `model-server/load_sales_data.py` | 로컬: 01.data 우선. 배포: USE_DASHBOARD_SQL=1 시 02.Database for dashboard 우선. 모든 모듈 동일 소스. |
| 예측 | `model-server/03.prediction model/` (arima_model.joblib 등) | 수요·매출 예측. |
| 매출 집계·분기·매장명 매칭 | `model-server/04.Sales analysis/Sales analysis.py` | 매출 대시보드 전용 로직. |
| 안전재고·수요 예측 차트 | `model-server/05.Inventory Optimization/Inventory Optimization.py` | 안전재고 대시보드 전용. |
| 추천·성과·퍼널 | `model-server/06.Real-time execution and performance dashboard/` | 추천 대시보드·피드백 루프. |
| API 라우트·폴백 | `web-development/backend/main.py` | 위 모듈 import 후 라우트만 제공. |

### 9.2 매출 대시보드 안정화

- **API 호출**: `frontend/lib/api.ts` — `apiGet`/`apiPost` 시 **항상 상대경로(`''`) 먼저** 시도 후 `NEXT_PUBLIC_API_URL`, `localhost:8000` 순. CORS 회피·매출/추천 로드 안정화.
- **로딩 타임아웃**: `app/sales/page.tsx` — 로딩 15초 초과 시 강제 해제 → "다시 시도" 표시.
- **3개월 단위 매출 추이**: `Sales analysis.py` — `get_sales_by_store_quarterly`, `get_sales_by_store_quarterly_by_category`에서 매장명 매칭 강화  
  - `_strip_apple_store_prefix()` 추가 (Apple Store / Apple 접두사 제거)  
  - `_extract_store_name_for_match()` 후보에 "Apple SoHo", "Store SoHo" 등 추가  
  - 대소문자 무시 비교로 "소호(SoHo)" 클릭 시 분기별·카테고리별 차트 정상 표시  

### 9.3 추천·안전재고·기타

- **추천 대시보드**: 상점 목록 12초 타임아웃·재시도·에러 시 "다시 불러오기". 샘플/시뮬레이션 구간은 카드 테두리·뱃지·설명으로 구분.
- **데이터 소스 표시**: 대시보드에서 "데이터: SQL · 예측: arima_model.joblib" 등 명시.
- **실행**: `web-development/start.ps1` 실행 → 백엔드(8000) → 프론트(3000). 작업 이력은 **start.ps1 상단 주석**에 순서대로 기록됨.

### 9.4 Hugging Face Space (백엔드 배포)

- **Space**: [apple-retail-study/Apple-Retail-Sales-Strategy](https://huggingface.co/spaces/apple-retail-study/Apple-Retail-Sales-Strategy)
- **배포용 데이터**: **`02.Database for dashboard`** 폴더만 사용하도록 설정하면 배포 시 문제가 없음.  
  - Dockerfile에 **`ENV USE_DASHBOARD_SQL=1`** 설정됨 → 컨테이너 기동 시 `02.Database for dashboard/*.sql` 우선 로드.  
  - `.hfignore`에서 `01.data/*.sql` 제외 후 **`02.Database for dashboard/*.sql`만 포함**해 업로드하면 대용량 없이 배포 가능.
- **Exit 137(OOM) 대응**: 백엔드 기동 시 `load_sales_dataframe()` 호출 제거 → 첫 API 요청 시 지연 로드로 기동 시 메모리 절감.
- **동기화**: GitHub Actions(`.github/workflows/sync_to_hf.yml`)는 현재 `ajjk1/apple-sales-api`로 푸시. 위 Space가 다른 리포라면 해당 Space 리포로 푸시하도록 워크플로의 `huggingface.co/spaces/...` URL을 수정해야 함.

**관련 문서**: 루트 `README.md`(전체 구조·데이터 정책·점검 상세), `backend/HF_SPACE_CHECK.md`(HF 배포 점검), `VERCEL_GITHUB_SETUP.md`(Vercel 루트 디렉터리).
