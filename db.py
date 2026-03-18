# -*- coding: utf-8 -*-
"""
db.py — SQLite wrapper for NEXUS agency.
Handles chat history, price alerts, opportunities, and user profile.
"""

import sqlite3
import os
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id   INTEGER NOT NULL,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            type        TEXT NOT NULL DEFAULT 'price',
            symbol      TEXT NOT NULL,
            target      REAL NOT NULL,
            direction   TEXT NOT NULL,
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS opportunities (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            url        TEXT UNIQUE NOT NULL,
            prize      TEXT,
            deadline   TEXT,
            fit_score  INTEGER DEFAULT 5,
            source     TEXT,
            seen_at    REAL NOT NULL,
            notified   INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_profile (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversations(chat_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_alert_active ON alerts(active, symbol);
        CREATE INDEX IF NOT EXISTS idx_opp_fit ON opportunities(fit_score DESC, deadline);
    """)
    conn.commit()
    conn.close()


# ── Conversations ─────────────────────────────────────────────────────────────

def save_message(chat_id: int, role: str, content: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO conversations (chat_id, role, content, timestamp) VALUES (?,?,?,?)",
        (chat_id, role, content, time.time())
    )
    conn.commit()
    conn.close()


def get_history(chat_id: int, limit: int = 12) -> list:
    """Return last `limit` messages as list of dicts with role/content."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM conversations WHERE chat_id=? ORDER BY timestamp DESC LIMIT ?",
        (chat_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(chat_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM conversations WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()


# ── Alerts ────────────────────────────────────────────────────────────────────

def save_alert(chat_id: int, symbol: str, target: float, direction: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO alerts (chat_id, type, symbol, target, direction, created_at) VALUES (?,?,?,?,?,?)",
        (chat_id, "price", symbol.upper(), target, direction.lower(), time.time())
    )
    alert_id = cur.lastrowid
    conn.commit()
    conn.close()
    return alert_id


def get_active_alerts() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE active=1"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def deactivate_alert(alert_id: int):
    conn = get_conn()
    conn.execute("UPDATE alerts SET active=0 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def get_user_alerts(chat_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE chat_id=? AND active=1 ORDER BY created_at DESC",
        (chat_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Opportunities ─────────────────────────────────────────────────────────────

def save_opportunity(title: str, url: str, prize: str, deadline: str,
                     fit_score: int, source: str) -> bool:
    """Returns True if newly inserted, False if duplicate."""
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO opportunities (title, url, prize, deadline, fit_score, source, seen_at)
               VALUES (?,?,?,?,?,?,?)""",
            (title, url, prize, deadline, fit_score, source, time.time())
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_top_opportunities(limit: int = 10, unnotified_only: bool = False) -> list:
    conn = get_conn()
    where = "WHERE notified=0" if unnotified_only else ""
    rows = conn.execute(
        f"""SELECT * FROM opportunities {where}
            ORDER BY fit_score DESC, seen_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notified(opp_id: int):
    conn = get_conn()
    conn.execute("UPDATE opportunities SET notified=1 WHERE id=?", (opp_id,))
    conn.commit()
    conn.close()


# ── User profile ──────────────────────────────────────────────────────────────

def set_profile(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_profile (key, value) VALUES (?,?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def get_profile(key: str, default: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM user_profile WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


# Initialise on import
init_db()
