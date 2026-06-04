# 實作規劃

> 截止日：2026-06-10 下課前  
> 必要功能全數完成後再進行加分功能

---

## 零、進度概覽

| Phase | 內容 | 狀態 |
|-------|------|------|
| 1 | 基礎設施（Docker、SQLite、容器骨架） | ✅ 完成 |
| 2 | 計算節點（/run、Heartbeat、compute.py stub） | ✅ 完成 |
| 3 | Web 後端 API（全部 endpoint、Dispatcher） | ✅ 完成 |
| 4 | MAPF 計算引擎（PBS、GIF 產出） | ✅ 完成 |
| 5 | 前端（Canvas 編輯器、輪詢顯示） | ✅ 完成 |
| 6 | 整合測試 | 🔲 待實作 |

---

## 一、專案目錄結構

```
CloudSystem_final_Project/
│
├── docker-compose.yml          ← 四容器統一設定（環境變數直接寫在此）
├── data/
│   ├── .gitkeep                ← 確保 data/ 存在於 repo
│   ├── jobs.db                 ← SQLite 資料庫（runtime 自動建立，gitignore）
│   └── images/                 ← 結果 GIF（runtime 自動建立，gitignore）
│
├── web/                        ← Container 1（Apache + Python）
│   ├── Dockerfile
│   ├── requirements.txt        ← requests
│   ├── apache/
│   │   └── app.conf            ← VirtualHost：WSGIDaemonProcess、/api → wsgi.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── wsgi.py             ← WSGI 進入點，啟動時呼叫 init_db() 與 dispatcher
│   │   ├── db.py               ← SQLite 連線、Schema 初始化、CRUD
│   │   ├── dispatcher.py       ← 分派邏輯 + 背景掃描 thread  ← Phase 3
│   │   └── routes/
│   │       ├── jobs.py         ← /api/jobs 相關 endpoint      ← Phase 3
│   │       └── nodes.py        ← /api/nodes 相關 endpoint     ← Phase 3
│   └── frontend/
│       ├── index.html          ← 單頁面（Canvas + 狀態面板 + 工作列表）← Phase 5
│       └── app.js              ← 前端邏輯（輪詢、Canvas、送出）       ← Phase 5
│
├── node/                       ← Container 2/3/4（共用同一 image）
│   ├── Dockerfile
│   ├── requirements.txt        ← flask, gunicorn, requests（Phase 4 加 numpy, Pillow）
│   ├── node_app.py             ← Flask 主程式（/run、/status）
│   └── mapf/                   ← Phase 4
│       ├── astar.py
│       ├── pbs.py
│       ├── simulation.py
│       ├── render.py
│       └── compute.py
```

---

## 二、實作階段

---

### Phase 1　基礎設施　✅ 完成

**目標：** `docker compose up` 後四個容器全部啟動，資料庫 Schema 正確建立。

#### 1-1　docker-compose.yml

- [x] 定義 `web` service（build: ./web，port: 8080:80）
- [x] 定義 `node1 / node2 / node3` service（build: ./node，env: NODE_ID）
- [x] 掛載 `./data:/data` volume 給 web container
- [x] 環境變數直接寫在 compose（NODE_URLS、DB_PATH、IMAGE_DIR 等）
- [x] 設定統一 `cluster` bridge network

#### 1-2　資料庫初始化（db.py）

- [x] `init_db()`：WAL mode、建立 `jobs` 和 `nodes` 資料表
- [x] `CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)`
- [x] 自動建立 `IMAGE_DIR`（/data/images）

#### 1-3　Apache + mod_wsgi 骨架

- [x] `web/apache/app.conf`：VirtualHost、WSGIDaemonProcess（2 proc × 5 threads）
- [x] `WSGIScriptAlias /api` → wsgi.py
- [x] wsgi.py 啟動時呼叫 `init_db()`

#### 1-4　Node 容器骨架

- [x] `node/Dockerfile`：python:3.11-slim + procps + gunicorn
- [x] `node/node_app.py`：`GET /status`（top 解析），`POST /run`（stub 回 501）

