# 研究ワークスペース（自分専用RAG）

論文・資料を取り込んで、**自分の研究プロフィールに合わせてAIが答える** Notion風の研究管理アプリ。
Notionの汎用AIと違い、(1) あなたのライブラリだけを根拠に答え、(2) 分野・レベル・関心に合わせて回答を最適化する点が差別化です。

## できること
- PDF論文の取り込み（テキスト抽出 → チャンク分割 → ベクトルDB登録）
- ライブラリ管理（ステータス: 未読/読書中/読了、メモ、要約）
- ライブラリを根拠にした質問応答（出典つき、対象論文の限定も可）
- 進捗ダッシュボード ＋「次に読むべき論文」のAI提案
- 研究プロフィール（分野・サブトピック・レベル・関心・回答言語/スタイル）

## 構成
| ファイル | 役割 |
|---|---|
| `app.py` | Streamlit のUI |
| `rag.py` | PDF抽出・分割・ベクトル化・検索・Claude回答 |
| `db.py` | SQLite（論文・メモ・進捗・プロフィール） |
| `config.py` | モデル名・パス・各種設定 |

データは2層：**ベクトルDB(Chroma)** が「内容の検索」、**SQLite** が「何を読んだか/メモ」を担当します。

## セットアップ
```bash
pip install -r requirements.txt

# APIキーを設定（どちらか）
#  A) .streamlit/secrets.toml.example を secrets.toml にコピーしてキーを記入
#  B) アプリ起動後、サイドバーの「APIキー」に貼り付け

streamlit run app.py
```
初回起動時に多言語の埋め込みモデル（約400MB）が自動ダウンロードされます。

## 使い方
1. サイドバーで**研究プロフィール**を入力して保存（これがAIのチューニングに効きます）
2. 「ライブラリ」タブでPDFを取り込む
3. 「質問」タブでライブラリに質問（出典つきで回答）
4. 「進捗」タブで状況確認と次の論文提案

## Web公開（Streamlit Community Cloud）
GitHubに上げて Streamlit Cloud と連携すれば `https://〇〇.streamlit.app` で公開できます。注意点：
- **APIキーは絶対にコミットしない**。Cloud側の Secrets 設定に `ANTHROPIC_API_KEY` を登録する。
- Community Cloud の**ストレージは揮発性**で、再起動や再デプロイで `data/`（Chroma・SQLite）が消えます。
  継続的に貯めるなら、ベクトルを Qdrant Cloud 等、SQLiteを Supabase(Postgres) 等の外部に移すのが安全。
- 個人利用で「使うたびに論文を入れ直す」運用なら、そのままでも問題ありません。

## カスタマイズの入口
- 回答品質を上げる: `config.py` の `CLAUDE_MODEL` を `claude-opus-4-8` に
- 検索の精度: `TOP_K`、`CHUNK_SIZE`、`CHUNK_OVERLAP` を調整
- 日本語精度: `EMBED_MODEL` をより大きい多言語モデルに変更
