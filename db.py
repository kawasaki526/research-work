"""進捗管理レイヤー（SQLite）。
論文・タスク・メモ・資料と研究プロフィールを保持する。
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
            answer_style TEXT,
            theme_color TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            detail TEXT,
            due_date TEXT,
            status TEXT DEFAULT '未着手',
            priority TEXT DEFAULT '中',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT,
            category TEXT,
            note TEXT,
            uploaded_at TEXT
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


# ---- 研究プロフィール ----

def get_profile():
    conn = _conn()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def save_profile(field, subtopics, level, focus, answer_lang, answer_style, theme_color=None):
    conn = _conn()
    try:
        conn.execute("ALTER TABLE profile ADD COLUMN theme_color TEXT")
        conn.commit()
    except Exception:
        pass
    conn.execute(
        "UPDATE profile SET field=?, subtopics=?, level=?, focus=?, answer_lang=?, answer_style=?, theme_color=? WHERE id=1",
        (field, subtopics, level, focus, answer_lang, answer_style, theme_color),
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


# ---- タスク管理 ----

TASK_STATUSES = ["未着手", "進行中", "完了"]
TASK_PRIORITIES = ["高", "中", "低"]


def add_task(title, detail, due_date, priority):
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO tasks (title, detail, due_date, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, detail, due_date, priority,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    return tid


def list_tasks(status=None):
    conn = _conn()
    order = "CASE priority WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, due_date ASC"
    if status and status != "すべて":
        rows = conn.execute(
            f"SELECT * FROM tasks WHERE status=? ORDER BY {order}", (status,)
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT * FROM tasks ORDER BY {order}").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_task(tid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    conn = _conn()
    conn.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), tid))
    conn.commit()
    conn.close()


def delete_task(tid):
    conn = _conn()
    conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
    conn.commit()
    conn.close()


# ---- メモ ----

def add_memo(title, content):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO memos (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title, content, now, now),
    )
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid


def list_memos():
    conn = _conn()
    rows = conn.execute("SELECT * FROM memos ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_memo(mid, title, content):
    conn = _conn()
    conn.execute(
        "UPDATE memos SET title=?, content=?, updated_at=? WHERE id=?",
        (title, content, datetime.datetime.now().isoformat(timespec="seconds"), mid),
    )
    conn.commit()
    conn.close()


def delete_memo(mid):
    conn = _conn()
    conn.execute("DELETE FROM memos WHERE id=?", (mid,))
    conn.commit()
    conn.close()


# ---- 資料 ----

def add_material(title, filename, category, note):
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO materials (title, filename, category, note, uploaded_at) VALUES (?, ?, ?, ?, ?)",
        (title, filename, category, note,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid


def list_materials(category=None):
    conn = _conn()
    if category and category != "すべて":
        rows = conn.execute(
            "SELECT * FROM materials WHERE category=? ORDER BY uploaded_at DESC", (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM materials ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_material_categories():
    conn = _conn()
    rows = conn.execute(
        "SELECT DISTINCT category FROM materials WHERE category IS NOT NULL AND category != ''"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


def delete_material(mid):
    conn = _conn()
    conn.execute("DELETE FROM materials WHERE id=?", (mid,))
    conn.commit()
    conn.close()