#### 驗證結果　✅ 已驗證

```powershell
# 啟動（日後標準指令）
docker compose up --build -d

# 確認容器狀態
docker ps   # → web、node1/2/3 均 Up

# 確認 DB schema（PowerShell 用 here-string 避免引號衝突）
@'
import sqlite3
c = sqlite3.connect('/data/jobs.db')
print([r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")])
'@ | docker exec -i web python3
# → ['jobs', 'nodes']

# 確認 web API
curl http://localhost:8080/api
# → {"success": true, "data": "web service running", "error": null}

# 確認 node /status（從 web container 內呼叫）
docker exec web curl -s http://node1:5000/status
# → {"success":true,"data":{"node_id":"node1","status":"idle","cpu_percent":...}}
```

> **注意：** 若出現容器名稱衝突，先執行 `docker compose down` 再 `docker rm -f node1 node2 node3 web`，然後重新 `docker compose up --build -d`。


curl http://localhost:8080
# → 佔位前端頁面
```

---

### Phase 2　計算節點 Flask 服務　✅ 完成

**目標：** 節點可以接收工作、背景執行假計算、定期回報心跳。

#### 2-1　node_app.py — POST /run

- [x] 驗證必填欄位（`job_id`、`map_grid`、`products`、`num_agents`、`seed`）
- [x] 執行緒安全 job 狀態（`_job_lock` + `_current_job` dict）
- [x] `subprocess.Popen(['python3', 'mapf/compute.py', job_json])` 啟動背景計算
- [x] monitor thread 等待 process 結束後清除狀態
- [x] 立即回傳 HTTP 202 + `{"success": true}`；busy 時回傳 409

> `/status` 已於 Phase 1 完成（top 解析、回傳 CPU/MEM/current_job_id）

#### 2-2　Heartbeat background thread

- [x] `os.register_at_fork(after_in_child=_start_heartbeat)` + 模組層啟動（相容 Gunicorn fork）
- [x] 每 10 秒：`POST {WEB_CALLBACK_URL}/api/nodes/{NODE_ID}/heartbeat`，body 含 `status`、`current_job_id`
- [x] `try/except` 忽略網路錯誤（Phase 3 完成前 web endpoint 尚不存在）

#### 2-3　mapf/compute.py（暫時版）

- [x] `sys.argv[1]` 讀取 job JSON 字串
- [x] `time.sleep(15)` 模擬計算
- [x] 產生純色假 GIF（Pillow，單幀 200×200）
- [x] 回呼：`POST {WEB_CALLBACK_URL}/api/jobs/{job_id}/complete`（multipart，帶 GIF）
- [x] 指數退避重試：1s → 2s → 4s（三次失敗則放棄）

#### 驗證結果　✅ 已驗證

```powershell
# 送出假工作
docker exec web curl -s -X POST http://node1:5000/run \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test-001","map_grid":"10x10","products":"[]","num_agents":2,"seed":42}'
# → {"success":true,"data":{"job_id":"test-001"},...}  HTTP 202

# 確認 busy 狀態
docker exec web curl -s http://node1:5000/status
# → {"data":{"current_job_id":"test-001","status":"busy",...}}

# 確認拒絕重複派工
docker exec web curl -s -X POST http://node1:5000/run ...
# → {"error":{"code":"NODE_BUSY",...},"success":false}  HTTP 409

