"""RAG レイヤー。
PDF からテキストを取り出し、チャンク分割してベクトルDB(Chroma)に保存し、
質問時に関連チャンクを検索して、研究プロフィールを反映した Gemini の回答を返す。
"""
import os
import re

import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions
import google.generativeai as genai

import config

_client = None
_collection = None


def _get_collection():
    """Chroma コレクションを遅延初期化（埋め込みモデルは多言語）。"""
    global _client, _collection
    if _collection is None:
        os.makedirs(config.CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=config.EMBED_MODEL
        )
        _collection = _client.get_or_create_collection(
            name="papers", embedding_function=ef
        )
    return _collection


def extract_pdf_text(path):
    doc = fitz.open(path)
    parts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(parts)


def chunk_text(text, size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP):
    """文字数ベースの重なりつき分割（日本語・英語どちらでも素直に効く）。"""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap
    return chunks


def ingest_paper(paper_id, title, text):
    """1本の論文をチャンク化してベクトルDBに登録。チャンク数を返す。"""
    collection = _get_collection()
    chunks = chunk_text(text)
    if not chunks:
        return 0
    ids = [f"{paper_id}-{i}" for i in range(len(chunks))]
    metadatas = [
        {"paper_id": paper_id, "title": title, "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


def remove_paper(paper_id):
    collection = _get_collection()
    collection.delete(where={"paper_id": paper_id})


def retrieve(question, k=config.TOP_K, paper_ids=None):
    collection = _get_collection()
    where = {"paper_id": {"$in": paper_ids}} if paper_ids else None
    res = collection.query(query_texts=[question], n_results=k, where=where)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    out = []
    for doc, meta in zip(docs, metas):
        out.append({
            "text": doc,
            "title": meta.get("title", "?"),
            "paper_id": meta.get("paper_id"),
        })
    return out


def _build_system_prompt(profile):
    field = profile.get("field") or "（未設定）"
    subtopics = profile.get("subtopics") or "（未設定）"
    level = profile.get("level") or "大学院生"
    focus = profile.get("focus") or "（未設定）"
    lang = profile.get("answer_lang") or "日本語"
    style = profile.get("answer_style") or "簡潔に"
    return f"""あなたは利用者専用の研究アシスタントです。利用者の研究プロフィールに合わせて回答を最適化してください。

# 利用者プロフィール
- 専門分野: {field}
- サブトピック: {subtopics}
- レベル: {level}
- 現在の関心: {focus}

# 回答ルール
- 回答は必ず {lang} で行う。
- スタイル: {style}
- 提供された「参考文献」の内容だけを根拠にすること。推測で補わない。
- 根拠にした箇所には [論文タイトル] の形式で出典を示す。
- 参考文献に答えがない場合は、その旨を正直に伝える。
- 利用者のレベルに合わせ、前提知識を省きすぎず、冗長にもしない。"""


def answer(question, profile, k=config.TOP_K, paper_ids=None, api_key=None):
    """ライブラリを検索し、プロフィールを反映した回答と参照論文を返す。"""
    chunks = retrieve(question, k=k, paper_ids=paper_ids)
    if not chunks:
        return {
            "text": "ライブラリに関連する記述が見つかりませんでした。先に論文を取り込んでください。",
            "sources": [],
        }
    context = "\n\n".join(f"[{c['title']}]\n{c['text']}" for c in chunks)
    system = _build_system_prompt(profile)
    user_msg = f"# 質問\n{question}\n\n# 参考文献（あなたのライブラリから抽出）\n{context}"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=system,
    )
    resp = model.generate_content(user_msg)
    text = resp.text

    sources = []
    for c in chunks:
        if c["title"] not in sources:
            sources.append(c["title"])
    return {"text": text, "sources": sources}


def suggest_next(profile, papers, api_key=None):
    """プロフィールとライブラリから「次に読むべき論文」を提案。"""
    if not papers:
        return "まだ論文がありません。"
    lib = "\n".join(
        f"- {p['title']}（{p['status']}）"
        + (f" / {p['summary']}" if p.get("summary") else "")
        for p in papers
    )
    field = profile.get("field") or ""
    focus = profile.get("focus") or ""
    system = "あなたは利用者専用の研究アシスタントです。"
    user_msg = f"""利用者の分野: {field}
現在の関心: {focus}

以下はライブラリの論文一覧です:
{lib}

この中から、次に読むべき未読/読書中の論文を、関心との関連が高い順に最大3件挙げ、
それぞれ1行で理由を添えてください。日本語で簡潔に。"""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=system,
    )
    resp = model.generate_content(user_msg)
    return resp.text
