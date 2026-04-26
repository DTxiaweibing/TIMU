import json
import re

try:
    import pandas as pd
    ENGINE = "pandas"
except ImportError:
    from openpyxl import load_workbook
    ENGINE = "openpyxl"

EXCEL_FILE = "price.xlsx"
JSON_FILE = "price.json"

def is_lobster(name):
    lobsters = ['龙虾', '澳洲龙虾', '波士顿龙虾', '小青龙', '花龙', '青龙']
    return any(lob in name for lob in lobsters)

def process_item(name, price, target_list):
    original_name = name.strip()
    cleaned_name = original_name.replace('（', '(').replace('）', ')').strip()
    if '河虾' in cleaned_name or is_lobster(cleaned_name):
        target_list.append({"name": original_name, "price": price})
        return
    prices = re.split(r'[-~—]', price)
    prices = [p.strip() for p in prices if p.strip()]
    price_count = len(prices)
    if price_count == 1:
        target_list.append({"name": original_name, "price": prices[0]})
        return
    base_name = re.sub(r'\([^)]*\)', '', cleaned_name).strip()
    if price_count == 2:
        specs = ['大', '小']
    elif price_count == 3:
        specs = ['大', '中', '小']
    else:
        target_list.append({"name": original_name, "price": price})
        return
    for i, spec in enumerate(specs):
        target_list.append({"name": f"{base_name}（{spec}）", "price": prices[i]})

def process_lobster(row, target_list, last_price):
    if len(row) < 4:
        return last_price
    name = row[1].strip() if row[1] else ''
    spec = row[2].strip() if row[2] else ''
    price_str = row[3].strip() if row[3] else ''
    if '龙虾' not in name or not spec:
        return last_price
    if not price_str:
        price_str = last_price
    else:
        price_str = price_str.replace('-', '~')
        last_price = price_str
    if not price_str:
        return last_price
    target_list.append({"name": f"龙虾（{spec}）", "price": price_str})
    return last_price

def normalize_date(raw_date):
    if not raw_date:
        return ""
    raw_date = str(raw_date).strip()
    match = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', raw_date)
    if match:
        year, month, day = match.groups()
        return f"{year}/{int(month):02d}/{int(day):02d}"
    return raw_date

def parse_first_price(price_str):
    if not price_str:
        return 0.0
    parts = re.split(r'[~\-]', price_str)
    for part in parts:
        try:
            return float(part.strip())
        except ValueError:
            continue
    return 0.0

def sort_items(items):
    """组内排序：河虾按价格降序，其他按大→中→小；河虾组整体排最后"""
    def base_name(item):
        name = item["name"]
        return re.sub(r'[（(][大中小][）)]$', '', name).strip()

    # 分组并记录首次出现顺序
    grouped = {}
    group_order = []
    for item in items:
        base = base_name(item)
        if base not in grouped:
            grouped[base] = []
            group_order.append(base)
        grouped[base].append(item)

    # 组内排序
    spec_order = {'大': 0, '中': 1, '小': 2}
    for base in grouped:
        lst = grouped[base]
        if '河虾' in base:
            lst.sort(key=lambda x: parse_first_price(x["price"]), reverse=True)
        else:
            def spec_key(item):
                name = item["name"]
                match = re.search(r'[（(]([大中小])[）)]$', name)
                if match:
                    return spec_order.get(match.group(1), 99)
                return 99
            lst.sort(key=spec_key)

    # 河虾组移到末尾
    if '河虾' in group_order:
        group_order.remove('河虾')
        group_order.append('河虾')

    # 恢复组顺序
    result = []
    for base in group_order:
        result.extend(grouped[base])
    return result

def main():
    if ENGINE == "pandas":
        df = pd.read_excel(EXCEL_FILE, header=None, dtype=str)
        rows = df.values.tolist()
    else:
        wb = load_workbook(EXCEL_FILE, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            rows.append([str(c).strip() if c is not None else '' for c in row])
        wb.close()

    categories = []
    date_str = ""
    current_cat = None
    in_lobster = False
    lobster_last_price = ""

    for row in rows:
        if not row or all((pd.isna(c) if ENGINE == "pandas" else c == '') for c in row):
            continue
        row = [str(c).strip() if (not (pd.isna(c) if ENGINE == "pandas" else c == '')) else '' for c in row]
        row_text = ' '.join(row)

        if '日期:' in row_text:
            parts = row_text.split('日期:')
            if len(parts) > 1:
                date_str = normalize_date(parts[1])
            continue

        first_cell = row[0]
        if '批发价' in first_cell:
            title = first_cell.replace('：', ':').split(':')[0].strip()
            current_cat = {"title": title, "items": []}
            categories.append(current_cat)
            if '龙虾' in title:
                in_lobster = True
                lobster_last_price = ""
            else:
                in_lobster = False
            continue

        if first_cell in ['编号', '品名']:
            continue

        if current_cat is not None:
            if in_lobster:
                lobster_last_price = process_lobster(row, current_cat["items"], lobster_last_price)
            else:
                if len(row) >= 3 and row[1] and row[2]:
                    process_item(row[1], row[2], current_cat["items"])
                if len(row) >= 6 and row[4] and row[5]:
                    process_item(row[4], row[5], current_cat["items"])

    for cat in categories:
        cat["items"] = sort_items(cat["items"])

    result = {"date": date_str, "categories": categories}
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_items = sum(len(c['items']) for c in categories)
    print(f"✅ 成功生成 {JSON_FILE}，共 {len(categories)} 个分类，{total_items} 条记录")

if __name__ == "__main__":
    main()