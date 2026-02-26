"""
dashboard_sales_data.sql 의 각 INSERT 행에서 inventory(16번째 컬럼) 값을 1/100로 변경.
실행: python patch_inventory_one_hundredth.py
"""
import re
from pathlib import Path

path = Path(__file__).parent / "dashboard_sales_data.sql"
content = path.read_text(encoding="utf-8")
lines = content.split("\n")
out = []


def parse_row(line: str) -> list[str] | None:
    s = line.strip()
    if not s.startswith("("):
        return None
    rest = s[1:].lstrip()
    fields = []
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


for line in lines:
    s = line.strip()
    if not s.startswith("(") or (")," not in s and ");" not in s):
        out.append(line)
        continue
    fields = parse_row(line)
    if fields is None:
        out.append(line)
        continue
    try:
        inv = int(float(fields[15]))
        fields[15] = str(max(0, inv // 100))
    except (ValueError, TypeError):
        pass
    new_row = "(" + ", ".join(fields) + ")"
    if line.rstrip().endswith(");"):
        new_row += ");"
    else:
        new_row += ","
    indent = line[: len(line) - len(line.lstrip())]
    out.append(indent + new_row)

path.write_text("\n".join(out), encoding="utf-8")
print("Done: inventory values set to 1/100.")
