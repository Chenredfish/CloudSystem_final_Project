import json
import time

from db import get_all_nodes, upsert_node

_STATUS_TEXT = {200: '200 OK', 404: '404 Not Found'}


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
    if len(parts) == 1 and method == 'GET':
        return _json_resp(start_response, 200, data=get_all_nodes())
    if len(parts) == 3 and parts[2] == 'heartbeat' and method == 'POST':
        return _heartbeat(environ, start_response, parts[1])
    return _json_resp(start_response, 404, error={'code': 'NOT_FOUND', 'message': 'Not found'})


def _heartbeat(environ, start_response, node_id):
    body = _parse_json_body(environ)
    status = body.get('status', 'idle')
    current_job_id = body.get('current_job_id')
    cpu_percent = float(body.get('cpu_percent', 0.0))
    mem_percent = float(body.get('mem_percent', 0.0))
    upsert_node(node_id, status, current_job_id, time.time(), cpu_percent, mem_percent)
    return _json_resp(start_response, 200, data={'node_id': node_id})