# 15 秒後確認自動回到 idle
docker exec web curl -s http://node1:5000/status
# → {"data":{"current_job_id":null,"status":"idle",...}}
```

---

### Phase 3　Web 後端 API　✅ 完成

**目標：** 所有 REST API endpoint 正常運作，Dispatcher 可以分派工作。

#### 3-1　db.py CRUD 函式

- [x] `create_job(id, map_grid, products, ...)` → INSERT
- [x] `get_all_jobs()` → SELECT 全部，JSON 欄位反序列化
- [x] `get_job(id)` → SELECT WHERE id
- [x] `update_job_status(id, status, node_id=None, dispatched_at=None)`
- [x] `cancel_job(id)` → 僅當 `status='queued'` 才更新為 `cancelled`，否則回傳 False
- [x] `save_job_result(id, gif_path, stats, elapsed_sec)` → UPDATE
- [x] `upsert_node(node_id, status, current_job_id, last_heartbeat)`
- [x] `get_all_nodes()` → SELECT 全部
- [x] `get_idle_nodes()` → SELECT WHERE status='idle'

#### 3-2　wsgi.py 路由

```python
# PATH_INFO 為 /api 後的路徑（Apache WSGIScriptAlias 已剝除 /api 前綴）
# /jobs           → routes/jobs.py
# /jobs/<id>      → routes/jobs.py
# /jobs/<id>/...  → routes/jobs.py
# /nodes          → routes/nodes.py
# /nodes/<id>/... → routes/nodes.py
```

- [x] 解析 `PATH_INFO`、`REQUEST_METHOD`，路由到對應 handler
- [x] 統一回傳格式：`{"success": bool, "data": ..., "error": {"code":..., "message":...}}`
- [x] 啟動 dispatcher background thread（`threading.Thread(daemon=True)`）

#### 3-3　routes/jobs.py

| Endpoint | 邏輯重點 |
|----------|---------|
| `POST /api/jobs` | 驗證欄位 → UUID v4 → `create_job()` → `try_dispatch()` → 回傳 job_id |
| `GET /api/jobs` | `get_all_jobs()` → 回傳陣列 |
| `DELETE /api/jobs/<id>` | `cancel_job()` → False 時回傳 409 |
| `GET /api/jobs/<id>/image` | 讀 `result_gif_path`，以 binary 回傳 image/gif |
| `POST /api/jobs/<id>/complete` | multipart → 儲存 GIF → `save_job_result()` → 更新 node idle → `try_dispatch()` |

#### 3-4　routes/nodes.py

- [x] `GET /api/nodes`：`get_all_nodes()` → 回傳陣列
- [x] `POST /api/nodes/<id>/heartbeat`：`upsert_node()` 更新 `last_heartbeat = time.time()`、`consecutive_miss = 0`

#### 3-5　dispatcher.py

- [x] `try_dispatch()` 實作（含 BEGIN IMMEDIATE）
- [x] `background_scanner()` daemon thread
- [x] `try_dispatch()` 在 `POST /api/jobs` 與 `POST /api/jobs/<id>/complete` 後觸發

> **注意：** `cgi.FieldStorage` 在 Python 3.10 中不支援 `bool()` 轉換與 `.get()` 方法，需用 `form['key']` 搭配 `is not None` 判斷。

#### 驗證結果　✅ 已驗證

```powershell
# 查詢節點（heartbeat 自動註冊）
Invoke-RestMethod -Uri "http://localhost:8080/api/nodes" -Method GET
# → node1/2/3 均為 idle，last_heartbeat 正常更新

# 提交工作
Invoke-RestMethod -Uri "http://localhost:8080/api/jobs" -Method POST `
  -ContentType "application/json" `
  -Body '{"map_grid":[[0,0],[0,0]],"products":{"apple":5},"num_agents":2,"seed":42}'
# → {"success":true,"data":{"job_id":"..."},...}  HTTP 201

# 查詢工作狀態（約 15 秒後變 done）
Invoke-RestMethod -Uri "http://localhost:8080/api/jobs" -Method GET
# → status: running → done，result_gif_path 與 stats 正確寫入

# 同時提交 4 個工作，確認 3 running + 1 queued
1..4 | ForEach-Object { POST /api/jobs }
# → 前 3 個分派到 node1/2/3，第 4 個 status=queued

# 取消排隊工作
Invoke-RestMethod -Uri "http://localhost:8080/api/jobs/<id>" -Method DELETE
# → {"success":true}，status 變 cancelled

# 確認 running/done 工作無法取消
# → HTTP 409 {"error":{"code":"CANNOT_CANCEL",...}}

