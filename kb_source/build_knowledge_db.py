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


class BertTokenizer:
    """Simple BERT WordPiece tokenizer based on vocab.txt"""

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


def split_subsections(text, doc_type):
    """
    Split document by subsection boundaries.
    - 'theory': split on `## ` (markdown H2 = each section)
    - 'manual': split on numbered headings like `X.X.X` or `X.X.X.X`
    - 'rules': split on `**N.**` (already correct)
    """
    if doc_type == "rules":
        items = [r.strip() for r in re.split(r'(?=^\*\*\d+\.\*\*)', text, flags=re.MULTILINE) if r.strip()]
        return items
    elif doc_type == "theory":
        parts = re.split(r'(?=^## )', text, flags=re.MULTILINE)
        return [p.strip() for p in parts if p.strip()]
    elif doc_type == "manual":
        parts = re.split(r'(?=^\d+\.\d+\.\d+(?:\.\d+)*)', text, flags=re.MULTILINE)
        return [p.strip() for p in parts if p.strip()]
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
        ("水质理论篇.md", "theory"),
        ("小棚实操手册.md", "manual"),
        ("操作规则302条.md", "rules"),
    ]
    for fname, doc_id in name_map:
        path = BASE_DIR / fname
        if not path.exists():
            print(f"  Skip: {fname} (not found)")
            continue

        text = path.read_text(encoding='utf-8-sig')

        chunks = split_subsections(text, doc_id)
        start = len(all_chunks)
        for i, ch in enumerate(chunks):
            all_chunks.append((doc_id, i, ch))
        print(f"  {path.name}: {len(all_chunks) - start} chunks")

    if not all_chunks:
        print("No chunks generated. Check if input files exist.")
        print("Expected files: 水质理论篇.md, 小棚实操手册.md, 操作规则302条.md")
        return

    print(f"\nTotal: {len(all_chunks)} chunks, generating embeddings...")

    embeddings = []
    total = len(all_chunks)
    for i, (_, _, content) in enumerate(all_chunks):
        emb = get_embedding(session, tokenizer, content)
        embeddings.append(emb)
        if (i + 1) % 50 == 0 or i == total - 1:
            print(f"  [{i+1}/{total}]")

    # Version tracking
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

    # Compute md5
    conn.commit()
    conn.close()
    md5_hash = hashlib.md5(out_path.read_bytes()).hexdigest()

    # Store version info in DB
    conn = sqlite3.connect(str(out_path))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("version", str(current_version)))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("chunks", str(len(all_chunks))))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", ("md5", md5_hash))
    conn.commit()
    conn.close()

    # Output version.json for TIMU
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
