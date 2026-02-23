"""
대시보드 전용 경량 SQL 생성.
- 01.data 전체를 로드한 뒤 2020년 이후로 필터, 국가별 비율 유지하며 약 45,000행 샘플 추출.
- model-server/02.Database for dashboard/dashboard_sales_data.sql 한 파일로 출력.
- 실행: model-server 폴더에서
  python "02.Database for dashboard/build_dashboard_sql.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

# model-server 루트를 path에 추가
_MODEL_SERVER = Path(__file__).resolve().parent.parent
if str(_MODEL_SERVER) not in sys.path:
    sys.path.insert(0, str(_MODEL_SERVER))

import pandas as pd

# 컬럼 순서 (01.data와 동일)
SQL_COLUMNS = [
    "sale_id", "sale_date", "store_id", "product_id", "quantity", "product_name",
    "category_id", "launch_date", "price", "category_name", "store_name",
    "city", "country", "total_sales", "store_stock_quantity", "inventory",
    "frozen_money", "safety_stock", "status",
]

# 로더에서 쓰는 대문자 컬럼명 → SQL용 소문자
CANONICAL_TO_SQL = {
    "City": "city",
    "Country": "country",
    "Product_Name": "product_name",
    "Store_Name": "store_name",
}


def _escape_sql(s: str) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return "NULL"
    s = str(s).replace("\\", "\\\\").replace("'", "''")
    return "'" + s + "'"


def _row_to_sql_values(row: pd.Series, columns: list[str]) -> str:
    parts = []
    for c in columns:
        raw = row.get(c)
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            parts.append("NULL")
        elif c in ("sale_date", "launch_date") or "date" in c.lower():
            parts.append(_escape_sql(str(raw)[:10] if raw else ""))
        elif c in ("quantity", "store_stock_quantity", "inventory", "safety_stock"):
            try:
                parts.append(str(int(float(raw))))
            except (TypeError, ValueError):
                parts.append("NULL")
        elif c in ("price", "total_sales", "frozen_money"):
            try:
                parts.append(str(float(raw)))
            except (TypeError, ValueError):
                parts.append("NULL")
        else:
            parts.append(_escape_sql(raw))
    return "(" + ", ".join(parts) + ")"


def main() -> None:
    import load_sales_data as loader

    df = loader.load_sales_dataframe(force_reload=True)
    if df is None or df.empty:
        print("ERROR: No data from load_sales_data. Check 01.data SQL files.")
        sys.exit(1)

    # 컬럼명 정리: 로더가 City/Country 등으로 바꿨을 수 있음 → SQL 컬럼명에 매핑
    col_map = {}
    for sql_col in SQL_COLUMNS:
        if sql_col in df.columns:
            col_map[sql_col] = sql_col
        else:
            for cap, low in CANONICAL_TO_SQL.items():
                if low == sql_col and cap in df.columns:
                    col_map[sql_col] = cap
                    break
            else:
                col_map[sql_col] = sql_col

    # 실제 사용할 DataFrame 컬럼 (SQL 순서)
    use_cols = [col_map[c] for c in SQL_COLUMNS if col_map[c] in df.columns]
    if len(use_cols) != len(SQL_COLUMNS):
        missing = set(SQL_COLUMNS) - set(col_map[c] for c in SQL_COLUMNS if col_map[c] in df.columns)
        print("WARNING: Missing columns for SQL:", missing)

    df = df[use_cols].copy()
    df.columns = SQL_COLUMNS[: len(use_cols)]

    # sale_date 파싱
    if "sale_date" in df.columns:
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
        df = df[df["sale_date"].dt.year >= 2020].copy()

    if df.empty:
        print("ERROR: No rows after 2020 filter.")
        sys.exit(1)

    # 약 20,000행 샘플 (경량화·국가 비율 대략 유지)
    target = 20_000
    if len(df) <= target:
        sample = df
    else:
        sample = df.sample(n=target, random_state=42)

    sample = sample.sort_values(["country", "sale_date"]).reset_index(drop=True)
    out_dir = Path(__file__).resolve().parent
    out_file = out_dir / "dashboard_sales_data.sql"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("-- Dashboard-only lightweight sales_data (subset from 01.data, 2020+, sampled)\n")
        f.write("DROP TABLE IF EXISTS sales_data CASCADE;\n")
        f.write("CREATE TABLE sales_data (\n")
        f.write("    sale_id VARCHAR(50),\n")
        f.write("    sale_date DATE,\n")
        f.write("    store_id VARCHAR(20),\n")
        f.write("    product_id VARCHAR(20),\n")
        f.write("    quantity INTEGER,\n")
        f.write("    product_name VARCHAR(255),\n")
        f.write("    category_id VARCHAR(20),\n")
        f.write("    launch_date DATE,\n")
        f.write("    price DECIMAL(12,2),\n")
        f.write("    category_name VARCHAR(100),\n")
        f.write("    store_name VARCHAR(255),\n")
        f.write("    city VARCHAR(100),\n")
        f.write("    country VARCHAR(100),\n")
        f.write("    total_sales DECIMAL(12,2),\n")
        f.write("    store_stock_quantity INTEGER,\n")
        f.write("    inventory INTEGER,\n")
        f.write("    frozen_money DECIMAL(12,2),\n")
        f.write("    safety_stock INTEGER,\n")
        f.write("    status VARCHAR(50)\n")
        f.write(");\n\n")
        f.write(
            "INSERT INTO sales_data (sale_id, sale_date, store_id, product_id, quantity, product_name, category_id, launch_date, price, category_name, store_name, city, country, total_sales, store_stock_quantity, inventory, frozen_money, safety_stock, status) VALUES\n"
        )

        rows = []
        for i, row in sample.iterrows():
            rows.append(_row_to_sql_values(row, SQL_COLUMNS))
        f.write(",\n".join(rows))
        f.write(";\n")

    print(f"Written {len(sample)} rows to {out_file}")
    print(f"File size: {out_file.stat().st_size / (1024*1024):.2f} MB")


if __name__ == "__main__":
    main()
