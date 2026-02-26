"""
data_02_inventory_final.csv 의 Safety_Stock, Inventory, Status, Frozen_Money 값을
dashboard_sales_data.sql 의
store_stock_quantity, inventory, frozen_money, safety_stock, status 에 매핑해서 교체.

실행:
    python patch_inventory_from_csv.py

매핑 규칙 (가정):
- store_stock_quantity  <- CSV.Inventory
- inventory             <- CSV.Inventory
- frozen_money          <- CSV.Frozen_Money
- safety_stock          <- CSV.Safety_Stock
- status                <- CSV.Status

매칭 키:
- (sale_date, store_id, Product_Name, quantity, price)
  * Product_Name / product_name 은 영문자·숫자만 남기고 소문자로 변환하여 비교.
"""

import csv
import re
from pathlib import Path


def normalize_name(name: str) -> str:
    """영문/숫자만 남기고 소문자로 변환."""
    return re.sub(r"[^A-Za-z0-9]+", "", (name or "")).lower()


def strip_quotes(val: str) -> str:
    """'값' 형태에서 바깥 작은따옴표 제거 및 이스케이프 복원."""
    s = val.strip()
    if s.startswith("'") and s.endswith("'"):
        inner = s[1:-1]
        return inner.replace("''", "'")
    return s


def parse_row(line: str) -> list[str] | None:
    """
    SQL VALUES 한 줄에서 괄호 안의 19개 필드를 파싱해 리스트로 반환.
    문자열은 작은따옴표를 포함한 원본 형태로, 숫자는 그대로 반환.
    """
    s = line.strip()
    if not s.startswith("("):
        return None
    rest = s[1:].lstrip()
    fields: list[str] = []
    while rest:
        rest = rest.lstrip()
        if rest.startswith(")"):
            break
        if rest.startswith("'"):
            i = 1
            while i < len(rest):
                if rest[i] == "'":
                    if i + 1 < len(rest) and rest[i + 1] == "'":
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            fields.append(rest[:i])
            rest = rest[i:].lstrip()
            if rest.startswith(","):
                rest = rest[1:]
            continue
        m = re.match(r"([-\d.]+)", rest)
        if m:
            fields.append(m.group(1))
            rest = rest[m.end() :].lstrip()
            if rest.startswith(","):
                rest = rest[1:]
            continue
        break
    return fields if len(fields) >= 19 else None


BASE_DIR = Path(__file__).resolve().parents[2]  # 프로젝트 루트
CSV_PATH = BASE_DIR / "00.old" / "data_02_inventory_final.csv"
SQL_PATH = Path(__file__).parent / "dashboard_sales_data.sql"

# 1) CSV 로드 및 인덱싱
index: dict[tuple, list[dict]] = {}

print("DEBUG CSV_PATH:", CSV_PATH)

with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    # BOM(UTF-8-SIG) 제거
    if reader.fieldnames:
        reader.fieldnames = [name.lstrip("\ufeff") for name in reader.fieldnames]
    print("DEBUG csv_fieldnames:", reader.fieldnames)
    for row in reader:
        try:
            sale_date = row["sale_date"]
            store_id = row["store_id"]
            prod_norm = normalize_name(row["Product_Name"])
            qty = int(float(row["quantity"]))
            price = float(row["price"])
        except (KeyError, ValueError, TypeError):
            continue
        key = (sale_date, store_id, prod_norm, qty, price)
        index.setdefault(key, []).append(row)

# 디버그: 특정 케이스(2020-03-12, ST-56, Smart Keyboard Folio) 확인
debug_sample_keys = [
    k
    for k in index.keys()
    if k[0] == "2020-03-12"
    and k[1].strip() == "ST-56"
    and "smartkeyboardfolio" in k[2]
]
print("DEBUG csv_index_size:", len(index))
print("DEBUG csv_keys_for_sample:", debug_sample_keys[:5])


content = SQL_PATH.read_text(encoding="utf-8")
lines = content.split("\n")
out: list[str] = []

matched = 0
not_found = 0
parse_failed = 0

for line in lines:
    s = line.strip()
    if not s.startswith("(") or (")," not in s and ");" not in s):
        out.append(line)
        continue

    fields = parse_row(line)
    if fields is None:
        parse_failed += 1
        out.append(line)
        continue

    try:
        sale_date = strip_quotes(fields[1])
        store_id = strip_quotes(fields[2])
        prod_norm = normalize_name(strip_quotes(fields[5]))
        qty = int(float(fields[4]))
        price = float(fields[8])
    except (ValueError, TypeError, IndexError):
        parse_failed += 1
        out.append(line)
        continue

    key = (sale_date, store_id, prod_norm, qty, price)
    # 디버그: 초기 몇 개 키만 존재 여부 출력
    total_seen = matched + not_found + parse_failed
    if total_seen < 5:
        print("DEBUG key_from_sql:", key, " -> in_csv:", key in index)

    candidates = index.get(key)
    if not candidates:
        not_found += 1
        out.append(line)
        continue

    row = candidates[0]  # 동일 키가 여러 개면 첫 번째 사용

    try:
        inv_val = int(float(row["Inventory"]))
        ss_val = int(float(row["Safety_Stock"]))
        fm_raw = row.get("Frozen_Money", "").strip()
        fm_val = fm_raw if fm_raw else str(inv_val)
        status_val = row["Status"]
    except (KeyError, ValueError, TypeError):
        parse_failed += 1
        out.append(line)
        continue

    # store_stock_quantity (idx 14), inventory (15), frozen_money (16),
    # safety_stock (17), status (18) 업데이트
    try:
        fields[14] = str(inv_val)
        fields[15] = str(inv_val)
        fields[16] = fm_val
        fields[17] = str(ss_val)
        fields[18] = "'" + status_val.replace("'", "''") + "'"
    except IndexError:
        parse_failed += 1
        out.append(line)
        continue

    matched += 1

    new_row = "(" + ", ".join(fields) + ")"
    if line.rstrip().endswith(");"):
        new_row += ");"
    else:
        new_row += ","

    indent = line[: len(line) - len(line.lstrip())]
    out.append(indent + new_row)


SQL_PATH.write_text("\n".join(out), encoding="utf-8")
print(
    f"Done: updated from CSV. matched={matched}, not_found={not_found}, parse_failed={parse_failed}"
)

