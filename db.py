"""Storage layer. SQLite by default (local); Postgres when a DATABASE_URL is given.

Streamlit Community Cloud wipes local files on reboot/redeploy, so for real
multi-user use point DATABASE_URL (in Secrets) at a free Postgres (Neon / Supabase).
"""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id {pk}, username TEXT UNIQUE NOT NULL, salt TEXT NOT NULL,
        pw_hash TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS profiles (
        user_id INTEGER PRIMARY KEY, goal TEXT NOT NULL, skills_start TEXT NOT NULL,
        skills_now TEXT NOT NULL, start_date TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS study_log (
        id {pk}, user_id INTEGER NOT NULL, day TEXT NOT NULL,
        minutes INTEGER NOT NULL, skill TEXT, note TEXT)""",
    """CREATE TABLE IF NOT EXISTS steps_done (
        id {pk}, user_id INTEGER NOT NULL, skill TEXT NOT NULL, done_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS assessments (
        id {pk}, user_id INTEGER NOT NULL, kind TEXT NOT NULL, score INTEGER NOT NULL,
        detail TEXT, taken_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS feedback (
        id {pk}, user_id INTEGER NOT NULL, clarity INTEGER, usefulness INTEGER,
        topic_order INTEGER, comment_text TEXT, created_at TEXT NOT NULL)""",
]


def today_str():
    return date.today().isoformat()


def now_str():
    return datetime.now().isoformat(timespec="seconds")


def current_week(start_date, today=None):
    today = today or date.today()
    return max(1, (today - date.fromisoformat(start_date)).days // 7 + 1)


def streak_days(day_strings, today=None):
    """Consecutive study days ending today (or yesterday, so the streak isn't lost mid-day)."""
    today = today or date.today()
    days = set(day_strings)
    d = today if today.isoformat() in days else today - timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


class Store:
    def __init__(self, url=None):
        self.pg = bool(url) and url.startswith(("postgres://", "postgresql://"))
        if self.pg:
            import psycopg2  # noqa: F401  (only needed for Postgres)
            self.url = url.replace("postgres://", "postgresql://", 1)
        else:
            path = url.replace("sqlite:///", "", 1) if url else str(ROOT / "data" / "app.db")
            self.path = path
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        pk = "SERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        for stmt in SCHEMA:
            self._run(stmt.format(pk=pk))

    @contextmanager
    def _conn(self):
        if self.pg:
            import psycopg2
            con = psycopg2.connect(self.url)
        else:
            con = sqlite3.connect(self.path)
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _run(self, sql, params=(), fetch=False):
        if self.pg:
            sql = sql.replace("?", "%s")
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(sql, params)
            if fetch:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        return None

    def _df(self, sql, params=(), cols=None):
        rows = self._run(sql, params, fetch=True)
        return pd.DataFrame(rows, columns=cols) if not rows else pd.DataFrame(rows)

    # ------------------------------------------------------------- accounts
    @staticmethod
    def _hash(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 150_000).hex()

    def create_user(self, username, password):
        username = (username or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,30}", username):
            return None, "Username must be 3-30 characters: letters, numbers or underscore."
        if len(password or "") < 6:
            return None, "Password must be at least 6 characters."
        if self._run("SELECT id FROM users WHERE username = ?", (username,), fetch=True):
            return None, "That username is taken. Try another."
        salt = secrets.token_hex(16)
        self._run("INSERT INTO users (username, salt, pw_hash, created_at) VALUES (?, ?, ?, ?)",
                  (username, salt, self._hash(password, salt), now_str()))
        return self.login(username, password)

    def login(self, username, password):
        username = (username or "").strip().lower()
        rows = self._run("SELECT id, username, salt, pw_hash FROM users WHERE username = ?",
                         (username,), fetch=True)
        if not rows or not hmac.compare_digest(rows[0]["pw_hash"], self._hash(password or "", rows[0]["salt"])):
            return None, "Wrong username or password."
        return {"id": rows[0]["id"], "username": rows[0]["username"]}, "ok"

    # --------------------------------------------------------------- profile
    def save_profile(self, uid, goal, skills):
        blob = json.dumps(skills)
        self._run("DELETE FROM profiles WHERE user_id = ?", (uid,))
        self._run("DELETE FROM steps_done WHERE user_id = ?", (uid,))
        self._run("INSERT INTO profiles (user_id, goal, skills_start, skills_now, start_date) "
                  "VALUES (?, ?, ?, ?, ?)", (uid, goal, blob, blob, today_str()))

    def get_profile(self, uid):
        rows = self._run("SELECT * FROM profiles WHERE user_id = ?", (uid,), fetch=True)
        if not rows:
            return None
        r = rows[0]
        return {"goal": r["goal"], "start": json.loads(r["skills_start"]),
                "now": json.loads(r["skills_now"]), "start_date": r["start_date"]}

    def set_skill_level(self, uid, skill, level):
        p = self.get_profile(uid)
        p["now"][skill] = max(p["now"].get(skill, 0), level)
        self._run("UPDATE profiles SET skills_now = ? WHERE user_id = ?", (json.dumps(p["now"]), uid))

    def reset_profile(self, uid):
        self._run("DELETE FROM profiles WHERE user_id = ?", (uid,))
        self._run("DELETE FROM steps_done WHERE user_id = ?", (uid,))

    # ----------------------------------------------------------------- steps
    def steps_done(self, uid):
        rows = self._run("SELECT skill FROM steps_done WHERE user_id = ?", (uid,), fetch=True)
        return {r["skill"] for r in rows}

    def mark_step(self, uid, skill):
        if skill not in self.steps_done(uid):
            self._run("INSERT INTO steps_done (user_id, skill, done_at) VALUES (?, ?, ?)",
                      (uid, skill, now_str()))

    # ------------------------------------------------------------------ logs
    def log_study(self, uid, minutes, skill, note):
        self._run("INSERT INTO study_log (user_id, day, minutes, skill, note) VALUES (?, ?, ?, ?, ?)",
                  (uid, today_str(), int(minutes), skill, (note or "").strip()))

    def study_log(self, uid):
        df = self._df("SELECT day, minutes, skill, note FROM study_log WHERE user_id = ? ORDER BY day",
                      (uid,), cols=["day", "minutes", "skill", "note"])
        return df

    # ----------------------------------------------------------- assessments
    def add_assessment(self, uid, kind, score, detail):
        self._run("INSERT INTO assessments (user_id, kind, score, detail, taken_at) VALUES (?, ?, ?, ?, ?)",
                  (uid, kind, int(score), json.dumps(detail), now_str()))

    def assessments(self, uid):
        return self._df("SELECT kind, score, detail, taken_at FROM assessments WHERE user_id = ? "
                        "ORDER BY taken_at", (uid,), cols=["kind", "score", "detail", "taken_at"])

    # -------------------------------------------------------------- feedback
    def add_feedback(self, uid, clarity, usefulness, topic_order, comment):
        self._run("INSERT INTO feedback (user_id, clarity, usefulness, topic_order, comment_text, created_at) "
                  "VALUES (?, ?, ?, ?, ?, ?)", (uid, clarity, usefulness, topic_order, comment, now_str()))

    # ----------------------------------------------------------------- admin
    def admin_tables(self):
        q = {"users": "SELECT id, username, created_at FROM users",
             "profiles": "SELECT * FROM profiles",
             "study_log": "SELECT user_id, day, minutes, skill FROM study_log",
             "steps_done": "SELECT user_id, skill, done_at FROM steps_done",
             "assessments": "SELECT user_id, kind, score, taken_at FROM assessments ORDER BY taken_at",
             "feedback": "SELECT user_id, clarity, usefulness, topic_order, comment_text, created_at FROM feedback"}
        return {k: self._df(v) for k, v in q.items()}
