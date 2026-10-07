#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地混合检索：向量（bge-small-zh-v1.5）+ BM25 + RRF 融合。

索引与检索对象是记忆库的正式分层（L0-portable、L1-L3、controlled-memory）以及可选的额外笔记库；
L0-raw 与各类缓存不参与，避免重复内容与 Token 膨胀。

Usage:
  python memory_search.py index [--rebuild]
  python memory_search.py search -q "query" [-k 8] [--mode hybrid|embedding|keyword]
"""

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

# 记忆库根目录：优先读环境变量 MEMORY_ROOT，默认 ~/ai-memory
MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path.home() / "ai-memory")))
# 可选：额外索引的 Markdown 根目录（例如个人笔记库）；留空则不索引
_vault_root = os.environ.get("MEMORY_VAULT_ROOT", "").strip()
VAULT_ROOT = Path(_vault_root) if _vault_root else None
# 索引数据库：默认放在记忆库内的 indexes/ 下；它只是可重建的缓存
DB_PATH = Path(os.environ.get("MEMORY_DB_PATH", str(MEMORY_ROOT / "indexes" / "index.sqlite")))
# 向量模型：MEMORY_EMBED_DIR 留空时按模型名联网下载
MODEL_NAME = os.environ.get("MEMORY_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
_embed_dir = os.environ.get("MEMORY_EMBED_DIR", "").strip()
LOCAL_MODEL_DIR = Path(_embed_dir) if _embed_dir else None
# bge 中文模型要求的检索前缀；换模型时按该模型文档调整
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
MAX_CHUNK_CHARS = 600
MAX_FILE_KB = 300


def collect_files():
    files = {}
    # 只索引正式可移植记忆层；L0-raw、旧 memory-bank 和缓存不进入日常上下文，避免重复与 Token 膨胀。
    layer_names = (
        "00-system", "L0-portable", "L1-facts", "L2-scenarios",
        "L2-projects", "L2-skills", "L3-profile", "controlled-memory",
    )
    roots = [MEMORY_ROOT / name for name in layer_names if (MEMORY_ROOT / name).exists()]
    if VAULT_ROOT is not None and VAULT_ROOT.exists():
        roots.append(VAULT_ROOT)
    for root in roots:
        patterns = ("*.md", "*.jsonl") if root.name == "L0-portable" else ("*.md",)
        for pattern in patterns:
            for p in root.rglob(pattern):
                if any(part.startswith(".") for part in p.parts):
                    continue
                try:
                    mtime = p.stat().st_mtime
                    size = p.stat().st_size
                except OSError:
                    continue
                if size > MAX_FILE_KB * 1024:
                    continue
                files[str(p)] = mtime
    return files


def read_index_chunks(path):
    """读取 Markdown 或 L0-portable JSONL，统一转换成可向量化的文本块。"""
    if path.suffix.lower() != ".jsonl":
        text = path.read_text(encoding="utf-8", errors="replace")
        return chunk_markdown(text)

    chunks = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        role = str(item.get("role") or "message")
        session_id = str(item.get("session_id") or path.stem)
        heading = f"L0 {role} {session_id} line {line_no}"
        chunks.extend(chunk_markdown(f"## {heading}\n{content}"))
    return chunks


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def chunk_markdown(text):
    text = strip_frontmatter(text)
    lines = text.splitlines()
    chunks = []
    cur = []
    cur_heading = ""

    def flush():
        nonlocal cur
        body = "\n".join(cur).strip()
        cur = []
        if not body:
            return
        if len(body) > MAX_CHUNK_CHARS * 2:
            paras = re.split(r"\n\s*\n", body)
            piece = ""
            for para in paras:
                if len(piece) + len(para) + 1 > MAX_CHUNK_CHARS and piece:
                    chunks.append((cur_heading, piece.strip()))
                    piece = ""
                piece += para + "\n"
            if piece.strip():
                chunks.append((cur_heading, piece.strip()))
        else:
            chunks.append((cur_heading, body))

    for line in lines:
        if re.match(r"^#{1,6}\s", line):
            flush()
            cur_heading = re.sub(r"^#+\s*", "", line).strip()
        else:
            cur.append(line)
    flush()
    return chunks


def load_model():
    # 优先用本地模型目录（离线/内网）；未配置时交给 sentence-transformers 按模型名下载
    from sentence_transformers import SentenceTransformer
    use_local = LOCAL_MODEL_DIR is not None and LOCAL_MODEL_DIR.exists()
    return SentenceTransformer(str(LOCAL_MODEL_DIR) if use_local else MODEL_NAME, device="cpu")


def _tokenize(text):
    """CJK 用字符二元组 + 单字，ASCII 用单词；无 jieba 依赖。"""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    tokens += [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    tokens += cjk
    return tokens


def _bm25_scores(docs, query_tokens, k1=1.5, b=0.75):
    n = len(docs)
    df = {}
    for doc in docs:
        for t in set(doc):
            df[t] = df.get(t, 0) + 1
    avgdl = sum(len(d) for d in docs) / n if n else 0.0
    scores = []
    for doc in docs:
        dl = len(doc)
        tf = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in query_tokens:
            if t not in df:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            tfd = tf.get(t, 0)
            s += idf * (tfd * (k1 + 1)) / (tfd + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


def _rrf(*score_lists, k=60):
    """Reciprocal Rank Fusion：每个排序器的分数转排名后融合。"""
    ranks = []
    for scores in score_lists:
        arr = np.asarray(scores, dtype=np.float64)
        ranks.append(np.argsort(np.argsort(-arr)))
    fused = np.zeros(len(ranks[0]), dtype=np.float64)
    for r in ranks:
        fused += 1.0 / (k + r + 1)
    return fused


def cmd_index(args):
    files = collect_files()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "path TEXT, mtime REAL, heading TEXT, text TEXT, emb BLOB)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON chunks(path)")
    conn.commit()

    existing = {}
    for row in conn.execute("SELECT path, mtime FROM chunks GROUP BY path"):
        existing[row[0]] = row[1]

    if args.rebuild:
        conn.execute("DELETE FROM chunks")
        conn.commit()
    else:
        gone = set(existing) - set(files)
        for g in gone:
            conn.execute("DELETE FROM chunks WHERE path=?", (g,))
        conn.commit()

    changed = [
        p for p, m in files.items()
        if args.rebuild or p not in existing or abs(existing[p] - m) > 1e-6
    ]
    if not changed:
        total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        print(f"INDEX_UP_TO_DATE files={len(files)} chunks={total}")
        return

    model = load_model()
    texts_all = []
    meta_all = []
    for path in changed:
        try:
            source_path = Path(path)
            chunks = read_index_chunks(source_path)
        except OSError:
            continue
        for heading, body in chunks:
            texts_all.append(body)
            meta_all.append((path, files[path], heading, body))

    t0 = time.time()
    BATCH = 64
    rows = []
    for i in range(0, len(texts_all), BATCH):
        batch = texts_all[i:i + BATCH]
        embs = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        for j, emb in enumerate(embs):
            path, mtime, heading, body = meta_all[i + j]
            rows.append((path, mtime, heading, body, np.asarray(emb, dtype=np.float32).tobytes()))
        conn.executemany(
            "INSERT INTO chunks(path, mtime, heading, text, emb) VALUES(?,?,?,?,?)",
            rows,
        )
        conn.commit()
        rows.clear()

    total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(
        f"INDEX_OK files={len(changed)} chunks={len(texts_all)} "
        f"seconds={time.time() - t0:.1f} total_files={len(files)} total_chunks={total}"
    )


def cmd_search(args):
    if not DB_PATH.exists():
        print("INDEX_NOT_FOUND: run `python memory_search.py index` first")
        sys.exit(2)
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT path, heading, text, emb FROM chunks").fetchall()
    if not rows:
        print("INDEX_EMPTY: run `python memory_search.py index` first")
        sys.exit(2)

    model = load_model()
    qv = model.encode(
        [QUERY_PREFIX + args.query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0].astype(np.float32)

    matrix = np.stack([np.frombuffer(r[3], dtype=np.float32) for r in rows])
    emb_scores = matrix @ qv

    if args.mode == "embedding":
        final = emb_scores
    elif args.mode == "keyword":
        docs = [_tokenize(r[2]) for r in rows]
        qtoks = _tokenize(args.query)
        final = np.asarray(_bm25_scores(docs, qtoks), dtype=np.float64)
    else:
        docs = [_tokenize(r[2]) for r in rows]
        qtoks = _tokenize(args.query)
        kw_scores = np.asarray(_bm25_scores(docs, qtoks), dtype=np.float64)
        final = _rrf(emb_scores, kw_scores)

    order = np.argsort(-final)[: args.top]

    print(f"QUERY: {args.query} (mode={args.mode})")
    for idx in order:
        path, heading, text, _ = rows[idx]
        snip = re.sub(r"\s+", " ", text).strip()
        if len(snip) > 120:
            snip = snip[:120] + "..."
        print(f"[{final[idx]:.4f}] {path} :: {heading or '-'} :: {snip}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Local semantic search (bge-small-zh-v1.5)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="build / update the local index")
    p_index.add_argument("--rebuild", action="store_true", help="rebuild from scratch")
    p_index.set_defaults(func=cmd_index)

    p_search = sub.add_parser("search", help="semantic search")
    p_search.add_argument("-q", "--query", required=True)
    p_search.add_argument("-k", "--top", type=int, default=8)
    p_search.add_argument(
        "--mode",
        choices=["hybrid", "embedding", "keyword"],
        default="hybrid",
    )
    p_search.set_defaults(func=cmd_search)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
