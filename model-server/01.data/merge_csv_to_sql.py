"""
data_02_inventory_final.csv 와 Apple_Retail_Sales_Dataset_Modified SQL 스키마 결합.
- CSV 로드 후 sale_id 기준 중복 제거
- store_stock_quantity = quantity * (0.95 ~ 1.30) 랜덤 생성
- 10개 SQL 파일로 분할 출력 (01: CREATE+INSERT, 02~10: INSERT)
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_SERVER = SCRIPT_DIR.parent
CSV_PATH = MODEL_SERVER / "00.old" / "data_02_inventory_final.csv"
NUM_PARTS = 10
OUTPUT_NAME = "Apple_Retail_Sales_Dataset_Modified"

# SQL 테이블 컬럼 순서 (INSERT용) — 재고 전용 컬럼 포함
SQL_COLUMNS = [
    "sale_id", "sale_date", "store_id", "product_id", "quantity",
    "product_name", "category_id", "launch_date", "price", "category_name",
    "store_name", "city", "country", "total_sales", "store_stock_quantity",
    "inventory", "frozen_money", "safety_stock", "status",
]

# CSV 컬럼명 -> SQL 컬럼명 매핑
COLUMN_MAP = {
    "Product_Name": "product_name",
    "Launch_Date": "launch_date",
    "Store_Name": "store_name",
    "City": "city",
    "Country": "country",
    "Inventory": "inventory",
    "Frozen_Money": "frozen_money",
    "Safety_Stock": "safety_stock",
    "Status": "status",
}


def _sql_escape(s):
    """PostgreSQL: single quote -> double single quote."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip()
    return s.replace("'", "''")


def _row_to_sql_value(row):
    """한 행을 SQL VALUES 한 항목 문자열로."""
    parts = []
    for col in SQL_COLUMNS:
        v = row.get(col)
        if col in ("quantity", "store_stock_quantity", "inventory", "safety_stock"):
            parts.append(str(int(v)) if pd.notna(v) and str(v).strip() != "" else "0")
        elif col in ("price", "total_sales", "frozen_money"):
            if pd.isna(v) or str(v).strip() == "":
                parts.append("0")
            else:
                try:
                    parts.append(str(round(float(v), 2)))
                except (TypeError, ValueError):
                    parts.append("0")
        elif col in ("sale_date", "launch_date"):
            if pd.isna(v) or str(v).strip() == "":
                parts.append("NULL")
            else:
                s = str(v).strip()[:10]
                if re.match(r"\d{4}-\d{2}-\d{2}", s):
                    parts.append(f"'{s}'")
                else:
                    parts.append("NULL")
        elif col == "status":
            parts.append(f"'{_sql_escape(v)}'" if pd.notna(v) and str(v).strip() else "'Normal'")
        else:
            parts.append(f"'{_sql_escape(v)}'")
    return "(" + ", ".join(parts) + ")"


def main():
    if not CSV_PATH.exists():
        print(f"CSV 없음: {CSV_PATH}")
        return

    print(f"CSV 로드: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, low_memory=False)

    # 컬럼 정규화: 대문자 컬럼명 -> 소문자
    rename = {}
    for c in list(df.columns):
        if c in COLUMN_MAP:
            rename[c] = COLUMN_MAP[c]
    df = df.rename(columns=rename)

    # 필요한 컬럼 (재고 전용 포함; store_stock_quantity는 아래에서 생성)
    required = [c for c in SQL_COLUMNS if c != "store_stock_quantity"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"필요 컬럼 없음: {missing}")
        return

    df = df[required].copy()

    # sale_id 기준 중복 제거 (첫 행 유지)
    before = len(df)
    df = df.drop_duplicates(subset=["sale_id"], keep="first")
    after = len(df)
    print(f"중복 제거: {before} -> {after} 행")

    # 숫자/날짜 컬럼 정규화
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    if "inventory" in df.columns:
        df["inventory"] = pd.to_numeric(df["inventory"], errors="coerce").fillna(0).astype(int)
    if "frozen_money" in df.columns:
        df["frozen_money"] = pd.to_numeric(df["frozen_money"], errors="coerce").fillna(0)
    if "safety_stock" in df.columns:
        df["safety_stock"] = pd.to_numeric(df["safety_stock"], errors="coerce").fillna(0).astype(int)
    if "status" not in df.columns:
        df["status"] = "Normal"

    # store_stock_quantity: CSV에 없으면 quantity * (0.95 ~ 1.30) 랜덤 생성
    if "store_stock_quantity" not in df.columns:
        rng = np.random.default_rng(42)
        q = df["quantity"].values
        ratio = 0.95 + rng.random(len(df)) * 0.35
        df["store_stock_quantity"] = np.clip(np.round(q * ratio), 1, None).astype(int)
    else:
        df["store_stock_quantity"] = pd.to_numeric(df["store_stock_quantity"], errors="coerce").fillna(0).astype(int)

    n = len(df)
    chunk_size = (n + NUM_PARTS - 1) // NUM_PARTS
    rows_per_part = [min(chunk_size, n - i * chunk_size) for i in range(NUM_PARTS)]
    rows_per_part = [x for x in rows_per_part if x > 0]

    create_table_sql = """-- PostgreSQL table for Apple retail sales data (from data_02_inventory_final.csv + Modified)
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
    total_sales DECIMAL(12,2),
    store_stock_quantity INTEGER,
    inventory INTEGER,
    frozen_money DECIMAL(12,2),
    safety_stock INTEGER,
    status VARCHAR(50)
);
"""

    insert_header = "INSERT INTO sales_data (" + ", ".join(SQL_COLUMNS) + ") VALUES\n"
    start = 0
    for part in range(1, NUM_PARTS + 1):
        take = rows_per_part[part - 1] if part <= len(rows_per_part) else 0
        if take <= 0:
            break
        chunk = df.iloc[start : start + take]
        start += take

        path = SCRIPT_DIR / f"{OUTPUT_NAME}_{part:02d}.sql"
        if part == 1:
            content = create_table_sql
            content += f"\n-- Part 1/10: rows 1 to {len(chunk)} (total: {len(chunk)} rows)\n"
        else:
            content = f"-- Part {part}/10: rows {start - take + 1} to {start} (total: {len(chunk)} rows)\n"
        content += insert_header

        values = []
        for _, row in chunk.iterrows():
            values.append(_row_to_sql_value(row))
        content += ",\n".join(values)
        content += "\n;\n"

        path.write_text(content, encoding="utf-8")
        print(f"  작성: {path.name} ({len(chunk)} rows)")

    print("완료: 10개 SQL 파일 생성.")


if __name__ == "__main__":
    main()
