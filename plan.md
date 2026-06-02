# 實作規劃

> 截止日：2026-06-10 下課前  
> 必要功能全數完成後再進行加分功能

---

## 零、進度概覽

| Phase | 內容 | 狀態 |
|-------|------|------|
| 1 | 基礎設施（Docker、SQLite、容器骨架） | ✅ 完成 |
| 2 | 計算節點（/run、Heartbeat、compute.py stub） | 🔲 待實作 |
| 3 | Web 後端 API（全部 endpoint、Dispatcher） | 🔲 待實作 |
| 4 | MAPF 計算引擎（PBS、GIF 產出） | 🔲 待實作 |
| 5 | 前端（Canvas 編輯器、輪詢顯示） | 🔲 待實作 |
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

#### 驗證指令

```bash
docker compose up --build
docker exec web python3 -c "
import sqlite3; c=sqlite3.connect('/data/jobs.db')
print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")])
"
# → ['jobs', 'nodes']

curl http://localhost:8080/api
# → {"success": true, "data": "web service running", "error": null}

curl http://localhost:8080
# → 佔位前端頁面
```

---

### Phase 2　計算節點 Flask 服務

**目標：** 節點可以接收工作、背景執行假計算、定期回報心跳。

#### 2-1　node_app.py — POST /run

- [ ] 驗證必填欄位（`job_id`、`map_grid`、`products`、`num_agents`、`seed`）
- [ ] 設定 `_current_job_id`（執行緒安全）
- [ ] `subprocess.Popen(['python3', 'mapf/compute.py', job_json])` 啟動背景計算
- [ ] 立即回傳 HTTP 202 + `{"success": true}`

> `/status` 已於 Phase 1 完成（top 解析、回傳 CPU/MEM/current_job_id）

#### 2-2　Heartbeat background thread

- [ ] `threading.Thread(target=_heartbeat_loop, daemon=True).start()` 在 app 啟動時執行
- [ ] 每 10 秒：`POST {WEB_CALLBACK_URL}/api/nodes/{NODE_ID}/heartbeat`，body 含 `status`、`current_job_id`
- [ ] 使用 `try/except` 忽略網路錯誤（web container 可能尚未就緒）

#### 2-3　mapf/compute.py（暫時版）

- [ ] `sys.argv[1]` 讀取 job JSON 字串
- [ ] `time.sleep(15)` 模擬計算
- [ ] 產生純色假 GIF（用 Pillow，只需一幀）
- [ ] 回呼：`POST {WEB_CALLBACK_URL}/api/jobs/{job_id}/complete`（multipart，帶 GIF）
- [ ] 指數退避重試：1s → 2s → 4s（三次失敗則放棄）

#### 驗證指令

```bash
# 需先完成 Phase 3 才能做 end-to-end 測試
# 但可單獨驗證 /status：
curl http://localhost:8080       # 前端佔位（Phase 1）
# node 的 /status 在 Docker 內部，由 Phase 3 完成後透過 web 觸發
```

---

### Phase 3　Web 後端 API

**目標：** 所有 REST API endpoint 正常運作，Dispatcher 可以分派工作。

#### 3-1　db.py CRUD 函式

- [ ] `create_job(id, map_grid, products, ...)` → INSERT
- [ ] `get_all_jobs()` → SELECT 全部，JSON 欄位反序列化
- [ ] `get_job(id)` → SELECT WHERE id
- [ ] `update_job_status(id, status, node_id=None, dispatched_at=None)`
- [ ] `cancel_job(id)` → 僅當 `status='queued'` 才更新為 `cancelled`，否則回傳 False
- [ ] `save_job_result(id, gif_path, stats, elapsed_sec)` → UPDATE
- [ ] `upsert_node(node_id, status, current_job_id, last_heartbeat)`
- [ ] `get_all_nodes()` → SELECT 全部
- [ ] `get_idle_nodes()` → SELECT WHERE status='idle'

#### 3-2　wsgi.py 路由

```python
# PATH_INFO 為 /api 後的路徑（Apache WSGIScriptAlias 已剝除 /api 前綴）
# /jobs           → routes/jobs.py
# /jobs/<id>      → routes/jobs.py
# /jobs/<id>/...  → routes/jobs.py
# /nodes          → routes/nodes.py
# /nodes/<id>/... → routes/nodes.py
```

- [ ] 解析 `PATH_INFO`、`REQUEST_METHOD`，路由到對應 handler
- [ ] 統一回傳格式：`{"success": bool, "data": ..., "error": {"code":..., "message":...}}`
- [ ] 啟動 dispatcher background thread（`threading.Thread(daemon=True)`）

#### 3-3　routes/jobs.py

| Endpoint | 邏輯重點 |
|----------|---------|
| `POST /api/jobs` | 驗證欄位 → UUID v4 → `create_job()` → `try_dispatch()` → 回傳 job_id |
| `GET /api/jobs` | `get_all_jobs()` → 回傳陣列 |
| `DELETE /api/jobs/<id>` | `cancel_job()` → False 時回傳 409 |
| `GET /api/jobs/<id>/image` | 讀 `result_gif_path`，以 binary 回傳 image/gif |
| `POST /api/jobs/<id>/complete` | multipart → 儲存 GIF → `save_job_result()` → 更新 node idle → `try_dispatch()` |

#### 3-4　routes/nodes.py

- [ ] `GET /api/nodes`：`get_all_nodes()` → 回傳陣列
- [ ] `POST /api/nodes/<id>/heartbeat`：`upsert_node()` 更新 `last_heartbeat = time.time()`、`consecutive_miss = 0`

#### 3-5　dispatcher.py

