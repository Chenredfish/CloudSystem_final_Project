import json
import os
import time
from urllib.parse import urlparse

import requests

from db import get_connection

# Build node_id → URL map from NODE_URLS env var (e.g. "http://node1:5000,http://node2:5000")
_NODE_URL_MAP: dict = {}
for _u in os.environ.get('NODE_URLS', '').split(','):
    _u = _u.strip()
    if _u:
        _host = urlparse(_u).hostname or ''
        if _host:
            _NODE_URL_MAP[_host] = _u

MAX_RETRY = int(os.environ.get('MAX_RETRY', '3'))
DISPATCH_INTERVAL = int(os.environ.get('DISPATCH_INTERVAL', '5'))
NODE_TIMEOUT_SEC = int(os.environ.get('NODE_TIMEOUT_SEC', '35'))


def _node_url(node_id: str) -> str:
    return _NODE_URL_MAP.get(node_id, f'http://{node_id}:5000')


def try_dispatch():
    """Pick one queued job + one idle node, mark both as running/busy, then HTTP-POST to node.
    Uses BEGIN IMMEDIATE so two concurrent callers don't double-dispatch the same pair."""
    conn = get_connection()
    job = node = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT * FROM jobs WHERE status='queued' ORDER BY submitted_at LIMIT 1"
        ).fetchone()
        node = conn.execute(
            "SELECT * FROM nodes WHERE status='idle' LIMIT 1"
        ).fetchone()
        if not job or not node:
            conn.rollback()
            conn.close()
            return
        job_id = job['id']
        node_id = node['node_id']
        now = time.time()
        conn.execute(
            "UPDATE jobs  SET status='running', node_id=?, dispatched_at=? WHERE id=?",
            (node_id, now, job_id),
        )
        conn.execute(
            "UPDATE nodes SET status='busy', current_job_id=? WHERE node_id=?",
            (job_id, node_id),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return
    conn.close()

    # HTTP dispatch — outside the transaction so the lock is released first
    payload = {
        'job_id': job['id'],
        'map_grid': json.loads(job['map_grid']),
        'products': json.loads(job['products']),
        'num_agents': job['num_agents'],
        'seed': job['seed'],
        'list_size': job['list_size'],
        'max_steps': job['max_steps'],
        'algorithm': job['algorithm'],
    }

    success = False
    try:
        r = requests.post(f"{_node_url(node_id)}/run", json=payload, timeout=10)
        success = r.ok
    except Exception:
        pass

    if not success:
        conn2 = get_connection()
        retry = job['retry_count'] + 1
        if retry >= MAX_RETRY:
            conn2.execute(
                """UPDATE jobs SET status='failed', retry_count=?,
                   error_msg='dispatch failed after max retries' WHERE id=?""",
                (retry, job['id']),
            )
        else:
            conn2.execute(
                """UPDATE jobs SET status='queued', node_id=NULL, dispatched_at=NULL,
                   retry_count=? WHERE id=?""",
                (retry, job['id']),
            )
        conn2.execute(
            "UPDATE nodes SET status='idle', current_job_id=NULL WHERE node_id=?",
            (node_id,),
        )
        conn2.commit()
        conn2.close()


def background_scanner():
    """Daemon thread: detect offline nodes, re-queue orphaned jobs, call try_dispatch."""
    while True:
        time.sleep(DISPATCH_INTERVAL)
        now = time.time()
        conn = get_connection()
        try:
            conn.execute("BEGIN")
            # Mark nodes that missed heartbeats as offline
            conn.execute(
                """UPDATE nodes
                   SET status='offline', consecutive_miss=consecutive_miss+1
                   WHERE last_heartbeat IS NOT NULL
                     AND ? - last_heartbeat > ?
                     AND status NOT IN ('offline')""",
                (now, NODE_TIMEOUT_SEC),
            )
            # Re-queue running jobs whose node went offline
            conn.execute(
                """UPDATE jobs
                   SET status='queued', node_id=NULL, dispatched_at=NULL
                   WHERE status='running'
                     AND node_id IN (SELECT node_id FROM nodes WHERE status='offline')"""
            )
            # Re-queue running jobs whose node restarted (idle but job still 'running')
            conn.execute(
                """UPDATE jobs
                   SET status='queued', node_id=NULL, dispatched_at=NULL
                   WHERE status='running'
                     AND node_id IN (SELECT node_id FROM nodes WHERE status='idle')"""
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()

        try_dispatch()
