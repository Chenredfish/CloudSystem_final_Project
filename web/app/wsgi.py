import json
import sys
import threading

sys.path.insert(0, '/var/www/app')

from db import init_db
import dispatcher as disp
from routes import jobs as jobs_routes
from routes import nodes as nodes_routes

init_db()

# One background scanner thread per daemon process (mod_wsgi daemon mode)
threading.Thread(target=disp.background_scanner, daemon=True, name='dispatcher').start()


def _json_resp(start_response, code, data=None, error=None):
    body = json.dumps({'success': error is None, 'data': data, 'error': error}).encode()
    texts = {200: '200 OK', 404: '404 Not Found', 405: '405 Method Not Allowed'}
    start_response(texts.get(code, str(code)), [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(body))),
    ])
    return [body]


def application(environ, start_response):
    method = environ.get('REQUEST_METHOD', 'GET').upper()
    path_info = environ.get('PATH_INFO', '/')

    parts = [p for p in path_info.split('/') if p]

    if not parts:
        return _json_resp(start_response, 200, data='web service running')

    if parts[0] == 'jobs':
        return jobs_routes.handle(environ, start_response, parts, method)

    if parts[0] == 'nodes':
        return nodes_routes.handle(environ, start_response, parts, method)

    return _json_resp(start_response, 404, error={'code': 'NOT_FOUND', 'message': 'Endpoint not found'})
