# -*- coding: utf-8 -*-
"""知识库构建脚本（唯一权威切块实现）— 由 GitHub Actions 自动执行。

工作流
    本目录下 *.md 改动 -> push 到 main -> .github/workflows/build_knowledge_base.yml
    -> 本脚本在 ubuntu 上运行 -> 产出 knowledge_base.db / knowledge_base_version.json
    -> workflow 复制到仓库根并提交 -> 客户端比对 version 后自动下载。

与旧版的关键差异（v5 -> v6）
    旧版按 doc_type 各写一套粗糙切分，导致：
      - 1617 块里 859 块(53.1%)短于 50 字
      - 单块最长 58136 字（整篇塞进一块，召回后必然污染 prompt）
      - near_dedup 是 O(n^2) 且会连带丢掉含同义词的块
    新版统一走「语义块 -> 句子切分 -> 相邻合并」，目标 200~500 字，块间保留重叠。

实测确认的链路事实（不要凭直觉改）
    - 端上 TokenEmbedder 与本脚本都是：字符级分词 + CLS 池化 + L2 归一化，seq_len=512
      （旧版 BertTokenizer 名字有误导性，它按单字符查表，不是 WordPiece）
    - 因此不存在离线/端上分词不一致的问题
    - 分桶批量推理与 batch=1/seq_len=512 的余弦约 0.996，只为提速，不改变语义

本地手动跑
    python kb_source/build_knowledge_db.py
"""

import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import struct
import sys
import time

import numpy as np
import onnxruntime as ort

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------- 切块参数 ----------------
MAX_SEQ = 512           # 端上上限，超出 token 会被丢弃
T_MIN, T_MAX = 200, 500 # 目标块长区间（字）
OVERLAP = 60            # 相邻块重叠字数
BATCH = 24              # 分桶批量推理大小

# doc_id 映射：doc_id 被 App 侧 searchByDoc 的 startsWith(docIdPrefix) 依赖，
# routeQuery 也按前缀分派到不同模型，**改名会让线上路由失效**。
NAME_MAP = [
    ("水质理论篇.md", "theory"),
    ("小棚实操手册.md", "manual"),
    ("操作规则2026.md", "rules"),
    ("水生动物药物学.md", "pharma"),
    ("范老师徒弟班文字内容整理.md", "lecture"),
    ("肥水培藻循环.md", "single"),
    ("有毒氨比例表.md", "single"),
    ("微生物藻类增殖数据.md", "single"),
    ("对虾分阶段投喂管理.md", "single"),
    ("弧菌药敏实验数据.md", "single"),
]

# 同义词注入：源文件本身已含大量「（又称…）」，这里只是补充少量同义词以提升召回。
# 与 v5 行为保持一致，可用 --no-alias 关闭。
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
SYNONYM_GROUPS = [["高了", "偏高", "含量高了", "超标", "含量超标"]]


def add_aliases(text, max_per_term=3):
    lines = text.split("\n")
    counts = {t: 0 for t in ALIAS_MAP}
    for i, line in enumerate(lines):
        for term, aliases in ALIAS_MAP.items():
            if counts[term] >= max_per_term or term not in line:
                continue
            new = line.replace(term, term + "（又称" + "、".join(aliases) + "）", 1)
            if new != line:
                counts[term] += 1
                lines[i] = new
                break
    return "\n".join(lines)


def add_synonyms(text, max_per_group=3):
    lines = text.split("\n")
    counts = [0] * len(SYNONYM_GROUPS)
    for i, line in enumerate(lines):
        for gi, group in enumerate(SYNONYM_GROUPS):
            if counts[gi] >= max_per_group:
                continue
            for term in sorted(group, key=len, reverse=True):
                if term in line:
                    new = line.replace(term, term + "（同义：" + "、".join(group) + "）", 1)
                    if new != line:
                        counts[gi] += 1
                        lines[i] = new
                    break
    return "\n".join(lines)


# ================= 切块 =================
DUP_PAREN = re.compile(r"(（[^（）]{2,20}）)\1+")


