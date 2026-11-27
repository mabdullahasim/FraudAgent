import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "reviews.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                trans_num TEXT PRIMARY KEY,
                action TEXT,
                risk TEXT,
                reason TEXT,
                reviewer_label INTEGER,
                created_at TEXT
            )
        """)

def save_review(trans_num, decision):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO reviews
            (trans_num, action, risk, reason, reviewer_label, created_at)
            VALUES (?, ?, ?, ?, NULL, ?)
        """, (trans_num, decision["action"], decision["risk"],
              decision["reason"], datetime.now().isoformat()))

def get_review(trans_num):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE trans_num = ?", (trans_num,)).fetchone()
    return dict(row) if row else None

def save_feedback(trans_num, label):
    with get_conn() as conn:
        conn.execute("UPDATE reviews SET reviewer_label = ? WHERE trans_num = ?", (label, trans_num))