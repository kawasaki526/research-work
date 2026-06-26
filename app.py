import os
from datetime import date

import streamlit as st
from groq import Groq

import config
import db
import rag

st.set_page_config(page_title="研究ワークスペース", page_icon=None, layout="wide", initial_sidebar_state="expanded")
db.init_db()

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stHeader"] {visibility: hidden; height: 0; min-height: 0;}
[data-testid="stSidebarCollapsedControl"] {visibility: visible !important; height: auto !important;}
[data-testid="stSidebarNavToggleButton"] {visibility: visible !important;}

h1 { font-weight: 700; letter-spacing: -0.5px; }

.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 2px solid #E2E8F0;
}
.stTabs [data-baseweb="tab"] {
    font-weight: 500;
    padding: 8px 20px;
    border-radius: 6px 6px 0 0;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px;
    border: 1px solid #E2E8F0;
}

.stButton > button {
    border-radius: 6px;
    font-weight: 500;
}

button[data-testid="baseButton-secondary"] {
    min-height: 26px !important;
    height: 26px !important;
    padding: 0 4px !important;
    font-size: 0.8em !important;
    line-height: 1 !important;
}

[data-testid="stMetric"] {
    border-radius: 10px;
    padding: 12px;
    border: 1px solid #E2E8F0;
}
</style>
""", unsafe_allow_html=True)


def get_api_key():
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None
    if not key:
        key = st.session_state.get("api_key")
    return key


STATUS_COLORS = {"未着手": "#94A3B8", "進行中": "#3B82F6", "完了": "#22C55E"}


def chat_system_prompt():
    prof = db.get_profile()
    field = prof.get("field") or "（未設定）"
    subtopics = prof.get("subtopics") or "（未設定）"
    level = prof.get("level") or "大学院生"
    focus = prof.get("focus") or "（未設定）"
    lang = prof.get("answer_lang") or "日本語"
    style = prof.get("answer_style") or "簡潔に"
    return f"""あなたは利用者専用の研究アシスタントです。利用者の研究プロフィールをもとに、研究全般について助言・議論・質問への回答を行います。

# 利用者プロフィール
- 専門分野: {field}
- サブトピック: {subtopics}
- レベル: {level}
- 現在の関心: {focus}

# 回答ルール
- 回答は必ず {lang} で行う。
- スタイル: {style}
- 利用者のレベルに合わせた説明をする。
- 論文ライブラリへのアクセスはないため、一般的な知識をもとに答える。"""


# ---------------- サイドバー ----------------
if "prof_loaded" not in st.session_state:
    _prof = db.get_profile()
    st.session_state.prof_field    = _prof.get("field", "")
    st.session_state.prof_sub      = _prof.get("subtopics", "")
    st.session_state.prof_level    = _prof.get("level", "大学院生")
    st.session_state.prof_focus    = _prof.get("focus", "")
    st.session_state.prof_lang     = _prof.get("answer_lang", "日本語")
    st.session_state.prof_style    = _prof.get("answer_style", "簡潔に、要点から先に")
    st.session_state.prof_loaded   = True

with st.sidebar:
    st.subheader("研究プロフィール")

    field        = st.text_input("専門分野", key="prof_field")
    subtopics    = st.text_input("サブトピック", key="prof_sub")
    level        = st.selectbox(
        "レベル", config.LEVELS,
        index=config.LEVELS.index(st.session_state.prof_level)
              if st.session_state.prof_level in config.LEVELS else 1,
        key="prof_level",
    )
    focus        = st.text_area("現在の関心 / 取り組み", key="prof_focus", height=80)
    answer_lang  = st.selectbox(
        "回答言語", ["日本語", "English"],
        index=0 if st.session_state.prof_lang == "日本語" else 1,
        key="prof_lang",
    )
    answer_style = st.text_input("回答スタイル", key="prof_style")

    if st.button("プロフィールを保存", use_container_width=True):
        db.save_profile(field, subtopics, level, focus, answer_lang, answer_style)
        st.success("保存しました")


# ---------------- メイン ----------------
if "chat_open" not in st.session_state:
    st.session_state.chat_open = True

hd_left, hd_right = st.columns([3, 2])
with hd_left:
    st.title("研究ワークスペース")
    with st.expander("このアプリの使い方", expanded=False):
        st.markdown("""
