"""Main compute worker — runs PBS MAPF simulation and returns a GIF."""
import json
import os
import sys
import time

import requests

from .simulation import run_simulation
from .render import render_gif


def _callback(web_url, job_id, gif_bytes, stats, elapsed_sec):
    for delay in [1, 2, 4]:
        try:
            resp = requests.post(
                f"{web_url}/api/jobs/{job_id}/complete",
                files={'gif': ('result.gif', gif_bytes, 'image/gif')},
                data={'stats': json.dumps(stats), 'elapsed_sec': str(elapsed_sec)},
                timeout=30,
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

    map_grid = job['map_grid']
    products = job.get('products', {})
    num_agents = int(job.get('num_agents', 10))
    list_size = int(job.get('list_size', 3))
    max_steps = int(job.get('max_steps', 200))
    seed = int(job.get('seed', 42))

    t0 = time.time()
    frames, stats = run_simulation(map_grid, products, num_agents, list_size, max_steps, seed)
    gif_bytes = render_gif(map_grid, frames, products)
    elapsed = round(time.time() - t0, 2)

    _callback(web_url, job_id, gif_bytes, stats, elapsed)


if __name__ == '__main__':
    main()
