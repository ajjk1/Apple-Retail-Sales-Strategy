"""
data_02_inventory_final.csv → PostgreSQL SQL 파일로 변환 후 01.data 폴더에 저장.
- 출력: Apple_Retail_Sales_Dataset_Modified_01.sql ~ _10.sql (10개 분할)
- 테이블: sales_data (14컬럼, 기존 스키마와 동일)
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent
CSV_FILE = DATA_DIR / "data_02_inventory_final.csv"
NUM_FILES = 10
OUTPUT_PREFIX = "Apple_Retail_Sales_Dataset_Modified"


def escape_sql(value: str) -> str:
    """PostgreSQL용 작은따옴표 이스케이프."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "NULL"
    s = str(value).strip().replace("'", "''")
    return "'" + s + "'"


def num_sql(value: str) -> str:
    """숫자 컬럼용: 유효하면 그대로, 아니면 0."""
    if value is None:
        return "0"
    s = str(value).strip()
    if not s:
        return "0"
    try:
        float(s)
        return s
    except ValueError:
        return "0"


def main():
    if not CSV_FILE.exists():
        print(f"오류: {CSV_FILE} 파일이 없습니다.")
        return

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("CSV에 행이 없습니다.")
        return

    total = len(rows)
    chunk_size = (total + NUM_FILES - 1) // NUM_FILES

    create_table_sql = """-- PostgreSQL table for Apple retail sales data (from data_02_inventory_final.csv)
DROP TABLE IF EXISTS sales_data CASCADE;
CREATE TABLE sales_data (
    sale_id VARCHAR(50),
    sale_date DATE,
    store_id VARCHAR(20),
    product_id VARCHAR(20),
    quantity INTEGER,
    product_name VARCHAR(255),
    category_id VARCHAR(20),
    launch_date DATE,
    price DECIMAL(12,2),
    category_name VARCHAR(100),
    store_name VARCHAR(255),
    city VARCHAR(100),
    country VARCHAR(100),
    total_sales DECIMAL(12,2)
);

"""

    # CSV 컬럼명 (대소문자 혼용 대응)
    def get(row: dict, *keys: str) -> str:
        for k in keys:
            if k in row:
                return row[k] or ""
            if k.lower() in row:
                return row[k.lower()] or ""
        return ""

    for i in range(NUM_FILES):
        start = i * chunk_size
        end = min(start + chunk_size, total)
        if start >= total:
            break

        chunk = rows[start:end]
        out_file = DATA_DIR / f"{OUTPUT_PREFIX}_{i+1:02d}.sql"

        with open(out_file, "w", encoding="utf-8") as f:
            if i == 0:
                f.write(create_table_sql)

            f.write(f"-- Part {i+1}/{NUM_FILES}: rows {start+1} to {end} (total: {len(chunk)} rows)\n")
            f.write("INSERT INTO sales_data (sale_id, sale_date, store_id, product_id, quantity, product_name, category_id, launch_date, price, category_name, store_name, city, country, total_sales) VALUES\n")

            values_list = []
            for row in chunk:
                values = [
                    escape_sql(get(row, "sale_id")),
                    escape_sql(get(row, "sale_date")),
                    escape_sql(get(row, "store_id")),
                    escape_sql(get(row, "product_id")),
                    num_sql(get(row, "quantity")),
                    escape_sql(get(row, "Product_Name", "product_name")),
                    escape_sql(get(row, "category_id")),
                    escape_sql(get(row, "Launch_Date", "launch_date")),
                    num_sql(get(row, "price")),
                    escape_sql(get(row, "category_name")),
                    escape_sql(get(row, "Store_Name", "store_name")),
                    escape_sql(get(row, "City", "city")),
                    escape_sql(get(row, "Country", "country")),
                    num_sql(get(row, "total_sales")),
                ]
                values_list.append("(" + ", ".join(values) + ")")

            batch_size = 500
            for j in range(0, len(values_list), batch_size):
                batch = values_list[j : j + batch_size]
                f.write(",\n".join(batch))
                if j + batch_size < len(values_list):
                    f.write(",\n")
                else:
                    f.write("\n")

            f.write(";\n")
        print(f"생성: {out_file.name} ({len(chunk)} rows)")

    print(f"\n완료: {NUM_FILES}개 SQL 파일이 {DATA_DIR} (01.data)에 저장되었습니다.")


if __name__ == "__main__":
    main()