**研究ワークスペース**は、自分でアップロードした論文PDFだけを根拠にAIが答える、個人用の研究管理ツールです。

#### 基本的な流れ
1. **サイドバーで研究プロフィールを入力・保存**
   専門分野・関心・レベルを設定すると、AIがあなた向けに回答を最適化します。

2. **「論文」タブでPDFを取り込む**
   論文PDFをアップロードするだけで、AIが内容を読み込みます。
   タイトル・著者・年・メモを記録でき、読書状況（未読／読書中／読了）も管理できます。
   取り込んだ論文に対して質問することもできます。

3. **「タスク」タブで研究タスクを管理する**
   締切・優先度つきのTODOリストで研究の進捗を管理できます。

4. **「メモ」タブでアイデアや気づきを記録する**
   自由形式のメモを作成・編集できます。

5. **「資料」タブでファイルを整理する**
   論文以外の資料（スライド・画像・ノートなど）をカテゴリ別にアップロード・管理できます。

6. **右側のチャットで研究について相談する**
   研究プロフィールを踏まえた研究特化チャットです。

#### 注意事項
- アップロードしたファイルとデータはサーバー上に保存されますが、再デプロイ時に消える場合があります。
- 論文への質問はライブラリ内の文献のみを根拠とします。
""")
    if not st.session_state.chat_open:
        st.write("")
        if st.button("チャットを開く"):
            st.session_state.chat_open = True
            st.rerun()

with hd_right:
    today = date.today()
    st.markdown("<div style='font-weight:700;font-size:0.95em;margin-bottom:6px;'>直近のタスク</div>", unsafe_allow_html=True)
    upcoming = sorted(
        [t for t in db.list_tasks() if t.get("due_date") and t["status"] != "完了"],
        key=lambda t: t["due_date"],
    )
    no_due = [t for t in db.list_tasks() if not t.get("due_date") and t["status"] != "完了"]
    display_tasks = upcoming + no_due
    if not display_tasks:
        st.caption("タスクがありません")
    for t in display_tasks:
        sc = STATUS_COLORS.get(t["status"], "#94A3B8")
        pc = {"高": "#EF4444", "中": "#F59E0B", "低": "#94A3B8"}.get(t["priority"], "#94A3B8")
        due = t.get("due_date", "")
        overdue = due and due < today.isoformat() and t["status"] != "完了"
        due_color = "#EF4444" if overdue else "#64748B"
        due_label = f"<span style='color:{due_color};font-size:0.75em;'>{due}</span>" if due else ""
        st.markdown(
            f"<div style='padding:5px 8px;border-left:3px solid {sc};margin:3px 0;"
            f"background:#F8FAFC;border-radius:0 6px 6px 0;font-size:0.82em;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<span style='font-weight:600;'>{t['title']}</span>"
            f"<span style='background:{pc};color:white;padding:1px 5px;border-radius:3px;font-size:0.72em;'>{t['priority']}</span>"
            f"</div>{due_label}</div>",
            unsafe_allow_html=True,
        )

if st.session_state.chat_open:
    col_main, col_chat = st.columns([3, 2])
else:
    col_main = st.container()
    col_chat = None

# ================== 左カラム: タブ ==================
with col_main:
    tab_lib, tab_task, tab_memo, tab_material, tab_works = st.tabs(["論文", "タスク", "メモ", "資料", "製作物"])

    # ===== 論文 =====
    with tab_lib:
        counts = db.counts_by_status()
        total = sum(counts.values())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("合計", total)
        m2.metric("未読", counts.get("未読", 0))
        m3.metric("読書中", counts.get("読書中", 0))
        m4.metric("読了", counts.get("読了", 0))
        if total > 0:
            done = counts.get("読了", 0)
            st.progress(done / total, text=f"読了率 {done}/{total}")

        st.divider()
        st.subheader("質問")
        papers_all = db.list_papers()
        if not papers_all:
            st.info("先に論文を取り込んでください。")
        else:
            options = {p["title"]: p["id"] for p in papers_all}
            scope = st.multiselect("対象論文を限定（空なら全体）", list(options.keys()))
            q = st.text_input("質問", placeholder="例: この論文の提案手法の新規性は？")
            if st.button("質問する", type="primary") and q:
                key = get_api_key()
                if not key:
                    st.error("APIキーを設定してください（サイドバー）")
                else:
                    paper_ids = [options[s] for s in scope] if scope else None
                    with st.spinner("検索して回答を生成中..."):
                        result = rag.answer(
                            q, db.get_profile(), paper_ids=paper_ids, api_key=key
                        )
                    st.markdown(result["text"])
                    if result["sources"]:
                        st.caption("参照: " + " ・ ".join(result["sources"]))

        st.divider()
        st.subheader("次に読むべき論文")
        if st.button("提案してもらう"):
            key = get_api_key()
            if not key:
                st.error("APIキーを設定してください")
            else:
                with st.spinner("提案を生成中..."):
                    st.markdown(rag.suggest_next(db.get_profile(), db.list_papers(), api_key=key))

        st.divider()
        st.subheader("論文一覧")
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
                    badge_color = {"未読": "#94A3B8", "読書中": "#3B82F6", "読了": "#22C55E"}.get(p["status"], "#94A3B8")
                    st.markdown(
                        f"**{p['title']}** "
                        f"<span style='background:{badge_color};color:white;padding:2px 8px;"
                        f"border-radius:4px;font-size:0.75em;'>{p['status']}</span>",
                        unsafe_allow_html=True,
                    )
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

    # ===== タスク =====
    with tab_task:
        with st.expander("タスクを追加", expanded=False):
            t_title = st.text_input("タスク名", key="t_title")
            t_detail = st.text_area("詳細（任意）", key="t_detail", height=60)
            tc1, tc2 = st.columns(2)
            with tc1:
                t_due = st.date_input("締切（任意）", value=None, key="t_due")
            with tc2:
                t_priority = st.selectbox("優先度", db.TASK_PRIORITIES, index=1, key="t_priority")
            if st.button("追加", type="primary", key="t_add"):
                if not t_title.strip():
                    st.error("タスク名を入力してください")
                else:
                    due_str = t_due.isoformat() if t_due else ""
                    db.add_task(t_title.strip(), t_detail.strip(), due_str, t_priority)
                    st.rerun()

        flt_t = st.selectbox("絞り込み", ["すべて"] + db.TASK_STATUSES, key="task_filter")
        tasks = db.list_tasks(flt_t)
        if not tasks:
            st.info("タスクがありません。")

        for t in tasks:
            with st.container(border=True):
                h1, h2, h3 = st.columns([3, 1, 1])
                with h1:
                    st.markdown(f"**{t['title']}**")
                    if t.get("detail"):
                        st.caption(t["detail"])
                    if t.get("due_date"):
                        st.caption(f"締切: {t['due_date']}")
                with h2:
                    p_color = {"高": "#EF4444", "中": "#F59E0B", "低": "#6B7280"}.get(t["priority"], "#6B7280")
                    st.markdown(
                        f"<span style='background:{p_color};color:white;padding:2px 8px;"
                        f"border-radius:4px;font-size:0.75em;'>{t['priority']}</span>",
                        unsafe_allow_html=True,
                    )
                with h3:
                    st_color = {"未着手": "#94A3B8", "進行中": "#3B82F6", "完了": "#22C55E"}.get(t["status"], "#94A3B8")
                    st.markdown(
                        f"<span style='background:{st_color};color:white;padding:2px 8px;"
                        f"border-radius:4px;font-size:0.75em;'>{t['status']}</span>",
                        unsafe_allow_html=True,
                    )
                    idx = db.TASK_STATUSES.index(t["status"]) if t["status"] in db.TASK_STATUSES else 0
                    new_st = st.selectbox(
                        "状態", db.TASK_STATUSES, index=idx,
                        key=f"tst_{t['id']}", label_visibility="collapsed",
                    )
                    if new_st != t["status"]:
                        db.update_task(t["id"], status=new_st)
                        st.rerun()

                if st.button("削除", key=f"tdel_{t['id']}"):
                    db.delete_task(t["id"])
                    st.rerun()

    # ===== メモ =====
    with tab_memo:
        with st.expander("メモを作成", expanded=False):
            m_title = st.text_input("タイトル", key="m_title")
            m_content = st.text_area("内容", key="m_content", height=150)
            if st.button("作成", type="primary", key="m_add"):
                if not m_title.strip():
                    st.error("タイトルを入力してください")
                else:
                    db.add_memo(m_title.strip(), m_content.strip())
                    st.rerun()

        memos = db.list_memos()
        if not memos:
            st.info("メモがありません。")

        for m in memos:
            with st.container(border=True):
                st.markdown(f"**{m['title']}**")
                st.caption(f"更新: {m['updated_at']}")
                new_content = st.text_area(
                    "内容", m.get("content") or "", key=f"mc_{m['id']}", height=100
                )
                new_title = st.text_input("タイトル", m["title"], key=f"mt_{m['id']}")
                mc1, mc2, _ = st.columns([1, 1, 3])
                with mc1:
                    if st.button("保存", key=f"msave_{m['id']}"):
                        db.update_memo(m["id"], new_title.strip(), new_content.strip())
                        st.toast("保存しました")
                        st.rerun()
                with mc2:
                    if st.button("削除", key=f"mdel_{m['id']}"):
                        db.delete_memo(m["id"])
                        st.rerun()

    # ===== 資料 =====
    with tab_material:
        with st.expander("資料をアップロード", expanded=False):
            mat_up = st.file_uploader("ファイルを選択", key="mat_up")
            mat_title = st.text_input("タイトル（空ならファイル名）", key="mat_title")
            mat_cat = st.text_input("カテゴリ（例: スライド、データ、ノート）", key="mat_cat")
            mat_note = st.text_area("メモ（任意）", key="mat_note", height=60)
            if st.button("アップロード", type="primary", key="mat_add"):
                if not mat_up:
                    st.error("ファイルを選択してください")
                else:
                    os.makedirs(config.MATERIALS_DIR, exist_ok=True)
                    path = os.path.join(config.MATERIALS_DIR, mat_up.name)
                    with open(path, "wb") as f:
                        f.write(mat_up.getbuffer())
                    title = mat_title.strip() or mat_up.name
                    db.add_material(title, mat_up.name, mat_cat.strip(), mat_note.strip())
                    st.success(f"「{title}」をアップロードしました")
                    st.rerun()

        cats = ["すべて"] + db.list_material_categories()
        flt_m = st.selectbox("カテゴリで絞り込み", cats, key="mat_filter")
        materials = db.list_materials(flt_m)
        if not materials:
            st.info("資料がありません。")

        for mat in materials:
            with st.container(border=True):
                mc1, mc2 = st.columns([4, 1])
                with mc1:
                    st.markdown(f"**{mat['title']}**")
                    if mat.get("category"):
                        st.caption(f"カテゴリ: {mat['category']}")
                    if mat.get("note"):
                        st.caption(mat["note"])
                    st.caption(f"アップロード: {mat['uploaded_at']}")
                with mc2:
                    path = os.path.join(config.MATERIALS_DIR, mat["filename"])
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            st.download_button(
                                "ダウンロード",
                                data=f,
                                file_name=mat["filename"],
                                key=f"dl_{mat['id']}",
                            )
                    if st.button("削除", key=f"matdel_{mat['id']}"):
                        if os.path.exists(path):
                            os.remove(path)
                        db.delete_material(mat["id"])
                        st.rerun()


    # ===== 製作物 =====
    with tab_works:
        with st.expander("製作物を追加", expanded=False):
            w_title = st.text_input("タイトル", key="w_title")
            w_desc  = st.text_input("一言説明（任意）", key="w_desc")
            wc1, wc2 = st.columns(2)
            with wc1:
                w_cat  = st.selectbox("カテゴリ", db.WORK_CATEGORIES, key="w_cat")
            with wc2:
                w_date = st.date_input("完成日（任意）", value=None, key="w_date")
            w_url     = st.text_input("URL（任意）", key="w_url", placeholder="https://...")
            w_content = st.text_area("詳細（Markdown対応）", key="w_content", height=200,
                                     placeholder="## 概要\n\n詳細をMarkdownで記述できます...")
            if st.button("追加", type="primary", key="w_add"):
                if not w_title.strip():
                    st.error("タイトルを入力してください")
                else:
                    db.add_work(
                        w_title.strip(), w_desc.strip(), w_content.strip(), w_cat,
                        w_url.strip(), w_date.isoformat() if w_date else "",
                    )
                    st.rerun()

        flt_w = st.selectbox("カテゴリで絞り込み", ["すべて"] + db.WORK_CATEGORIES, key="w_filter")
        works = db.list_works(flt_w)
        if not works:
            st.info("製作物がありません。")

        cat_colors = {
            "論文": "#6366F1", "ソフトウェア": "#3B82F6", "デザイン": "#EC4899",
            "レポート": "#F59E0B", "その他": "#94A3B8",
        }
        for w in works:
            with st.container(border=True):
                wh1, wh2, wh3 = st.columns([4, 1, 1])
                c = cat_colors.get(w.get("category", ""), "#94A3B8")
                with wh1:
                    st.markdown(
                        f"**{w['title']}** "
                        f"<span style='background:{c};color:white;padding:2px 8px;"
                        f"border-radius:4px;font-size:0.75em;'>{w.get('category','')}</span>",
                        unsafe_allow_html=True,
                    )
                    if w.get("date"):
                        st.caption(f"完成日: {w['date']}")
                    if w.get("description"):
                        st.caption(w["description"])
                    if w.get("url"):
                        st.markdown(f"[リンクを開く]({w['url']})")
                with wh2:
                    edit_key = f"w_edit_{w['id']}"
                    if st.button("編集", key=f"wedit_{w['id']}"):
                        st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                        st.rerun()
                with wh3:
                    if st.button("削除", key=f"wdel_{w['id']}"):
                        db.delete_work(w["id"])
                        st.rerun()

                if st.session_state.get(f"w_edit_{w['id']}"):
                    # 編集モード
                    new_content = st.text_area(
                        "Markdown編集", w.get("content") or "",
                        key=f"wcontent_{w['id']}", height=300,
                    )
                    new_desc = st.text_input("一言説明", w.get("description") or "", key=f"wdesc_{w['id']}")
                    new_url  = st.text_input("URL", w.get("url") or "", key=f"wurl_{w['id']}")
                    if st.button("保存", key=f"wsave_{w['id']}"):
                        db.update_work(w["id"], content=new_content, description=new_desc, url=new_url)
                        st.session_state[f"w_edit_{w['id']}"] = False
                        st.rerun()
                elif w.get("content"):
                    # プレビューモード
                    st.divider()
                    st.markdown(w["content"])


# ================== 右カラム: チャット ==================
if col_chat is not None:
    with col_chat:
        ch1, ch2 = st.columns([4, 1])
        with ch1:
            st.subheader("チャット")
        with ch2:
            st.write("")
            if st.button("閉じる", use_container_width=True):
                st.session_state.chat_open = False
                st.rerun()

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        chat_container = st.container(height=500)
        with chat_container:
            if not st.session_state.chat_history:
                st.caption("研究について何でも聞いてください。")
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        user_input = st.chat_input("メッセージを入力...")
        if user_input:
            key = get_api_key()
            if not key:
                st.error("APIキーを設定してください（サイドバー）")
            else:
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                messages = [{"role": "system", "content": chat_system_prompt()}] + st.session_state.chat_history
                client = Groq(api_key=key)
                resp = client.chat.completions.create(
                    model=config.GROQ_MODEL,
                    messages=messages,
                    max_tokens=1500,
                )
                answer = resp.choices[0].message.content
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                st.rerun()

        if st.session_state.chat_history:
            if st.button("会話をリセット", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
