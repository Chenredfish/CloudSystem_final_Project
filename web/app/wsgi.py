import sys
sys.path.insert(0, '/var/www/app')

from db import init_db

# 每個 daemon process 啟動時初始化資料庫（CREATE IF NOT EXISTS，可重複呼叫）
init_db()


def application(environ, start_response):
    """
    WSGI 進入點。
    Apache WSGIScriptAlias /api 將請求轉入此函式，
    PATH_INFO 為 /api 之後的路徑（如 /jobs、/nodes）。
    Phase 3 將在此實作完整路由；Phase 1 僅回傳確認訊息。
    """
    body = b'{"success": true, "data": "web service running", "error": null}'
    start_response('200 OK', [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(body))),
    ])
    return [body]
