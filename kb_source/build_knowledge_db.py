# -*- coding: utf-8 -*-
# Knowledge base chunking & vectorization script (ONNX local version)
# Uses local model_qint8.onnx + vocab.txt, no PyTorch needed

import hashlib, json
import re
import sqlite3
import numpy as np
from pathlib import Path

try:
    import onnxruntime as ort
except ImportError:
    print("Please run: pip install onnxruntime numpy")
    exit(1)

BASE_DIR = Path(__file__).parent

MAX_SEQ_LEN = 512
MAX_CHARS = 500
OVERLAP_CHARS = 60

ALIAS_MAP = {
    "气盘": ["气头", "纳米管", "增氧盘", "增氧环", "曝气盘", "微孔管"],
    "增氧机": ["风机", "鼓风机", "高速风机", "罗茨风机", "增氧泵", "叶轮增氧机", "水车增氧机"],
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

SYNONYM_GROUPS = [
    ["高了", "偏高", "含量高了", "超标", "含量超标"],
]

def add_synonym_groups_to_text(text, max_per_group=3):
    lines = text.split("\n")
    group_counts = [0] * len(SYNONYM_GROUPS)
    for i, line in enumerate(lines):
        for gidx, group in enumerate(SYNONYM_GROUPS):
            if group_counts[gidx] >= max_per_group:
                continue
            sorted_terms = sorted(group, key=len, reverse=True)
            for term in sorted_terms:
                if term in line:
                    all_terms = "、".join(group)
                    new_line = line.replace(term, term + "（同义：" + all_terms + "）", 1)
                    if new_line != line:
                        group_counts[gidx] += 1
                        lines[i] = new_line
                        break
    return "\n".join(lines)

def add_aliases_to_text(text, max_per_term=3):
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
                    break
    return "\n".join(lines)

def char_ngrams(s, n=4):
    s = re.sub(r'\s+', '', s)
    return set(s[i:i+n] for i in range(len(s) - n + 1))

def ngram_jaccard(a, b, n=4):
    nga = char_ngrams(a, n)
    ngb = char_ngrams(b, n)
    if not nga or not ngb:
        return 0.0
    inter = len(nga & ngb)
    union = len(nga | ngb)
    return inter / union if union > 0 else 0.0

def exact_dedup(chunks):
    seen = set()
    result = []
    for item in chunks:
        content = item[2]
        if content not in seen:
            seen.add(content)
            result.append(item)
    return result

def near_dedup(chunks, threshold=0.85):
    if len(chunks) < 2:
        return chunks
    deduped = [chunks[0]]
    for item in chunks[1:]:
        is_dup = False
        for j, existing in enumerate(deduped):
            sim = ngram_jaccard(item[2], existing[2], 4)
            if sim >= threshold:
                if len(existing[2]) < len(item[2]):
                    deduped[j] = item
                is_dup = True
                break
        if not is_dup:
            deduped.append(item)
    return deduped

class BertTokenizer:
    def __init__(self, vocab_path):
        with open(vocab_path, 'r', encoding='utf-8') as f:
            self.vocab = {t.strip(): i for i, t in enumerate(f)}
        self.cls_id = self.vocab.get('[CLS]', 101)
        self.sep_id = self.vocab.get('[SEP]', 102)
        self.pad_id = self.vocab.get('[PAD]', 0)
        self.unk_id = self.vocab.get('[UNK]', 100)

    def _clean(self, text):
        text = text.replace('\u3000', ' ').replace('\xa0', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def encode(self, text):
        text = self._clean(text)
        chars = list(text)
        ids = []
        for ch in chars:
            if ch in self.vocab:
                ids.append(self.vocab[ch])
            elif ch.isspace():
                continue
            else:
                ids.append(self.unk_id)
        if len(ids) > MAX_SEQ_LEN - 2:
            ids = ids[:MAX_SEQ_LEN - 2]
        input_ids = [self.cls_id] + ids + [self.sep_id]
        attn_mask = [1] * len(input_ids)
        token_type = [0] * len(input_ids)
        pad_len = MAX_SEQ_LEN - len(input_ids)
        if pad_len > 0:
            input_ids += [self.pad_id] * pad_len
            attn_mask += [0] * pad_len
            token_type += [0] * pad_len
        return (
            np.array([input_ids], dtype=np.int64),
            np.array([attn_mask], dtype=np.int64),
            np.array([token_type], dtype=np.int64),
        )

def split_sentences(text, max_splits=3):
    sents = [s.strip() for s in re.split(r'[。？！；！?]', text) if s.strip()]
    return [s for s in sents if len(s) >= 10][:max_splits]

def split_subsections(text, doc_type):
    if doc_type == "rules":
        sections = [r.strip() for r in re.split(r'(?=^\*\*\d+\.\*\*)', text, flags=re.MULTILINE) if r.strip()]
        chunks = []
        for sec in sections:
            body = re.sub(r'^\*\*\d+\.\*\*', '', sec).strip()
            sents = split_sentences(body, 3)
            if not sents:
                chunks.append(sec)
            else:
                m = re.search(r'\*\*(\d+)\.\*\*', sec)
                num = m.group(1) if m else "0"
                for s in sents:
                    chunks.append(f"**{num}.** {s}")
        return chunks
    elif doc_type == "theory":
        parts = re.split(r'(?=^## )', text, flags=re.MULTILINE)
        chunks = []
        for p in parts:
            p = p.strip()
            if not p: continue
            title = re.match(r'(## [^\n]+)', p)
            sec_title = title.group(1) if title else ""
            body = re.sub(r'^## [^\n]+\n*', '', p).strip()
            sents = split_sentences(body, 5)
            if not sents:
                chunks.append(p)
            else:
                for s in sents:
                    chunks.append(f"{sec_title}\n{s}")
        return chunks
    elif doc_type == "manual":
        parts = re.split(r'(?=^\d+\.\d+\.\d+(?:\.\d+)*)', text, flags=re.MULTILINE)
        chunks = []
        for p in parts:
            p = p.strip()
            if not p: continue
            sec = re.match(r'^(\d+\.\d+\.\d+(?:\.\d+)*)', p)
            sec_num = sec.group(1) if sec else ""
            body = re.sub(r'^\d+\.\d+\.\d+(?:\.\d+)*\s*', '', p).strip()
            sents = split_sentences(body, 3)
            if not sents:
                chunks.append(p)
            else:
                for s in sents:
                    chunks.append(f"{sec_num} {s}")
        return chunks
    elif doc_type == "pharma":
        lines = text.split("\n")
        chunks = []
        buf = []
        def flush():
            nonlocal buf
            if buf:
                chunks.append("\n".join(buf).strip())
                buf = []
        for i, line in enumerate(lines):
            if re.match(r'^[\u4e00-\u9fff]{2,8}$', line) and i + 1 < len(lines) and re.match(r'^[A-Z]', lines[i + 1]):
                flush()
            buf.append(line)
        flush()
        return [c for c in chunks if len(c) >= 50]
    elif doc_type == "lecture":
        parts = re.split(r'(?=^\d{8}\s)', text, flags=re.MULTILINE)
        chunks = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 50]
        return chunks
    elif doc_type == "single":
        text = text.strip()
        return [text] if len(text) >= 20 else []
    return []

def get_embedding(session, tokenizer, text):
    ids, mask, ttype = tokenizer.encode(text)
    outputs = session.run(None, {
        'input_ids': ids,
        'attention_mask': mask,
        'token_type_ids': ttype,
    })
    emb = outputs[0][0, 0, :].copy()
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm
    return emb.astype(np.float32)

def main():
    model_path = BASE_DIR / "model_qint8.onnx"
    vocab_path = BASE_DIR / "vocab.txt"

    if not model_path.exists():
        print(f"Error: {model_path} not found")
        return
    if not vocab_path.exists():
        print(f"Error: {vocab_path} not found")
        return

    print("Loading model...")
    tokenizer = BertTokenizer(vocab_path)
    session = ort.InferenceSession(str(model_path))

    all_chunks = []
    print("Chunking documents...")

    name_map = [
        ("水质调控篇.md", "theory"),
        ("小棚实战手册.md", "manual"),
        ("操作规则2026.md", "rules"),
        ("水生动物药物学.md", "pharma"),
        ("范老师徒弟班文字内容整理.md", "lecture"),
        ("肥水培藻循环.md", "single"),
        ("有毒氨比例表.md", "single"),
        ("微生物藻类增殖数据.md", "single"),
        ("对虾分阶段投喂管理.md", "single"),
        ("弧菌药敏实验数据.md", "single"),
    ]
    for fname, doc_id in name_map:
        path = BASE_DIR / fname
        if not path.exists():
            print(f"  Skip: {fname} (not found)")
            continue

        text = path.read_text(encoding='utf-8-sig')
        text = add_aliases_to_text(text)
        text = add_synonym_groups_to_text(text)

        chunks = split_subsections(text, doc_id)
        start = len(all_chunks)
        for i, ch in enumerate(chunks):
            all_chunks.append((doc_id, i, ch))
        print(f"  {path.name}: {len(all_chunks) - start} raw chunks")

    if not all_chunks:
        print("No chunks generated. Check if input files exist.")
        print("Expected files: 水质调控篇.md, 小棚实战手册.md, 操作规则2026.md, 水生动物药物学.md, 范老师徒弟班文字内容整理.md")
        return

    pre_dedup = len(all_chunks)
    all_chunks = exact_dedup(all_chunks)
    after_exact = len(all_chunks)
    all_chunks = near_dedup(all_chunks, 0.85)
    after_near = len(all_chunks)
    print(f"\nDedup: {pre_dedup} -> {after_exact} (exact) -> {after_near} (near, threshold=0.85)")

    print(f"\nTotal: {len(all_chunks)} chunks, generating embeddings...")

    embeddings = []
    total = len(all_chunks)
    for i, (_, _, content) in enumerate(all_chunks):
        emb = get_embedding(session, tokenizer, content)
        embeddings.append(emb)
        if (i + 1) % 50 == 0 or i == total - 1:
            print(f"  [{i+1}/{total}]")

    version_counter_file = BASE_DIR / "kb_version.txt"
    current_version = 1
    if version_counter_file.exists():
        try:
            current_version = int(version_counter_file.read_text().strip()) + 1
        except ValueError:
            pass
    version_counter_file.write_text(str(current_version))

    out_path = BASE_DIR / "knowledge_base.db"
    if out_path.exists():
        out_path.unlink()
    conn = sqlite3.connect(str(out_path))
    conn.execute("""
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB
        )
    """)
    conn.execute("CREATE INDEX idx_doc_id ON chunks(doc_id)")
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")

    for i, (doc_id, idx, content) in enumerate(all_chunks):
        emb_bytes = embeddings[i].tobytes()
        conn.execute(
            "INSERT INTO chunks (doc_id, chunk_index, content, embedding) VALUES (?, ?, ?, ?)",
            (doc_id, idx, content, emb_bytes)
        )

    conn.commit()
    conn.close()
    md5_hash = hashlib.md5(out_path.read_bytes()).hexdigest()

    conn = sqlite3.connect(str(out_path))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("version", str(current_version)))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("chunks", str(len(all_chunks))))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("md5", md5_hash))
    conn.commit()
    conn.close()

    version_info = {
        "version": current_version,
        "chunks": len(all_chunks),
        "md5": md5_hash,
    }
    ver_path = BASE_DIR / "knowledge_base_version.json"
    with open(ver_path, "w", encoding="utf-8") as f:
        json.dump(version_info, f, indent=2)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nDone! v{current_version}, {len(all_chunks)} chunks -> {out_path.name} ({size_mb:.1f} MB)")
    print(f"  md5={md5_hash}")

if __name__ == "__main__":
    main()
