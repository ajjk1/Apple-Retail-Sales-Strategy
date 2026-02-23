# Dashboard 전용 데이터 (경량 SQL)

- **용도**: Vercel(프론트) + Hugging Face(백엔드) 배포 시 백엔드에서 사용할 경량 판매 데이터.
- **소스**: `01.data` 전체 데이터에서 2020년 이후 기준으로 대표 샘플을 추출해 단일 SQL로 저장.
- **스키마**: `01.data`와 동일한 `sales_data` 테이블 (sale_id, sale_date, store_id, product_id, quantity, product_name, category_id, launch_date, price, category_name, store_name, city, country, total_sales, store_stock_quantity, inventory, frozen_money, safety_stock, status).
- **생성**: model-server 폴더에서 `python "02.Database for dashboard/build_dashboard_sql.py"` 실행 시 `dashboard_sales_data.sql` 생성 (약 20,000행, ~3.7MB).
- **로더**: `load_sales_data.py`는 이 폴더에 `.sql`이 있으면 01.data 대신 우선 사용 (Hugging Face 배포 시 이 폴더만 포함하면 됨).
