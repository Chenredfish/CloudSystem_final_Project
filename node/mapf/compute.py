"""Stub compute worker — sleep 15s, produce a fake GIF, callback to web."""
import io
import json
import os
import sys
import time

import requests
from PIL import Image


def _callback(web_url, job_id, gif_bytes, stats, elapsed_sec):
    for delay in [1, 2, 4]:
        try:
            resp = requests.post(
                f"{web_url}/api/jobs/{job_id}/complete",
                files={'gif': ('result.gif', gif_bytes, 'image/gif')},
                data={'stats': json.dumps(stats), 'elapsed_sec': str(elapsed_sec)},
                timeout=10,
            )
            if resp.ok:
                return
        except Exception:
            pass
        time.sleep(delay)


def main():
    job = json.loads(sys.argv[1])
    job_id = job['job_id']
    web_url = os.environ.get('WEB_CALLBACK_URL', 'http://web:80')

    time.sleep(15)

    img = Image.new('RGB', (200, 200), color=(30, 144, 255))
    buf = io.BytesIO()
    img.save(buf, format='GIF')
    gif_bytes = buf.getvalue()

    stats = {
        'agents': job.get('num_agents', 1),
        'makespan': 0,
        'sum_of_costs': 0,
        'stub': True,
    }
    _callback(web_url, job_id, gif_bytes, stats, 15.0)


if __name__ == '__main__':
    main()
