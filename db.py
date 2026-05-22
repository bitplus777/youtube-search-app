"""검색 기록 저장/불러오기/삭제 + 쿼타 추적 - SQLite 기반"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "search_history.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            saved_at    TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            grade_s     INTEGER DEFAULT 0,
            grade_a     INTEGER DEFAULT 0,
            grade_b     INTEGER DEFAULT 0,
            grade_c     INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS results (
            session_id   TEXT,
            grade        TEXT,
            content_type TEXT,
            title        TEXT,
            channel      TEXT,
            subscribers  INTEGER,
            url          TEXT,
            published    TEXT,
            days_since   INTEGER,
            views        INTEGER,
            likes        INTEGER,
            comments     INTEGER,
            duration     TEXT,
            thumbnail    TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quota_log (
            date    TEXT PRIMARY KEY,
            units   INTEGER DEFAULT 0,
            calls   INTEGER DEFAULT 0
        );
        """)


def save_session(name: str, rows: list[dict]) -> str:
    """검색 결과를 저장하고 session_id 반환."""
    init_db()
    sid = str(uuid.uuid4())[:8]
    saved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    grade_counts = {g: sum(1 for r in rows if r.get("등급") == g) for g in "SABC"}

    with _conn() as con:
        con.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
            (sid, name, saved_at, len(rows),
             grade_counts["S"], grade_counts["A"],
             grade_counts["B"], grade_counts["C"]),
        )
        con.executemany(
            "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    sid,
                    r.get("등급", ""),
                    r.get("콘텐츠유형", ""),
                    r.get("제목", ""),
                    r.get("채널명", ""),
                    r.get("구독자수", 0),
                    r.get("URL", ""),
                    r.get("업로드일", ""),
                    r.get("업로드경과일", 0),
                    r.get("조회수", 0),
                    r.get("좋아요", 0),
                    r.get("댓글수", 0),
                    r.get("재생시간", ""),
                    r.get("썸네일", ""),
                )
                for r in rows
            ],
        )
    return sid


def list_sessions() -> list[dict]:
    """저장된 세션 목록 (최신순)."""
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM sessions ORDER BY saved_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def load_session(session_id: str) -> list[dict]:
    """세션의 검색 결과 불러오기."""
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM results WHERE session_id = ?", (session_id,)
        ).fetchall()
    return [
        {
            "등급": r["grade"],
            "콘텐츠유형": r["content_type"],
            "제목": r["title"],
            "채널명": r["channel"],
            "구독자수": r["subscribers"],
            "URL": r["url"],
            "업로드일": r["published"],
            "업로드경과일": r["days_since"],
            "조회수": r["views"],
            "좋아요": r["likes"],
            "댓글수": r["comments"],
            "재생시간": r["duration"],
            "썸네일": r["thumbnail"],
            "_is_short": r["content_type"] == "🩳 숏폼",
            "_channel_id": "",
        }
        for r in rows
    ]


def delete_session(session_id: str):
    """세션 삭제 (결과 포함)."""
    init_db()
    with _conn() as con:
        con.execute("DELETE FROM results WHERE session_id = ?", (session_id,))
        con.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def rename_session(session_id: str, new_name: str):
    init_db()
    with _conn() as con:
        con.execute("UPDATE sessions SET name = ? WHERE id = ?", (new_name, session_id))


# ── 쿼타 추적 ─────────────────────────────────────────────────────────────────
def add_quota(units: int, calls: int = 1):
    """오늘 사용한 쿼타 추가."""
    init_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _conn() as con:
        row = con.execute("SELECT units, calls FROM quota_log WHERE date=?", (today,)).fetchone()
        if row:
            con.execute(
                "UPDATE quota_log SET units=units+?, calls=calls+? WHERE date=?",
                (units, calls, today),
            )
        else:
            con.execute(
                "INSERT INTO quota_log (date, units, calls) VALUES (?,?,?)",
                (today, units, calls),
            )


def get_today_quota() -> dict:
    """오늘 사용한 쿼타 현황."""
    init_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _conn() as con:
        row = con.execute("SELECT units, calls FROM quota_log WHERE date=?", (today,)).fetchone()
    return {"units": row["units"] if row else 0, "calls": row["calls"] if row else 0}


def get_quota_history(days: int = 7) -> list[dict]:
    """최근 N일 쿼타 이력."""
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT date, units, calls FROM quota_log ORDER BY date DESC LIMIT ?",
            (days,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_total_stats() -> dict:
    """전체 누적 통계."""
    init_db()
    with _conn() as con:
        total_sessions = con.execute("SELECT COUNT(*) as n FROM sessions").fetchone()["n"]
        total_videos = con.execute("SELECT COUNT(*) as n FROM results").fetchone()["n"]
        total_quota = con.execute("SELECT SUM(units) as n FROM quota_log").fetchone()["n"] or 0
    return {
        "sessions": total_sessions,
        "videos": total_videos,
        "quota": total_quota,
    }
