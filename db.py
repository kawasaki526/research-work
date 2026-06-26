"""進捗管理レイヤー（SQLite）。
論文の一覧・ステータス・メモ・要約と、AIをあなた仕様にする研究プロフィールを保持する。
ベクトルDB（rag.py）とは別のレイヤー。
"""
import os
import sqlite3
import datetime
import config


def _conn():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            authors TEXT,
            year TEXT,
            status TEXT DEFAULT '未読',
            tags TEXT,
            summary TEXT,
            notes TEXT,
            filename TEXT,
            n_chunks INTEGER DEFAULT 0,
            added_at TEXT
        );
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            field TEXT,
            subtopics TEXT,
            level TEXT,
            focus TEXT,
            answer_lang TEXT,
            answer_style TEXT
        );
        """
    )
    cur = conn.execute("SELECT COUNT(*) AS c FROM profile")
    if cur.fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO profile (id, field, subtopics, level, focus, answer_lang, answer_style) "
            "VALUES (1, ?, ?, ?, ?, ?, ?)",
            ("", "", "大学院生", "", "日本語", "簡潔に、要点から先に"),
        )
    conn.commit()
    conn.close()


# ---- 研究プロフィール（Notionとの差別化の中核） ----

def get_profile():
    conn = _conn()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def save_profile(field, subtopics, level, focus, answer_lang, answer_style):
    conn = _conn()
    conn.execute(
        "UPDATE profile SET field=?, subtopics=?, level=?, focus=?, answer_lang=?, answer_style=? WHERE id=1",
        (field, subtopics, level, focus, answer_lang, answer_style),
    )
    conn.commit()
    conn.close()


# ---- 論文ライブラリ ----

def add_paper(title, authors, year, summary, filename, n_chunks):
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO papers (title, authors, year, summary, filename, n_chunks, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, authors, year, summary, filename, n_chunks,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def list_papers(status=None):
    conn = _conn()
    if status and status != "すべて":
        rows = conn.execute(
            "SELECT * FROM papers WHERE status=? ORDER BY added_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM papers ORDER BY added_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_paper(pid):
    conn = _conn()
    row = conn.execute("SELECT * FROM papers WHERE id=?", (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_paper_fields(pid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    conn = _conn()
    conn.execute(f"UPDATE papers SET {cols} WHERE id=?", (*fields.values(), pid))
    conn.commit()
    conn.close()


def delete_paper(pid):
    conn = _conn()
    conn.execute("DELETE FROM papers WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def counts_by_status():
    conn = _conn()
    rows = conn.execute(
        "SELECT status, COUNT(*) AS c FROM papers GROUP BY status"
    ).fetchall()
    conn.close()
    return {r["status"]: r["c"] for r in rows}