def clean(text):
    """统一换行；顺带折叠完全相邻重复的括号（源文件与同义词注入会叠加出这类噪声）"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    prev = None
    while prev != text:
        prev = text
        text = DUP_PAREN.sub(r"\1", text)
    return text


QA_SPLIT = re.compile(r"(?=^问[：:])", re.MULTILINE)


def split_blocks(text):
    """按空行 / markdown 标题 / 编号 / 【小节】 / 问答对切成语义块，标题作为块首。

    Q&A 文档（"问：xxx\\n答：yyy"）每对独立成块，不被 chunk_text 合并，
    保证检索命中的是完整的"问+答"上下文。
    """
    blocks, cur = [], []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            if cur:
                blocks.append("\n".join(cur))
            cur = []
            continue
        if re.match(r"^#{1,6}\s", s) or re.match(r"^【[^】]+】$", s) \
                or re.match(r"^\d+[\.、]\s", s) or re.match(r"^\*\*(?:\d+|[一二三四五六七八九十]+)[.、]",
                                                                s) \
                or re.match(r"^问[：:]", s):
            if cur:
                blocks.append("\n".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        blocks.append("\n".join(cur))

    # 对每个块再按 "问：" 拆成单对问答；QA 块长度天然远小于 T_MAX，不会被 split_long 硬切
    out = []
    for b in blocks:
        if re.search(r"^问[：:]", b, re.MULTILINE):
            # 标记 Q&A 块：每个问答对独立成块，合并阶段不再合并
            for qa in QA_SPLIT.split(b):
                qa = qa.strip()
                if qa:
                    out.append(qa + "\n[QA_KEEP]")
        else:
            out.append(b)
    return [b.strip() for b in out if b.strip()]


SENT_END = re.compile(r"(?<=[。！？；!?;])")


def split_long(block, limit=T_MAX):
    """超长块按句末标点切分；单句仍超长则硬切"""
    parts = [p for p in SENT_END.split(block) if p.strip()] or [block]
    out, cur = [], ""
    for p in parts:
        while len(p) > limit:
            if cur:
                out.append(cur)
                cur = ""
            out.append(p[:limit])
            p = p[limit:]
        if not cur:
            cur = p
        elif len(cur) + len(p) <= limit:
            cur += p
        else:
            out.append(cur)
            cur = (cur[-OVERLAP:] + p) if OVERLAP < len(cur) else p
    if cur:
        out.append(cur)
    return [c for c in out if c.strip()]


def chunk_text(text):
    """切成 200~500 字语义块：相邻短块合并，超长块按句子拆分，块间保留 OVERLAP 重叠。

    标记 [QA_KEEP] 的 Q&A 块不参与合并，每个问答对独立成块。
    """
    raw = []
    for b in split_blocks(text):
        if b.endswith("[QA_KEEP]"):
            # Q&A 块通常远小于 T_MAX，无需走 split_long；直接保留
            raw.append(b)
        else:
            raw.extend(split_long(b))
    merged, cur = [], ""
    for b in raw:
        qa = b.endswith("[QA_KEEP]")
        if qa:
            if cur:
                merged.append(cur)
                cur = ""
            merged.append(b[:-len("[QA_KEEP]")].strip())
            continue
        if not cur:
            cur = b
        elif len(cur) < T_MIN and len(cur) + len(b) <= T_MAX:
            cur += b
        else:
            merged.append(cur)
            cur = b
    if cur:
        merged.append(cur)
    return merged


# ================= 向量化（必须与 App 端一致） =================
class CharTokenizer:
    """按单字符查表 —— 与 App 端 TokenEmbedder 行为一致，名字不要叫 BertTokenizer，误导"""

    def __init__(self, vocab_path):
        with open(vocab_path, encoding="utf-8") as f:
            self.vocab = {t.strip(): i for i, t in enumerate(f) if t.strip()}
        self.cls = self.vocab.get("[CLS]", 101)
        self.sep = self.vocab.get("[SEP]", 102)
        self.unk = self.vocab.get("[UNK]", 100)

    def encode(self, text):
        text = re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()
        ids = [self.vocab[c] if c in self.vocab else self.unk for c in text]
        return ids[: MAX_SEQ - 2]


def make_session(model_path):
    so = ort.SessionOptions()
    so.intra_op_num_threads = max(1, os.cpu_count() or 1)
    return ort.InferenceSession(model_path, sess_options=so,
                               providers=["CPUExecutionProvider"])


def run_batch(session, cls, sep, id_lists, seq_len):
    b = len(id_lists)
    a = np.zeros((b, seq_len), np.int64)
    m = np.zeros((b, seq_len), np.int64)
    tt = np.zeros((b, seq_len), np.int64)
    for r, ids in enumerate(id_lists):
        size = min(len(ids), MAX_SEQ - 2) + 2
        a[r, 0] = cls
        m[r, 0] = 1
        for i, v in enumerate(ids[: MAX_SEQ - 2]):
            a[r, i + 1] = v
            m[r, i + 1] = 1
        a[r, size - 1] = sep
        m[r, size - 1] = 1
    o = session.run(None, {"input_ids": a, "attention_mask": m, "token_type_ids": tt})[0]
    out = []
    for r in range(b):
        e = o[r][0].astype(np.float32).copy()
        n = np.linalg.norm(e)
        out.append(e / n if n > 0 else e)
    return out


def embed_all(session, tok, texts, batch=BATCH):
    """按 token 长度分桶 + 批量推理（ARM 单条要 2~3 秒，1600 块要 70 分钟；分桶后约 5 块/秒）"""
    ids = [tok.encode(t) for t in texts]
    order = sorted(range(len(texts)), key=lambda i: min(len(ids[i]) + 2, MAX_SEQ))
    emb = [None] * len(texts)
    done, st = 0, time.time()
    for i0 in range(0, len(order), batch):
        grp = order[i0: i0 + batch]
        sl = min(MAX_SEQ, max(len(ids[i]) + 2 for i in grp) + 8)
        sl = ((sl + 15) // 16) * 16
        vs = run_batch(session, tok.cls, tok.sep, [ids[i] for i in grp], sl)
        for k, i in enumerate(grp):
            emb[i] = vs[k]
        done += len(grp)
        if done % 240 == 0 or done == len(texts):
            el = max(time.time() - st, 1e-6)
            print("  [%d/%d] %.1f%%  %.1f 块/秒  剩余约 %.0f 秒"
                  % (done, len(texts), 100.0 * done / len(texts),
                     done / el, (len(texts) - done) / (done / el)), flush=True)
    return emb


# ================= 主流程 =================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-alias", action="store_true", help="不注入同义词（默认注入，与 v5 一致）")
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--out-dir", default=BASE_DIR)
    a = ap.parse_args()

    model = os.path.join(BASE_DIR, "model_qint8.onnx")
    vocab = os.path.join(BASE_DIR, "vocab.txt")
    for p in (model, vocab):
        if not os.path.exists(p):
            raise SystemExit("缺少 %s" % p)

    print("Loading model + vocab ...", flush=True)
    tok = CharTokenizer(vocab)
    session = make_session(model)

    print("Chunking documents ...", flush=True)
    rows = []
    for fname, doc_id in NAME_MAP:
        path = os.path.join(BASE_DIR, fname)
        if not os.path.exists(path):
            print("  !! 源文件缺失，跳过: %s" % fname, flush=True)
            continue
        text = io.open(path, encoding="utf-8-sig", errors="ignore").read()
        if not a.no_alias:
            text = add_synonyms(add_aliases(text))
        text = clean(text)
        cs = chunk_text(text)
        for i, c in enumerate(cs):
            rows.append((doc_id, i, c))
        lens = [len(c) for c in cs]
        print("  %-34s doc_id=%-7s %4d 块  平均 %3d 字  最大 %5d 字"
              % (fname, doc_id, len(cs), sum(lens) // max(1, len(lens)), max(lens or [0])),
              flush=True)

    if not rows:
        raise SystemExit("未生成任何块，已中止（不会覆盖现有库）")

    # 仅做精确去重；旧版的 O(n^2) near_dedup 会误删含同义词的相邻块，且耗时不可控
    seen, dedup = set(), []
    for r in rows:
        if r[2] not in seen:
            seen.add(r[2])
            dedup.append(r)
    if len(dedup) != len(rows):
        print("精确去重: %d -> %d" % (len(rows), len(dedup)), flush=True)
    rows = dedup

    print("Embedding %d chunks (char-level + CLS + L2) ..." % len(rows), flush=True)
    emb = embed_all(session, tok, [r[2] for r in rows], a.batch)

    # 版本号：kb_version.txt 是仓库内既有的计数器，workflow 会一并提交
    vfile = os.path.join(BASE_DIR, "kb_version.txt")
    version = 1
    if os.path.exists(vfile):
        try:
            version = int(io.open(vfile, encoding="utf-8").read().strip()) + 1
        except ValueError:
            version = 1
    with io.open(vfile, "w", encoding="utf-8") as f:
        f.write(str(version))

    out_db = os.path.join(a.out_dir, "knowledge_base.db")
    if os.path.exists(out_db):
        os.remove(out_db)
    con = sqlite3.connect(out_db)
    con.execute("""CREATE TABLE chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding BLOB
    )""")
    con.execute("CREATE INDEX idx_doc_id ON chunks(doc_id)")
    con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany(
        "INSERT INTO chunks (doc_id, chunk_index, content, embedding) VALUES (?,?,?,?)",
        [(d, i, c, struct.pack("<512f", *emb[k].astype(np.float32)))
         for k, (d, i, c) in enumerate(rows)])
    con.commit()
    con.close()

    # 与 v5 保持一致的约定：md5 取「写入 metadata 之前」的库文件字节
    with open(out_db, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()

    con = sqlite3.connect(out_db)
    con.executemany("INSERT OR REPLACE INTO metadata VALUES (?,?)",
                    [("version", str(version)), ("chunks", str(len(rows))), ("md5", md5)])
    con.commit()
    con.close()

    info = {"version": version, "chunks": len(rows), "md5": md5}
    with io.open(os.path.join(a.out_dir, "knowledge_base_version.json"), "w",
                 encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False, indent=2) + "\n")

    lens = [len(r[2]) for r in rows]
    print("\nDone! v%d, %d chunks -> %s (%.2f MB)"
          % (version, len(rows), out_db, os.path.getsize(out_db) / 1024 / 1024))
    print("  <50字 %d (%.1f%%)  平均 %d 字  最大 %d 字  200~500字 %.1f%%  md5=%s"
          % (sum(1 for l in lens if l < 50),
             100.0 * sum(1 for l in lens if l < 50) / len(lens),
             sum(lens) // len(lens), max(lens),
             100.0 * sum(1 for l in lens if T_MIN <= l <= T_MAX) / len(lens), md5),
          flush=True)


if __name__ == "__main__":
    main()