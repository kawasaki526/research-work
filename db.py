"""進捗管理レイヤー（PostgreSQL / Supabase）。"""
import datetime
import os

import psycopg2
import psycopg2.extras

_cached_conn = None


def _get_url():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL", "")
        except Exception:
            pass
    return url


def _conn():
    global _cached_conn
    try:
        if _cached_conn is not None and _cached_conn.closed == 0:
            _cached_conn.cursor().execute("SELECT 1")
            return _cached_conn
    except Exception:
        pass
    _cached_conn = psycopg2.connect(
        _get_url(), cursor_factory=psycopg2.extras.RealDictCursor
    )
    _cached_conn.autocommit = True
    return _cached_conn


def init_db():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id SERIAL PRIMARY KEY,
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
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            field TEXT,
            subtopics TEXT,
            level TEXT,
            focus TEXT,
            answer_lang TEXT,
            answer_style TEXT,
            CONSTRAINT profile_singleton CHECK (id = 1)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            detail TEXT,
            due_date TEXT,
            status TEXT DEFAULT '未着手',
            priority TEXT DEFAULT '中',
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memos (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            filename TEXT,
            category TEXT,
            note TEXT,
            uploaded_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS works (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            content TEXT,
            category TEXT,
            url TEXT,
            date TEXT,
            created_at TEXT
        )
    """)
    cur.execute("SELECT COUNT(*) AS c FROM profile")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO profile (id, field, subtopics, level, focus, answer_lang, answer_style) "
            "VALUES (1, %s, %s, %s, %s, %s, %s)",
            ("", "", "大学院生", "", "日本語", "簡潔に、要点から先に"),
        )
    cur.close()


# ---- 研究プロフィール ----

def get_profile():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM profile WHERE id = 1")
    row = cur.fetchone()
    cur.close()
    return dict(row) if row else {}


def save_profile(field, subtopics, level, focus, answer_lang, answer_style):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE profile SET field=%s, subtopics=%s, level=%s, focus=%s, answer_lang=%s, answer_style=%s WHERE id=1",
        (field, subtopics, level, focus, answer_lang, answer_style),
    )
    cur.close()


# ---- 論文ライブラリ ----

def add_paper(title, authors, year, summary, filename, n_chunks):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO papers (title, authors, year, summary, filename, n_chunks, added_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (title, authors, year, summary, filename, n_chunks,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    pid = cur.fetchone()["id"]
    cur.close()
    return pid


def list_papers(status=None):
    conn = _conn()
    cur = conn.cursor()
    if status and status != "すべて":
        cur.execute("SELECT * FROM papers WHERE status=%s ORDER BY added_at DESC", (status,))
    else:
        cur.execute("SELECT * FROM papers ORDER BY added_at DESC")
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def get_paper(pid):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM papers WHERE id=%s", (pid,))
    row = cur.fetchone()
    cur.close()
    return dict(row) if row else None


def update_paper_fields(pid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=%s" for k in fields)
    conn = _conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE papers SET {cols} WHERE id=%s", (*fields.values(), pid))
    cur.close()


def delete_paper(pid):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM papers WHERE id=%s", (pid,))
    cur.close()


def counts_by_status():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) AS c FROM papers GROUP BY status")
    rows = cur.fetchall()
    cur.close()
    return {r["status"]: r["c"] for r in rows}


# ---- タスク管理 ----

TASK_STATUSES = ["未着手", "進行中", "完了"]
TASK_PRIORITIES = ["高", "中", "低"]


def add_task(title, detail, due_date, priority):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (title, detail, due_date, priority, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (title, detail, due_date, priority,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    tid = cur.fetchone()["id"]
    cur.close()
    return tid


def list_tasks(status=None):
    conn = _conn()
    cur = conn.cursor()
    order = "CASE priority WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, due_date ASC"
    if status and status != "すべて":
        cur.execute(f"SELECT * FROM tasks WHERE status=%s ORDER BY {order}", (status,))
    else:
        cur.execute(f"SELECT * FROM tasks ORDER BY {order}")
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def update_task(tid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=%s" for k in fields)
    conn = _conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE tasks SET {cols} WHERE id=%s", (*fields.values(), tid))
    cur.close()


def delete_task(tid):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id=%s", (tid,))
    cur.close()


# ---- メモ ----

def add_memo(title, content):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memos (title, content, created_at, updated_at) VALUES (%s, %s, %s, %s) RETURNING id",
        (title, content, now, now),
    )
    mid = cur.fetchone()["id"]
    cur.close()
    return mid


def list_memos():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM memos ORDER BY updated_at DESC")
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def update_memo(mid, title, content):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE memos SET title=%s, content=%s, updated_at=%s WHERE id=%s",
        (title, content, datetime.datetime.now().isoformat(timespec="seconds"), mid),
    )
    cur.close()


def delete_memo(mid):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM memos WHERE id=%s", (mid,))
    cur.close()


# ---- 資料 ----

def add_material(title, filename, category, note):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO materials (title, filename, category, note, uploaded_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (title, filename, category, note,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    mid = cur.fetchone()["id"]
    cur.close()
    return mid


def list_materials(category=None):
    conn = _conn()
    cur = conn.cursor()
    if category and category != "すべて":
        cur.execute("SELECT * FROM materials WHERE category=%s ORDER BY uploaded_at DESC", (category,))
    else:
        cur.execute("SELECT * FROM materials ORDER BY uploaded_at DESC")
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def list_material_categories():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM materials WHERE category IS NOT NULL AND category != ''")
    rows = cur.fetchall()
    cur.close()
    return [r["category"] for r in rows]


def delete_material(mid):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM materials WHERE id=%s", (mid,))
    cur.close()


# ---- 製作物 ----

WORK_CATEGORIES = ["論文", "ソフトウェア", "デザイン", "レポート", "その他"]


def add_work(title, description, content, category, url, date):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO works (title, description, content, category, url, date, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (title, description, content, category, url, date,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    wid = cur.fetchone()["id"]
    cur.close()
    return wid


def list_works(category=None):
    conn = _conn()
    cur = conn.cursor()
    if category and category != "すべて":
        cur.execute("SELECT * FROM works WHERE category=%s ORDER BY date DESC, created_at DESC", (category,))
    else:
        cur.execute("SELECT * FROM works ORDER BY date DESC, created_at DESC")
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def update_work(wid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=%s" for k in fields)
    conn = _conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE works SET {cols} WHERE id=%s", (*fields.values(), wid))
    cur.close()


def delete_work(wid):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM works WHERE id=%s", (wid,))
    cur.close()
