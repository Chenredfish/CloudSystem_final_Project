import os
import re
import subprocess

from flask import Flask, jsonify

app = Flask(__name__)

NODE_ID = os.environ.get('NODE_ID', 'unknown')

# Phase 2 將改為執行緒安全的物件；Phase 1 僅佔位
_current_job_id = None


def _parse_top():
    """執行 top -bn 1 -i -c 並解析 CPU / 記憶體使用率。"""
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
                m_used  = re.search(r'([\d.]+)\s+used', line)
                if m_total and m_used:
                    scale = 1.0 if 'MiB' in line else 1.0 / 1024.0
                    mem_total_mb = round(float(m_total.group(1)) * scale, 1)
                    mem_used_mb  = round(float(m_used.group(1))  * scale, 1)

        mem_pct = round(mem_used_mb / mem_total_mb * 100.0, 1) if mem_total_mb > 0 else 0.0
        return cpu_pct, mem_pct, mem_used_mb, mem_total_mb

    except Exception:
        return 0.0, 0.0, 0.0, 0.0


@app.route('/status', methods=['GET'])
def status():
    cpu_pct, mem_pct, mem_used_mb, mem_total_mb = _parse_top()
    return jsonify({
        'success': True,
        'data': {
            'node_id':       NODE_ID,
            'status':        'busy' if _current_job_id else 'idle',
            'current_job_id': _current_job_id,
            'cpu_percent':   cpu_pct,
            'mem_percent':   mem_pct,
            'mem_used_mb':   mem_used_mb,
            'mem_total_mb':  mem_total_mb,
        },
        'error': None,
    })


# Phase 2 將實作 /run endpoint
@app.route('/run', methods=['POST'])
def run():
    return jsonify({
        'success': False,
        'data': None,
        'error': {'code': 'NOT_IMPLEMENTED', 'message': 'Phase 2 pending'},
    }), 501


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
