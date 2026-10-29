"""SQLite storage: pengaturan (key-value) dan draft/post LinkedIn."""
import os
import secrets
import sqlite3
import threading
from pathlib import Path

from util import iso, now, parse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
KEY_FILE = BASE_DIR / "openai_key.txt"
ANTHROPIC_KEY_FILE = BASE_DIR / "anthropic_key.txt"
RESEND_KEY_FILE = BASE_DIR / "resend_key.txt"

DEFAULTS = {
    "profile_summary": (
        "Executive Assistant | Executive Secretary | Administrative & Procurement Specialist | "
        "Executive Support | Procurement & Vendor Coordination | Remote Administrative Support  "
        "South Sumatra, Indonesia"
    ),
    "openai_api_key": "",
    "openai_model": "gpt-5-mini",
    # openai | anthropic
    "llm_provider": "openai",
    "anthropic_api_key": "",
    "anthropic_model": "claude-sonnet-5-5",
    # email preview via Resend
    "email_preview_enabled": "1",
    "resend_api_key": "",
    "resend_from": "LinkedIn Bot <onboarding@resend.dev>",
    "resend_to": "",
    "resend_last_status": "",
    # daily | hours | minutes
    "gen_mode": "daily",
    "gen_daily_time": "18:30",
    "gen_every_value": "24",
    # at_time | immediate
    "publish_mode": "at_time",
    "publish_time": "19:30",
    "linkedin_client_id": "",
    "linkedin_client_secret": "",
    "linkedin_version": "202601",
    "public_base_url": "",
    "linkedin_access_token": "",
    "linkedin_refresh_token": "",
    "linkedin_expires_at": "",
    "linkedin_person_sub": "",
    "linkedin_person_name": "",
    "dashboard_password_hash": "",
    "app_secret": "",
    "last_generate_at": "",
    "oauth_state": "",
    "oauth_state_expires": "",
}

ALLOWED_POST_FIELDS = {
    "text", "status", "publish_at", "posted_at", "linkedin_urn", "error", "approved_at", "updated_at",
}

_init_lock = threading.Lock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    post_date TEXT NOT NULL,
    slot TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    publish_at TEXT NOT NULL DEFAULT '',
    posted_at TEXT NOT NULL DEFAULT '',
    linkedin_urn TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'openai',
    approved_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_post_date ON posts(post_date);
"""


def _connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _escape(name):
    if name not in ALLOWED_POST_FIELDS:
        raise ValueError("Kolom tidak diizinkan: %s" % name)
    return name


def init_db():
    """Buat tabel, isi default, dan tetapkan baseline jadwal pada start pertama."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        with _connect() as conn:
            conn.executescript(SCHEMA)
            for key, value in DEFAULTS.items():
                conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, value))
            secret = conn.execute("SELECT value FROM settings WHERE key='app_secret'").fetchone()["value"]
            if not secret:
                conn.execute("UPDATE settings SET value=? WHERE key='app_secret'", (secrets.token_hex(32),))
            last = conn.execute("SELECT value FROM settings WHERE key='last_generate_at'").fetchone()["value"]
            if not last:
                conn.execute("UPDATE settings SET value=? WHERE key='last_generate_at'", (iso(now()),))
        # Sisa proses yang mati di tengah publikasi jangan menggantung selamanya.
        with _connect() as conn:
            conn.execute(
                "UPDATE posts SET status='failed', error='Proses publikasi terhenti (aplikasi ditutup). Coba lagi.' "
                "WHERE status='publishing'"
            )
        _initialized = True


# ---------- settings ----------

def get_setting(key, default=""):
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, "" if value is None else str(value)),
        )


def set_settings(values):
    with _connect() as conn:
        for key, value in values.items():
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, "" if value is None else str(value)),
            )


def all_settings():
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    data = dict(DEFAULTS)
    data.update({row["key"]: row["value"] for row in rows})
    return data