# 從容器內確認 GIF 取回
docker exec web curl -sI "http://localhost:80/api/jobs/<id>/image"
# → HTTP 200，Content-Type: image/gif
```

---

### Phase 4　MAPF 計算引擎　✅ 完成

**目標：** `compute.py` 能執行真正的 PBS MAPF 並產出 GIF。

#### 已建立的檔案

- `node/mapf/astar.py` — Time-Expanded A*（heapq，5 動作，reserved 衝突檢查）
- `node/mapf/pbs.py` — Priority-Based Search（依 agent 順序依序規劃，reserved 累積）
- `node/mapf/simulation.py` — 模擬主控（seed 購物清單、庫存事件、收銀台結帳）
- `node/mapf/render.py` — Pillow GIF（CELL=9px，彩色 agent 圓點，售罄紅 X，max 300 幀）
- `node/mapf/compute.py` — 正式版，取代 stub（`python3 -m mapf.compute`）
- `node/node_app.py` — 改為 `python3 -m mapf.compute` 啟動子程序

#### 驗證結果（2026-06-05）

- 5 agents，20×20 地圖，list_size=2，max_steps=120
- makespan=73，all done，elapsed=1.72s
- GIF89a，23 914 bytes，stub=false ✅

#### 實作說明

- [x] Time-Expanded A*：heapq，(f, g, r, c, t)，5 種動作（等待+上下左右）
- [x] PBS：固定優先序（agent 索引），reserved 累積，失敗 fallback = 原地等待
- [x] 購物清單：`random.Random(seed)` 從貨架座標取樣
- [x] 庫存事件：agent 抵達貨架時 in-situ 扣減，售罄跳過重新分配目標
- [x] GIF：每幀 100ms，最多採 300 幀（stride 降採樣）

---

### Phase 5　前端　✅ 完成

**目標：** 使用者可在瀏覽器設計地圖、提交工作、監看進度、查看 GIF。

#### 5-1　index.html 版面（三區塊）

- [x] 方案選擇列（小超市 / 中型商場 / 大型賣場，含各自預設參數）
- [x] 商場編輯區（Canvas + 工具列 + 參數輸入）
- [x] 節點狀態區（node1/2/3，各顯示 idle/busy/offline 狀態與心跳時間）
- [x] 工作列表區（表格：ID、狀態、提交時間、節點、耗時、操作）

#### 5-2　app.js 商場 Canvas 編輯器

- [x] 60×60 格子（每格 9px，共 540×540 px）
- [x] 工具列：畫牆 / 畫貨架 / 放收銀台 / 清除；拖曳批次繪製，右鍵直接清除
- [x] 貨架自動產生 `products` dict（每格 stock=3，商品名 A/B/C…）
- [x] 「送出」按鈕：序列化 `map_grid`、`products` → `POST /api/jobs`
- [x] `↺ 重置參數` 按鈕：還原目前方案的預設值

#### 5-3　三組預設方案

| 方案 | 地圖特徵 | 顧客 | 清單 | 步數 | 種子 |
|------|---------|------|------|------|------|
| 小超市 | 3 排 × 8 組 2×2 貨架，寬走道，單排收銀台 | 10 | 3 | 150 | 42 |
| 中型商場（預設） | 7 排 × 11 組 2×2 貨架，平衡密度 | 20 | 4 | 200 | 42 |
| 大型賣場 | 兩翼各 6 組 3 寬貨架，9 格中央走道，雙排收銀台 | 35 | 5 | 300 | 99 |

#### 5-4　app.js 輪詢更新

- [x] `Promise.all([GET /api/jobs, GET /api/nodes])` 每 3 秒執行
- [x] 工作狀態顏色徽章（排隊中 / 執行中 / 完成 / 失敗 / 取消）
- [x] 執行中顯示 `node_id`
- [x] 完成工作：「查看動畫」開啟 Modal，顯示 GIF + stats（makespan、sum_of_costs 等）
- [x] 排隊中工作：「取消」按鈕 → `DELETE /api/jobs/<id>`
- [x] Toast 通知（提交成功 / 取消結果 / 錯誤訊息）

#### 驗證結果　✅ 已驗證

```powershell
# 前端首頁 HTTP 200
(Invoke-WebRequest -Uri "http://localhost:8080/" -UseBasicParsing).StatusCode   # → 200
(Invoke-WebRequest -Uri "http://localhost:8080/app.js" -UseBasicParsing).StatusCode  # → 200

