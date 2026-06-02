import os
import sqlite3

DB_PATH = os.environ.get('DB_PATH', '/data/jobs.db')
IMAGE_DIR = os.environ.get('IMAGE_DIR', '/data/images')


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
            consecutive_miss INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()
