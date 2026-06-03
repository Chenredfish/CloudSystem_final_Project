import cgi
import json
import os
import time
import uuid

from db import (
    IMAGE_DIR,
    cancel_job,
    create_job,
    get_all_jobs,
    get_job,
    save_job_result,
    upsert_node,
)
import dispatcher as disp

REQUIRED_CREATE_FIELDS = ['map_grid', 'products', 'num_agents', 'seed']

_STATUS_TEXT = {
    200: '200 OK',
    201: '201 Created',
    400: '400 Bad Request',
    404: '404 Not Found',
    409: '409 Conflict',
    500: '500 Internal Server Error',
}


def _json_resp(start_response, code, data=None, error=None):
    body = json.dumps({'success': error is None, 'data': data, 'error': error}).encode()
    start_response(_STATUS_TEXT.get(code, str(code)), [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(body))),
    ])
    return [body]


def _parse_json_body(environ):
    try:
        length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        return json.loads(environ['wsgi.input'].read(length))
    except Exception:
        return {}


def handle(environ, start_response, parts, method):
    if len(parts) == 1:
        if method == 'GET':
            return _list_jobs(environ, start_response)
        if method == 'POST':
            return _create_job(environ, start_response)
    elif len(parts) == 2:
        if method == 'DELETE':
            return _cancel_job(environ, start_response, parts[1])
    elif len(parts) == 3:
        job_id, action = parts[1], parts[2]
        if action == 'image' and method == 'GET':
            return _get_image(environ, start_response, job_id)
        if action == 'complete' and method == 'POST':
            return _complete_job(environ, start_response, job_id)
    return _json_resp(start_response, 404, error={'code': 'NOT_FOUND', 'message': 'Not found'})


def _list_jobs(environ, start_response):
    return _json_resp(start_response, 200, data=get_all_jobs())


def _create_job(environ, start_response):
    body = _parse_json_body(environ)
    missing = [f for f in REQUIRED_CREATE_FIELDS if f not in body]
    if missing:
        return _json_resp(start_response, 400, error={
            'code': 'MISSING_FIELDS',
            'message': f"Missing: {', '.join(missing)}",
        })
    job_id = str(uuid.uuid4())
    create_job(
        id=job_id,
        map_grid=body['map_grid'],
        products=body['products'],
        num_agents=int(body['num_agents']),
        list_size=int(body.get('list_size', 4)),
        max_steps=int(body.get('max_steps', 200)),
        algorithm=body.get('algorithm', 'PBS'),
        seed=int(body['seed']),
    )
    disp.try_dispatch()
    return _json_resp(start_response, 201, data={'job_id': job_id})


def _cancel_job(environ, start_response, job_id):
    if cancel_job(job_id):
        return _json_resp(start_response, 200, data={'job_id': job_id})
    return _json_resp(start_response, 409, error={
        'code': 'CANNOT_CANCEL',
        'message': 'Job is not in queued state',
    })


def _get_image(environ, start_response, job_id):
    job = get_job(job_id)
    if not job or not job.get('result_gif_path'):
        return _json_resp(start_response, 404, error={
            'code': 'NOT_READY', 'message': 'Image not available',
        })
    gif_path = job['result_gif_path']
    if not os.path.exists(gif_path):
        return _json_resp(start_response, 404, error={
            'code': 'FILE_NOT_FOUND', 'message': 'GIF file missing on disk',
        })
    with open(gif_path, 'rb') as f:
        data = f.read()
    start_response('200 OK', [
        ('Content-Type', 'image/gif'),
        ('Content-Length', str(len(data))),
        ('Content-Disposition', f'inline; filename="{job_id}.gif"'),
    ])
    return [data]


def _complete_job(environ, start_response, job_id):
    job = get_job(job_id)
    if not job:
        return _json_resp(start_response, 404, error={
            'code': 'NOT_FOUND', 'message': 'Job not found',
        })

    form = cgi.FieldStorage(
        fp=environ['wsgi.input'],
        environ=environ,
        keep_blank_values=True,
    )

    gif_path = None
    gif_item = form['gif'] if 'gif' in form else None
    if gif_item is not None and hasattr(gif_item, 'file'):
        gif_bytes = gif_item.file.read()
        gif_path = os.path.join(IMAGE_DIR, f'{job_id}.gif')
        with open(gif_path, 'wb') as f:
            f.write(gif_bytes)

    stats_str = form.getvalue('stats', '{}')
    try:
        stats = json.loads(stats_str)
    except Exception:
        stats = {}

    elapsed_sec = 0.0
    try:
        elapsed_sec = float(form.getvalue('elapsed_sec', '0') or '0')
    except (TypeError, ValueError):
        pass

    save_job_result(job_id, gif_path, stats, elapsed_sec)

    node_id = job.get('node_id')
    if node_id:
        upsert_node(node_id, 'idle', None, time.time())

    disp.try_dispatch()
    return _json_resp(start_response, 200, data={'job_id': job_id})
