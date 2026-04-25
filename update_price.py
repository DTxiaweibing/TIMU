import json
import re

# 尝试使用 pandas，若不可用则回退到 openpyxl
try:
    import pandas as pd
    ENGINE = "pandas"
except ImportError:
    from openpyxl import load_workbook
    ENGINE = "openpyxl"

EXCEL_FILE = "price.xlsx"
JSON_FILE = "price.json"

def is_lobster(name):
    """判断是否是龙虾类，不分大小"""
    lobsters = ['龙虾', '澳洲龙虾', '波士顿龙虾', '小青龙', '花龙', '青龙']
    return any(lob in name for lob in lobsters)

def process_item(name, price, target_list):
    # 1. 统一格式，保留原始名称
    original_name = name.strip()
    cleaned_name = original_name.replace('（', '(').replace('）', ')').strip()
    
    # 2. 河虾、龙虾 直接原样保留，不做任何处理
    if '河虾' in cleaned_name or is_lobster(cleaned_name):
        target_list.append({"name": original_name, "price": price})
        return
        
    # 3. 对于其他商品，检查价格是否需要拆分
    prices = re.split(r'[-~—]', price)
    prices = [p.strip() for p in prices if p.strip()]
    price_count = len(prices)
    
    # 如果只有一个价格，直接保留
    if price_count == 1:
        target_list.append({"name": original_name, "price": prices[0]})
        return

    # 4. 提取纯净名称（去掉括号里的 大中小 等描述）
    base_name = re.sub(r'\([^)]*\)', '', cleaned_name).strip()
    
    # 5. 按价格数量分配规格
    if price_count == 2:
        specs = ['大', '小']
    elif price_count == 3:
        specs = ['大', '中', '小']
    else:
        # 万一有4个以上的价格，就先保留原样，以后再调整
        target_list.append({"name": original_name, "price": price})
        return
    
    for i, spec in enumerate(specs):
        target_list.append({
            "name": f"{base_name}（{spec}）",
            "price": prices[i]
        })

def normalize_date(raw_date):
    """把各种日期格式统一成 yyyy/MM/dd"""
    if not raw_date:
        return ""
    raw_date = str(raw_date).strip()
    match = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', raw_date)
    if match:
        year, month, day = match.groups()
        return f"{year}/{int(month):02d}/{int(day):02d}"
    return raw_date

def main():
    # 1. 读取 Excel 文件
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
    
    # 2. 逐行解析
    for row in rows:
        if not row or all(pd.isna(c) if ENGINE == "pandas" else c == '' for c in row):
            continue
        
        row = [str(c).strip() if (not (pd.isna(c) if ENGINE == "pandas" else c == '')) else '' for c in row]
        row_text = ' '.join(row)
        
        # 提取日期
        if '日期:' in row_text:
            parts = row_text.split('日期:')
            if len(parts) > 1:
                date_str = normalize_date(parts[1])
            continue
        
        first_cell = row[0]
        # 识别分类标题
        if '批发价' in first_cell:
            title = first_cell.replace('：', ':').split(':')[0].strip()
            current_cat = {"title": title, "items": []}
            categories.append(current_cat)
            continue
        
        # 跳过表头行
        if first_cell in ['编号', '品名']:
            continue
        
        # 数据行处理
        if current_cat is not None:
            # 左列 (列1: 品名, 列2: 价格)
            if len(row) >= 3 and row[1] and row[2]:
                process_item(row[1], row[2], current_cat["items"])
            # 右列 (列4: 品名, 列5: 价格)
            if len(row) >= 6 and row[4] and row[5]:
                process_item(row[4], row[5], current_cat["items"])
    
    # 3. 给每个分类内的商品按名称排序（河虾就会集中到一起）
    for cat in categories:
        cat["items"].sort(key=lambda x: x["name"])
    
    # 4. 生成 JSON (不再过滤空分类，保留主标题)
    result = {"date": date_str, "categories": categories}
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    total_items = sum(len(c['items']) for c in categories)
    print(f"✅ 成功生成 {JSON_FILE}，共 {len(categories)} 个分类，{total_items} 条记录")

if __name__ == "__main__":
    main()