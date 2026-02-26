# Hugging Face Space 구동 점검

## 경로 구조 (Docker 기준)

- **실행 시 CWD**: `/app/web-development/backend`
- **main.py** `__file__`: `/app/web-development/backend/main.py`
  - `_PROJECT_ROOT` = `Path(__file__).resolve().parent.parent.parent` = **`/app`**
  - `_MODEL_SERVER` = **`/app/model-server`**
- **load_sales_data.py** 경로: `/app/model-server/load_sales_data.py`
  - 내부 `_MODEL_SERVER` = `Path(__file__).parent` = **`/app/model-server`**
  - 데이터 탐색: **배포 시** `USE_DASHBOARD_SQL=1`(Dockerfile 설정) → `02.Database for dashboard/*.sql` 우선. 로컬은 01.data 우선 → 02 폴백 → CSV.

## 점검 항목

| 항목 | 기대 | 확인 방법 |
|------|------|-----------|
| load_sales_data.py | `/app/model-server/load_sales_data.py` 존재 | Dockerfile RUN에서 검사 (없으면 빌드 실패) |
| 02.Database for dashboard (배포용) | `dashboard_sales_data.sql` 등 *.sql | **배포 시** `USE_DASHBOARD_SQL=1`로 이 폴더 우선 사용. HF Space는 Dockerfile에 설정됨. |
| 01.data (로컬 우선) | `Apple_Retail_Sales_Dataset_Modified_01.sql` 등 | 로컬에서만 우선. 배포 시 .hfignore로 제외 가능. |
| main.py 로더 연동 | startup 시 "load_sales_dataframe: OK" | Space 로그의 "모델 서버 연동 진단" 블록 확인 |

## Space 로그에서 확인할 메시지

- **정상**: `[Hugging Face Docker 환경] _PROJECT_ROOT=/app`, `load_sales_dataframe: OK`, `데이터 소스: sql`
- **데이터 없음**: `[load_sales_data] 데이터 없음. 시도 경로: ...` → SQL/CSV 경로와 디렉터리 존재 여부 확인

## 수정 사항 (이번 점검 반영)

1. **Dockerfile**: 경로 주석 추가, `load_sales_data.py` 존재 검사 RUN 추가 (없으면 빌드 실패).
2. **main.py**: startup 진단 시 `_PROJECT_ROOT=/app` 이면 `[Hugging Face Docker 환경]` 로그 출력.
3. **load_sales_data.py**: SQL/CSV 모두 없을 때 시도한 경로를 로그로 출력해 원인 파악 가능하도록 함.
