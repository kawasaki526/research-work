import os

import streamlit as st

import config
import db
import rag

st.set_page_config(page_title="研究ワークスペース", layout="wide")
db.init_db()


def get_api_key():
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None
    if not key:
        key = st.session_state.get("api_key")
    return key


# ---------------- サイドバー: APIキー + 研究プロフィール ----------------
with st.sidebar:
    st.header("設定")

    with st.expander("APIキー", expanded=not get_api_key()):
        entered = st.text_input("Groq API Key", type="password", value="")
        if entered:
            st.session_state["api_key"] = entered
            st.success("キーを設定しました")
        st.caption("secrets.toml に書いておけば毎回入力不要です。")

    st.divider()
    st.subheader("研究プロフィール")
    st.caption("ここがNotionとの差別化。AIがあなた仕様で答えます。")

    prof = db.get_profile()
    field = st.text_input("専門分野", prof.get("field", ""))
    subtopics = st.text_input("サブトピック", prof.get("subtopics", ""))
    cur_level = prof.get("level", "大学院生")
    level = st.selectbox(
        "レベル", config.LEVELS,
        index=config.LEVELS.index(cur_level) if cur_level in config.LEVELS else 1,
    )
    focus = st.text_area("現在の関心 / 取り組み", prof.get("focus", ""), height=80)
    answer_lang = st.selectbox(
        "回答言語", ["日本語", "English"],
        index=0 if prof.get("answer_lang", "日本語") == "日本語" else 1,
    )
    answer_style = st.text_input("回答スタイル", prof.get("answer_style", "簡潔に、要点から先に"))

    if st.button("プロフィールを保存", use_container_width=True):
        db.save_profile(field, subtopics, level, focus, answer_lang, answer_style)
        st.success("保存しました")


# ---------------- メイン ----------------
st.title("研究ワークスペース")
st.caption("自分専用のNotion風RAG。ライブラリの論文だけを根拠に、あなた仕様で答えます。")

tab_lib, tab_chat, tab_progress = st.tabs(["ライブラリ", "質問", "進捗"])


# ===== ライブラリ =====
with tab_lib:
    with st.expander("論文を追加 (PDF)", expanded=False):
        up = st.file_uploader("PDFをアップロード", type=["pdf"])
        title_in = st.text_input("タイトル（空ならファイル名）", key="add_title")
        authors_in = st.text_input("著者", key="add_authors")
        year_in = st.text_input("年", key="add_year")
        summary_in = st.text_area("メモ/要約（任意）", key="add_summary", height=60)
        if st.button("取り込む", type="primary"):
            if not up:
                st.error("PDFを選択してください")
            else:
                os.makedirs(config.PDF_DIR, exist_ok=True)
                path = os.path.join(config.PDF_DIR, up.name)
                with open(path, "wb") as f:
                    f.write(up.getbuffer())
                title = title_in.strip() or os.path.splitext(up.name)[0]
                with st.spinner("テキスト抽出とベクトル化中..."):
                    text = rag.extract_pdf_text(path)
                    pid = db.add_paper(title, authors_in, year_in, summary_in, up.name, 0)
                    n = rag.ingest_paper(pid, title, text)
                    db.update_paper_fields(pid, n_chunks=n)
                st.success(f"「{title}」を取り込みました（{n}チャンク）")
                st.rerun()

    flt = st.selectbox("ステータスで絞り込み", ["すべて"] + config.STATUSES, key="lib_filter")
    papers = db.list_papers(flt)
    if not papers:
        st.info("まだ論文がありません。上の「論文を追加」から取り込んでください。")

    for p in papers:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{p['title']}**")
                meta = " / ".join(x for x in [p.get("authors"), p.get("year")] if x)
                if meta:
                    st.caption(meta)
                if p.get("summary"):
                    st.caption(p["summary"])
            with c2:
                idx = config.STATUSES.index(p["status"]) if p["status"] in config.STATUSES else 0
                new_status = st.selectbox(
                    "状態", config.STATUSES, index=idx,
                    key=f"st_{p['id']}", label_visibility="collapsed",
                )
                if new_status != p["status"]:
                    db.update_paper_fields(p["id"], status=new_status)
                    st.rerun()

            notes = st.text_area("メモ", p.get("notes") or "", key=f"note_{p['id']}", height=70)
            cc1, cc2, _ = st.columns([1, 1, 3])
            with cc1:
                if st.button("メモを保存", key=f"save_{p['id']}"):
                    db.update_paper_fields(p["id"], notes=notes)
                    st.toast("保存しました")
            with cc2:
                if st.button("削除", key=f"del_{p['id']}"):
                    rag.remove_paper(p["id"])
                    db.delete_paper(p["id"])
                    st.rerun()


# ===== 質問 =====
with tab_chat:
    papers = db.list_papers()
    if not papers:
        st.info("先にライブラリへ論文を取り込んでください。")
    else:
        options = {p["title"]: p["id"] for p in papers}
        scope = st.multiselect("対象論文を限定（空ならライブラリ全体）", list(options.keys()))
        q = st.text_input("質問", placeholder="例: この論文の提案手法の新規性は？")
        if st.button("質問する", type="primary") and q:
            key = get_api_key()
            if not key:
                st.error("APIキーを設定してください（サイドバー）")
            else:
                paper_ids = [options[s] for s in scope] if scope else None
                with st.spinner("ライブラリを検索して回答を生成中..."):
                    result = rag.answer(
                        q, db.get_profile(), paper_ids=paper_ids, api_key=key
                    )
                st.markdown(result["text"])
                if result["sources"]:
                    st.caption("参照: " + " ・ ".join(result["sources"]))


# ===== 進捗 =====
with tab_progress:
    counts = db.counts_by_status()
    total = sum(counts.values())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("合計", total)
    m2.metric("未読", counts.get("未読", 0))
    m3.metric("読書中", counts.get("読書中", 0))
    m4.metric("読了", counts.get("読了", 0))

    st.divider()
    st.subheader("次に読むべき論文")
    st.caption("プロフィールの関心とライブラリの状況から提案します。")
    if st.button("提案してもらう"):
        key = get_api_key()
        if not key:
            st.error("APIキーを設定してください")
        else:
            with st.spinner("提案を生成中..."):
                st.markdown(rag.suggest_next(db.get_profile(), db.list_papers(), api_key=key))