def effective_openai_key(settings=None):
    """Key dari dashboard, lalu OPENAI_API_KEY, lalu file openai_key.txt.

    Mengembalikan (key, sumber) dengan sumber: 'dashboard', 'environment',
    'openai_key.txt', atau '' bila tidak ada.
    """
    settings = settings or all_settings()
    key = (settings.get("openai_api_key") or "").strip()
    if key:
        return key, "dashboard"
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if key:
        return key, "environment"
    try:
        if KEY_FILE.exists():
            key = KEY_FILE.read_text(encoding="utf-8").strip()
            if key:
                return key, "openai_key.txt"
    except OSError:
        pass
    return "", ""


def effective_anthropic_key(settings=None):
    """Key Claude dari dashboard, lalu ANTHROPIC_API_KEY, lalu anthropic_key.txt."""
    settings = settings or all_settings()
    key = (settings.get("anthropic_api_key") or "").strip()
    if key:
        return key, "dashboard"
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if key:
        return key, "environment"
    try:
        if ANTHROPIC_KEY_FILE.exists():
            key = ANTHROPIC_KEY_FILE.read_text(encoding="utf-8").strip()
            if key:
                return key, "anthropic_key.txt"
    except OSError:
        pass
    return "", ""


def effective_resend_key(settings=None):
    """Key Resend dari dashboard, lalu RESEND_API_KEY, lalu resend_key.txt."""
    settings = settings or all_settings()
    key = (settings.get("resend_api_key") or "").strip()
    if key:
        return key, "dashboard"
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if key:
        return key, "environment"
    try:
        if RESEND_KEY_FILE.exists():
            key = RESEND_KEY_FILE.read_text(encoding="utf-8").strip()
            if key:
                return key, "resend_key.txt"
    except OSError:
        pass
    return "", ""


def effective_llm_key(settings=None):
    """Key untuk provider yang sedang dipilih -> (provider, key, sumber)."""
    settings = settings or all_settings()
    provider = (settings.get("llm_provider") or "openai").strip().lower()
    if provider not in ("openai", "anthropic"):
        provider = "openai"
    if provider == "anthropic":
        key, source = effective_anthropic_key(settings)
    else:
        key, source = effective_openai_key(settings)
    return provider, key, source


# ---------- posts ----------

def create_post(post_date, slot, source="openai"):
    stamp = iso(now())
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO posts(created_at, updated_at, post_date, slot, source) VALUES(?, ?, ?, ?, ?)",
            (stamp, stamp, post_date, slot, source),
        )
        return cur.lastrowid


def update_post(post_id, **fields):
    if not fields:
        return
    fields.setdefault("updated_at", iso(now()))
    columns = ", ".join("%s=?" % _escape(name) for name in fields)
    values = list(fields.values()) + [post_id]
    with _connect() as conn:
        conn.execute("UPDATE posts SET %s WHERE id=?" % columns, values)


def get_post(post_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    return dict(row) if row else None


def list_posts(statuses=None, limit=200):
    query = "SELECT * FROM posts"
    params = []
    if statuses:
        query += " WHERE status IN (%s)" % ",".join("?" for _ in statuses)
        params.extend(statuses)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def active_posts():
    return list_posts(["pending", "approved", "failed", "publishing"], limit=100)


def due_posts(cutoff_dt):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE status='approved' AND publish_at<>'' ORDER BY publish_at ASC"
        ).fetchall()
    due = []
    for row in rows:
        when = parse(row["publish_at"])
        if when and when <= cutoff_dt:
            due.append(dict(row))
    return due


def claim_post(post_id):
    """Tandai publishing secara atomik agar tidak terkirim dua kali."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE posts SET status='publishing', updated_at=? WHERE id=? AND status='approved'",
            (iso(now()), post_id),
        )
        return cur.rowcount == 1


def delete_post(post_id):
    with _connect() as conn:
        cur = conn.execute("DELETE FROM posts WHERE id=? AND status IN ('cancelled','failed')", (post_id,))
        return cur.rowcount == 1