# 提交工作（模擬前端 payload）
$r = Invoke-WebRequest -Uri "http://localhost:8080/api/jobs" -Method POST `
     -ContentType "application/json" -Body $body -UseBasicParsing
# → {"success":true,"data":{"job_id":"..."},...}

# 15 秒後查詢，status=done，GIF 可取得
(Invoke-WebRequest -Uri "http://localhost:8080/api/jobs/<id>/image").Headers['Content-Type']
# → image/gif
```

---

### Phase 6　整合測試

- [ ] 同時提交 4 個工作，確認排隊行為正確（3 個出去、1 個排隊）
- [ ] 取消排隊工作；確認 running / done 工作無法取消（回傳 409）
- [ ] `docker stop node1`，確認 35 秒後標記 offline、工作重排
- [ ] 恢復 node1（`docker start node1`），確認心跳恢復、重新接受工作
- [ ] `docker compose down && docker compose up`：工作狀態從 SQLite 正確恢復
- [ ] 確認各節點 CPU/MEM 數字即時更新

---

## 三、必要功能 vs 加分功能

### 必要功能（Phase 1–5 覆蓋）

| 功能 | 對應實作位置 |
|------|------------|
| 工作狀態監控（完成 / 執行中 / 排隊中） | dispatcher.py + 前端輪詢 |
| 執行中標明節點 | jobs 資料表 node_id 欄位 |
| CPU / 記憶體使用率顯示 | node /status endpoint + 前端 |
| 刪除排隊中工作 | DELETE /api/jobs/\<id\> |

### 加分功能（Phase 5 完成後視時間決定）

| 功能 | 難度 | 說明 |
|------|------|------|
| Heartbeat + Circuit Breaker | 低 | background_scanner 已規劃，Phase 2/3 一起實作 |
| 工作失效重試 | 低 | dispatcher 已設計 retry_count 欄位 |
| WHCA\* 升級 | 中 | node/mapf/ 新增 whca.py，前端加算法選項 |
| 多配置批次比較 | 中 | 前端一次提交多組 products，各自建 job |

---

## 四、各容器關鍵技術備忘

### Web container（Container 1）

```
Apache 設定（web/apache/app.conf）：
- WSGIDaemonProcess webapp processes=2 threads=5 python-path=/var/www/app
- WSGIProcessGroup webapp
- WSGIScriptAlias /api /var/www/app/wsgi.py
- DocumentRoot /var/www/app/frontend（靜態檔由 Apache 直接服務）
```

### Node container（Container 2/3/4）

```
Gunicorn：gunicorn --workers 2 --bind 0.0.0.0:5000 --timeout 120 node_app:app

重點：
- /run 必須立即回傳 202，計算透過 subprocess.Popen 背景執行
- Heartbeat thread 設為 daemon=True
```

### SQLite 分派交易

```python
conn.execute("BEGIN IMMEDIATE")
try:
    job  = conn.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY submitted_at LIMIT 1").fetchone()
    node = conn.execute("SELECT * FROM nodes WHERE status='idle' LIMIT 1").fetchone()
    if job and node:
        conn.execute("UPDATE jobs  SET status='running', node_id=?, dispatched_at=? WHERE id=?",
                     (node['node_id'], time.time(), job['id']))
        conn.execute("UPDATE nodes SET status='busy', current_job_id=? WHERE node_id=?",
                     (job['id'], node['node_id']))
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

---

*最後更新：Phase 5 完成（2026-06-03）*
