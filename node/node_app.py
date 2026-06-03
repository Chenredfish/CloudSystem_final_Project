import json
import os
import re
import subprocess
import threading
import time

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

NODE_ID = os.environ.get('NODE_ID', 'unknown')
WEB_CALLBACK_URL = os.environ.get('WEB_CALLBACK_URL', 'http://web:80')
HEARTBEAT_INTERVAL = 10

_job_lock = threading.Lock()
_current_job = {'job_id': None, 'process': None}

REQUIRED_RUN_FIELDS = ['job_id', 'map_grid', 'products', 'num_agents', 'seed']


def _get_current_job_id():
    with _job_lock:
        return _current_job['job_id']


def _clear_job():
    with _job_lock:
        _current_job['job_id'] = None
        _current_job['process'] = None


def _monitor_job(proc):
    proc.wait()
    _clear_job()


def _heartbeat_loop():
    while True:
        try:
            job_id = _get_current_job_id()
            requests.post(
                f"{WEB_CALLBACK_URL}/api/nodes/{NODE_ID}/heartbeat",
                json={'status': 'busy' if job_id else 'idle', 'current_job_id': job_id},
                timeout=5,
            )
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


def _start_heartbeat():
    threading.Thread(target=_heartbeat_loop, daemon=True).start()


# Works with both direct run and Gunicorn fork
os.register_at_fork(after_in_child=_start_heartbeat)
_start_heartbeat()


def _parse_top():
    try:
        result = subprocess.run(
            ['top', '-bn', '1', '-i', '-c'],
            capture_output=True, text=True, timeout=5
        )
        cpu_pct = 0.0
        mem_used_mb = mem_total_mb = 0.0

        for line in result.stdout.split('\n'):
            if '%Cpu' in line:
                m = re.search(r'([\d.]+)\s*id', line)
                if m:
                    cpu_pct = round(100.0 - float(m.group(1)), 1)
            elif 'MiB Mem' in line or 'KiB Mem' in line:
                m_total = re.search(r'([\d.]+)\s+total', line)
                m_used = re.search(r'([\d.]+)\s+used', line)
                if m_total and m_used:
                    scale = 1.0 if 'MiB' in line else 1.0 / 1024.0
                    mem_total_mb = round(float(m_total.group(1)) * scale, 1)
                    mem_used_mb = round(float(m_used.group(1)) * scale, 1)

        mem_pct = round(mem_used_mb / mem_total_mb * 100.0, 1) if mem_total_mb > 0 else 0.0
        return cpu_pct, mem_pct, mem_used_mb, mem_total_mb
    except Exception:
        return 0.0, 0.0, 0.0, 0.0


@app.route('/status', methods=['GET'])
def status():
    cpu_pct, mem_pct, mem_used_mb, mem_total_mb = _parse_top()
    job_id = _get_current_job_id()
    return jsonify({
        'success': True,
        'data': {
            'node_id': NODE_ID,
            'status': 'busy' if job_id else 'idle',
            'current_job_id': job_id,
            'cpu_percent': cpu_pct,
            'mem_percent': mem_pct,
            'mem_used_mb': mem_used_mb,
            'mem_total_mb': mem_total_mb,
        },
        'error': None,
    })


@app.route('/run', methods=['POST'])
def run():
    body = request.get_json(silent=True) or {}
    missing = [f for f in REQUIRED_RUN_FIELDS if f not in body]
    if missing:
        return jsonify({
            'success': False, 'data': None,
            'error': {'code': 'MISSING_FIELDS', 'message': f"Missing: {', '.join(missing)}"},
        }), 400

    job_id = body['job_id']
    job_json = json.dumps(body)

    with _job_lock:
        if _current_job['job_id'] is not None:
            return jsonify({
                'success': False, 'data': None,
                'error': {'code': 'NODE_BUSY', 'message': f"Already running {_current_job['job_id']}"},
            }), 409
        try:
            proc = subprocess.Popen(['python3', 'mapf/compute.py', job_json])
        except Exception as e:
            return jsonify({
                'success': False, 'data': None,
                'error': {'code': 'SPAWN_ERROR', 'message': str(e)},
            }), 500
        _current_job['job_id'] = job_id
        _current_job['process'] = proc

    threading.Thread(target=_monitor_job, args=(proc,), daemon=True).start()
    return jsonify({'success': True, 'data': {'job_id': job_id}, 'error': None}), 202


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
