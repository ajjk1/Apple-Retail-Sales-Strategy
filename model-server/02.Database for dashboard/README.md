# 배포용 대시보드 데이터 (경량 SQL)

- **용도**: **배포 시** Hugging Face Space, Docker 등에서 사용하는 경량 판매 데이터. 배포용 데이터는 이 폴더를 사용해 문제 없이 동작하도록 설정함.
- **동작**: 환경 변수 **`USE_DASHBOARD_SQL=1`** 설정 시 `load_sales_data.py`가 **이 폴더(`02.Database for dashboard`)의 SQL을 우선** 로드. (Dockerfile에 이미 설정됨.) 로컬에서는 미설정 시 01.data 우선.
- **소스**: `01.data` 전체 데이터에서 2020년 이후 기준으로 대표 샘플을 추출해 단일 SQL로 저장.
- **스키마**: `01.data`와 동일한 `sales_data` 테이블 (sale_id, sale_date, store_id, product_id, quantity, product_name, category_id, launch_date, price, category_name, store_name, city, country, total_sales, store_stock_quantity, inventory, frozen_money, safety_stock, status).
- **생성**: model-server 폴더에서 `python "02.Database for dashboard/build_dashboard_sql.py"` 실행 시 `dashboard_sales_data.sql` 생성 (약 20,000행, ~3.7MB).