```python
def try_dispatch():
    # BEGIN IMMEDIATE TRANSACTION
    # 取 queued job（oldest first）+ idle node
    # UPDATE job → running、UPDATE node → busy
    # COMMIT
    # HTTP POST node /run（帶完整 job 參數 JSON）
    # 若 HTTP 失敗：UPDATE job → queued, retry_count+1
    #   retry_count >= MAX_RETRY → failed

def background_scanner():
    # 每 DISPATCH_INTERVAL 秒：
    #   偵測 last_heartbeat 超過 NODE_TIMEOUT_SEC → 標記 offline, consecutive_miss+1
    #   偵測 running job 但 node offline → UPDATE job → queued（重排）
    #   呼叫 try_dispatch()
```

- [ ] `try_dispatch()` 實作（含 BEGIN IMMEDIATE）
- [ ] `background_scanner()` daemon thread
- [ ] `try_dispatch()` 在 `POST /api/jobs` 與 `POST /api/jobs/<id>/complete` 後觸發

#### 驗證

```bash
# 提交一個工作（需先手動建一個簡單 map_grid）
curl -X POST http://localhost:8080/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"map_grid":[[0,0],[0,0]],"products":{},"num_agents":2,"list_size":1,"max_steps":50,"algorithm":"PBS","seed":42}'

# 查詢工作狀態
curl http://localhost:8080/api/jobs

# 查詢節點狀態
curl http://localhost:8080/api/nodes

# 確認：3 個工作出去後第 4 個排隊
# 確認：DELETE 可取消排隊工作
```

---

### Phase 4　MAPF 計算引擎

**目標：** `compute.py` 能執行真正的 PBS MAPF 並產出 GIF。

#### 4-1　astar.py　Time-Expanded A*

```python
def tea_star(grid, start, goal, reserved, max_steps):
    # 在 (x, y, t) 三維空間搜索
    # reserved: set of (x, y, t)
    # 回傳: list of (x, y)，長度為抵達時間步數
```

- [ ] priority queue（heapq），狀態 = `(f, g, x, y, t)`
- [ ] 鄰居：上下左右 + 等待原地（5 種動作）
- [ ] 邊界 + 牆壁 + reserved 衝突檢查
- [ ] 抵達 goal 後回傳完整路徑

#### 4-2　pbs.py　Priority-Based Search

- [ ] 按優先序（剩餘購物清單長度，長的優先）依序規劃每個 agent
- [ ] 已規劃 agent 路徑加入 `reserved` 集合
- [ ] 庫存事件：到達貨架 → 庫存 > 0 則取走，否則更新目標重規劃
- [ ] 記錄每時步所有 agent 位置 → `frames: list[dict]`

#### 4-3　simulation.py　模擬主控

- [ ] 依 `seed` 隨機產生每位顧客的購物清單（`list_size` 件）
- [ ] 貪婪 TSP 排序目標（先去最近商品）
- [ ] 呼叫 `pbs()` 執行模擬
- [ ] 回傳 `frames` 與 `stats`（購買率、平均完成步數等）

#### 4-4　render.py　視覺化

- [ ] 用 `PIL.Image` 繪製每幀（格子地圖 + agent 圓點 + 貨架標籤）
- [ ] 顏色：黑=牆、棕=貨架、黃=收銀台、彩色圓=顧客、紅X=售罄
- [ ] 每幀 100ms，合成 GIF（最多 200 幀）

#### 4-5　compute.py（正式版，取代 stub）

- [ ] `sys.argv[1]` 讀取 job JSON
- [ ] 呼叫 `simulation.run()` → `render.render_gif()`
- [ ] callback multipart POST，指數退避重試
- [ ] node/requirements.txt 加入 `numpy` 與 `Pillow`

#### 驗證

```bash
# 在 node container 內單機執行
docker exec node1 python3 mapf/compute.py '{"job_id":"test","map_grid":[...],...}'
# 應在 15–35 秒內產出 GIF
```

---

### Phase 5　前端

**目標：** 使用者可在瀏覽器設計地圖、提交工作、監看進度、查看 GIF。

#### 5-1　index.html 版面（三區塊）

- [ ] 商場編輯區（Canvas + 工具列 + 參數輸入）
- [ ] 節點狀態區（三欄：node1/2/3，各顯示 CPU/MEM/狀態）
- [ ] 工作列表區（表格：ID、顧客數、狀態、節點、耗時、操作、GIF 縮圖）

#### 5-2　app.js 商場 Canvas 編輯器

- [ ] 60×60 格子，依螢幕大小縮放
- [ ] 工具列：畫牆 / 畫貨架 / 放收銀台 / 清除；拖曳批次繪製
- [ ] 點擊貨架格 → 輸入商品名稱與庫存數量
- [ ] 「送出」按鈕：序列化 `map_grid`、`products` → `POST /api/jobs`

#### 5-3　app.js 輪詢更新

```javascript
async function poll() {
    const [jobs, nodes] = await Promise.all([
        fetch('/api/jobs').then(r => r.json()),
        fetch('/api/nodes').then(r => r.json()),
    ])
    renderJobTable(jobs.data)
    renderNodeStatus(nodes.data)
}
setInterval(poll, 3000)
```

- [ ] 工作狀態顏色徽章（排隊中 / 執行中 / 完成 / 失敗 / 取消）
- [ ] 執行中顯示 `node_id`
- [ ] 完成工作：GIF 縮圖，點擊展開放大
- [ ] 排隊中工作：「取消」按鈕 → `DELETE /api/jobs/<id>`

#### 驗證

```bash
# 在瀏覽器開啟 http://localhost:8080
# 設計地圖 → 送出 → 等待 → GIF 出現
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

*最後更新：Phase 1 完成（2026-05-27）*
