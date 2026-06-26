import os

# 回答生成に使う Claude モデル（コスパ重視で Sonnet）
# より高品質にしたいときは "claude-opus-4-8" に変更
CLAUDE_MODEL = "claude-sonnet-4-6"

# 埋め込みモデル（多言語=日本語論文+英語論文の両方に対応）
# 初回実行時に自動ダウンロードされます（約400MB）
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# 保存先（ローカル）
DATA_DIR = os.environ.get("RAG_DATA_DIR", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
DB_PATH = os.path.join(DATA_DIR, "research.db")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")

# チャンク分割
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# 検索で取得するチャンク数
TOP_K = 5

# 論文のステータス
STATUSES = ["未読", "読書中", "読了"]
LEVELS = ["学部生", "大学院生", "研究者", "その他"]
