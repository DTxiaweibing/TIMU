# -*- coding: utf-8 -*-
"""Add alias annotations to KB source md files for better vector retrieval."""

import re
from pathlib import Path

BASE_DIR = Path(__file__).parent

ALIAS_MAP = {
    "气盘": ["气头", "纳米管", "增氧盘", "增氧环", "曝气盘", "微孔管"],
    "增氧机": ["风机", "鼓风机", "罗茨风机", "增氧泵", "叶轮增氧机", "水车增氧机"],
    "盐度": ["咸度", "含盐量", "盐分"],
    "亚盐": ["亚硝酸盐", "亚硝态氮"],
    "氨氮毒性": ["游离氨", "非离子氨"],
    "硬度": ["总硬度"],
    "碱度": ["总碱度"],
    "投喂": ["喂料"],
    "摄食": ["吃料"],
    "食台": ["料台", "料盘", "食盘"],
    "拌料配比": ["拌药"],
    "饵料系数": ["饲料系数", "料比"],
    "加热棒": ["加温棒", "加热管"],
    "锅炉加温": ["烧锅炉"],
    "小棚": ["冬棚", "保温棚"],
    "调水": ["做水"],
    "培藻": ["肥水", "培水"],
    "放苗": ["投苗", "下苗"],
    "换水": ["加水"],
    "底排污": ["吸底"],
    "应激游塘": ["游塘"],
    "缺氧浮头": ["浮头"],
    "损耗": ["掉苗"],
    "红体病": ["红体"],
    "肠炎白便": ["白便"],
    "肠炎": ["空肠空胃"],
}


def add_aliases_to_text(text: str, max_per_term: int = 3) -> str:
    """
    For each standard term, add alias annotation to the first `max_per_term`
    occurrences found in the text.
    """
    lines = text.split("\n")
    term_counts = {term: 0 for term in ALIAS_MAP}

    for i, line in enumerate(lines):
        for term, aliases in ALIAS_MAP.items():
            if term_counts[term] >= max_per_term:
                continue
            if term in line:
                alias_text = "（又称" + "、".join(aliases) + "）"
                new_line = line.replace(term, term + alias_text, 1)
                if new_line != line:
                    term_counts[term] += 1
                    lines[i] = new_line
                    break  # one replacement per line

    return "\n".join(lines)


def main():
    files = [
        "水质理论篇.md",
        "小棚实操手册.md",
        "操作规则302条.md",
    ]

    total_ops = 0
    for fname in files:
        path = BASE_DIR / fname
        if not path.exists():
            print(f"  Skip: {fname} (not found)")
            continue

        print(f"Processing: {fname}...")
        text = path.read_text(encoding="utf-8-sig")
        modified = add_aliases_to_text(text)

        ops = modified.count("（又称")
        total_ops += ops

        if ops > 0:
            backup = path.with_suffix(path.suffix + ".bak")
            path.rename(backup)
            path.write_text(modified, encoding="utf-8-sig")
            print(f"  -> {ops} alias annotations added (backup: {backup.name})")
        else:
            print(f"  -> No changes needed")

    print(f"\nDone! {total_ops} total alias annotations added across {len(files)} files.")


if __name__ == "__main__":
    main()
