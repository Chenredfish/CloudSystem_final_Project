import json
import os
import sqlite3
import time

DB_PATH = os.environ.get('DB_PATH', '/data/jobs.db')
IMAGE_DIR = os.environ.get('IMAGE_DIR', '/data/images')


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    conn = get_connection()
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS jobs (
            id              TEXT PRIMARY KEY,
            map_grid        TEXT NOT NULL,
            products        TEXT NOT NULL,
            num_agents      INTEGER NOT NULL,
            list_size       INTEGER NOT NULL DEFAULT 4,
            max_steps       INTEGER NOT NULL DEFAULT 200,
            algorithm       TEXT NOT NULL DEFAULT 'PBS',
            seed            INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'queued',
            node_id         TEXT,
            retry_count     INTEGER NOT NULL DEFAULT 0,
            result_gif_path TEXT,
            stats           TEXT,
            elapsed_sec     REAL,
            error_msg       TEXT,
            submitted_at    REAL NOT NULL,
            dispatched_at   REAL,
            completed_at    REAL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

        CREATE TABLE IF NOT EXISTS nodes (
            node_id          TEXT PRIMARY KEY,
            status           TEXT NOT NULL DEFAULT 'unknown',
            current_job_id   TEXT,
            last_heartbeat   REAL,
            consecutive_miss INTEGER NOT NULL DEFAULT 0,
            cpu_percent      REAL NOT NULL DEFAULT 0.0,
            mem_percent      REAL NOT NULL DEFAULT 0.0
        );
    """)
    # Migration: add columns if table already existed without them
    for col, dtype in [('cpu_percent', 'REAL'), ('mem_percent', 'REAL')]:
        try:
            conn.execute(f"ALTER TABLE nodes ADD COLUMN {col} {dtype} NOT NULL DEFAULT 0.0")
            conn.commit()
        except Exception:
            pass
    conn.close()


# ── helpers ──────────────────────────────────────────────────────────────────

def _row_to_job(row):
    if row is None:
        return None
    d = dict(row)
    for field in ('map_grid', 'products', 'stats'):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ── jobs CRUD ─────────────────────────────────────────────────────────────────

def create_job(id, map_grid, products, num_agents, list_size, max_steps, algorithm, seed):
    conn = get_connection()
    conn.execute(
        """INSERT INTO jobs
               (id, map_grid, products, num_agents, list_size, max_steps, algorithm, seed, submitted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (id, json.dumps(map_grid), json.dumps(products),
         num_agents, list_size, max_steps, algorithm, seed, time.time()),
    )
    conn.commit()
    conn.close()


def get_all_jobs():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM jobs ORDER BY submitted_at DESC").fetchall()
    conn.close()
    return [_row_to_job(r) for r in rows]


def get_job(id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
    conn.close()
    return _row_to_job(row)


def update_job_status(id, status, node_id=None, dispatched_at=None):
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET status=?, node_id=?, dispatched_at=? WHERE id=?",
        (status, node_id, dispatched_at, id),
    )
    conn.commit()
    conn.close()


def cancel_job(id):
    """Return True only when the job was queued and is now cancelled."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE jobs SET status='cancelled' WHERE id=? AND status='queued'", (id,)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def save_job_result(id, gif_path, stats, elapsed_sec):
    stats_str = json.dumps(stats) if not isinstance(stats, str) else stats
    conn = get_connection()
    conn.execute(
        """UPDATE jobs
           SET status='done', result_gif_path=?, stats=?, elapsed_sec=?, completed_at=?
           WHERE id=?""",
        (gif_path, stats_str, elapsed_sec, time.time(), id),
    )
    conn.commit()
    conn.close()


# ── nodes CRUD ────────────────────────────────────────────────────────────────

def upsert_node(node_id, status, current_job_id, last_heartbeat, cpu_percent=0.0, mem_percent=0.0):
    conn = get_connection()
    conn.execute(
        """INSERT INTO nodes (node_id, status, current_job_id, last_heartbeat, consecutive_miss, cpu_percent, mem_percent)
           VALUES (?, ?, ?, ?, 0, ?, ?)
           ON CONFLICT(node_id) DO UPDATE SET
               status          = excluded.status,
               current_job_id  = excluded.current_job_id,
               last_heartbeat  = excluded.last_heartbeat,
               consecutive_miss = 0,
               cpu_percent     = excluded.cpu_percent,
               mem_percent     = excluded.mem_percent""",
        (node_id, status, current_job_id, last_heartbeat, cpu_percent, mem_percent),
    )
    conn.commit()
    conn.close()


def get_all_nodes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM nodes ORDER BY node_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_idle_nodes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM nodes WHERE status='idle'").fetchall()
    conn.close()
    return [dict(r) for r in rows]
