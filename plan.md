# 實作規劃

> 截止日：2026-06-10 下課前  
> 必要功能全數完成後再進行加分功能

---

## 一、專案目錄結構

```
CloudSystem_final_Project/
│
├── docker-compose.yml          ← 四容器統一設定
├── .env                        ← 環境變數（NODE_URLS、DB_PATH 等）
│
├── web/                        ← Container 1（Apache + Python）
│   ├── Dockerfile
│   ├── apache/
│   │   ├── httpd.conf          ← Apache 主設定（監聽 port、靜態檔）
│   │   └── wsgi.conf           ← mod_wsgi daemon 設定
│   ├── app/
│   │   ├── wsgi.py             ← WSGI 進入點，啟動 dispatcher thread
│   │   ├── db.py               ← SQLite 連線、Schema 初始化、CRUD
│   │   ├── dispatcher.py       ← 分派邏輯 + 背景掃描 thread
│   │   └── routes/
│   │       ├── jobs.py         ← /api/jobs 相關 endpoint
│   │       └── nodes.py        ← /api/nodes 相關 endpoint
│   └── frontend/
│       ├── index.html          ← 單頁面（Canvas 編輯器 + 狀態面板 + 工作列表）
│       └── app.js              ← 前端邏輯（輪詢、Canvas、送出）
│
├── node/                       ← Container 2/3/4（共用同一 image）
│   ├── Dockerfile
│   ├── requirements.txt        ← flask, gunicorn, pillow, numpy
│   ├── node_app.py             ← Flask 主程式（/run、/status）
│   └── mapf/
│       ├── astar.py            ← Time-Expanded A*（核心路徑搜尋）
│       ├── pbs.py              ← Priority-Based Search（多 agent 協調）
│       ├── simulation.py       ← 模擬主控：multi-waypoint、庫存事件
│       ├── render.py           ← PNG 序列產生 + GIF 合成
│       └── compute.py          ← subprocess 進入點（接收 JSON 參數）
│
└── data/                       ← Docker volume 掛載
    ├── jobs.db                 ← SQLite 資料庫（自動建立）
    └── images/                 ← 結果 GIF 存放位置
```

---

## 二、實作階段

---

### Phase 1　基礎設施

**目標：** `docker compose up` 後四個容器全部啟動、互相可以 ping 通，資料庫 Schema 正確建立。

#### 1-1　docker-compose.yml

```yaml
# 四個 service：web, node1, node2, node3
# 共用同一 node image，以 NODE_ID 環境變數區別
# volumes：./data:/data
# network：bridge，hostnames = service name
```

- [ ] 定義 `web` service（build: ./web，port: 8080:80）
- [ ] 定義 `node1 / node2 / node3` service（build: ./node，env: NODE_ID）
- [ ] 掛載 `./data:/data` volume 給 web container
- [ ] 設定統一 network，確認 hostname 解析

#### 1-2　.env

```dotenv
NODE_URLS=http://node1:5000,http://node2:5000,http://node3:5000
DB_PATH=/data/jobs.db
IMAGE_DIR=/data/images
DISPATCH_INTERVAL=5
MAX_RETRY=3
NODE_TIMEOUT_SEC=35
WEB_CALLBACK_URL=http://web:80
```

- [ ] 建立 `.env` 並在 Compose 中透過 `env_file` 注入

#### 1-3　資料庫初始化（db.py）

- [ ] 實作 `init_db()`：建立 `jobs` 和 `nodes` 兩張資料表（依確定 schema）
- [ ] `PRAGMA journal_mode=WAL;` 啟用 WAL 模式
- [ ] `CREATE INDEX idx_jobs_status ON jobs(status);`
- [ ] 在 `wsgi.py` 啟動時呼叫 `init_db()`，確保 db 存在才接受請求

#### 1-4　驗證

- [ ] `docker compose up --build` 不報錯
- [ ] 進入 web container，確認 `/data/jobs.db` 存在且 Schema 正確
- [ ] `docker exec web curl http://node1:5000/status` 回應正常

---

### Phase 2　計算節點 Flask 服務

**目標：** 節點可以接收工作、背景計算（先用 sleep 替代）、定期回報心跳。

#### 2-1　node_app.py 骨架

```python
# POST /run     ← 接收工作參數 JSON，spawn subprocess，立刻回傳 202
# GET  /status  ← 解析 top -bn 1 -i -c，回傳 CPU、MEM、current_job_id
```

- [ ] `POST /run`：驗證必填欄位 → 寫入 `current_job` 暫存 → `subprocess.Popen(['python', 'mapf/compute.py', ...])` → 回傳 `{"success": true}` + HTTP 202
- [ ] `GET /status`：執行 `top -bn 1 -i -c`，解析 `%Cpu(s)` 與 `MiB Mem`，回傳 JSON
- [ ] 心跳 background thread：每 10 秒 `POST {WEB_CALLBACK_URL}/api/nodes/{NODE_ID}/heartbeat`
- [ ] 啟動指令寫入 Dockerfile：`CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--timeout", "120", "node_app:app"]`

#### 2-2　compute.py（暫時版）

- [ ] 接收命令列 JSON 參數（job_id、map_grid、products、num_agents 等）
- [ ] 先做 `time.sleep(15)`，產生一張假 GIF（純色圖片）
- [ ] 完成後 `POST {WEB_CALLBACK_URL}/api/jobs/{job_id}/complete`（multipart/form-data 帶 GIF 檔案），實作指數退避重試

#### 2-3　驗證

- [ ] `curl -X POST http://localhost:8080/api/jobs -d '{...}'` 後能看到節點收到任務
- [ ] 15 秒後 web 端收到 callback，工作狀態變為 `done`

---

### Phase 3　Web 後端 API

**目標：** 所有 REST API endpoint 正常運作，Dispatcher 可以分派工作。

#### 3-1　Apache + mod_wsgi 設定

```apache
# wsgi.conf
WSGIDaemonProcess webapp processes=2 threads=5 python-home=/usr/local
WSGIProcessGroup webapp
WSGIScriptAlias /api /var/www/app/wsgi.py
```

- [ ] `httpd.conf`：載入 `mod_wsgi.so`、設定靜態檔路徑（`/frontend`）、引入 `wsgi.conf`
- [ ] `wsgi.conf`：設定 daemon process group，將 `/api` 路由到 Python 應用
- [ ] Dockerfile 安裝 `apache2 libapache2-mod-wsgi-py3`

#### 3-2　db.py CRUD 函式

- [ ] `create_job(id, map_grid, products, ...)` → INSERT
- [ ] `get_all_jobs()` → SELECT + JSON 反序列化
- [ ] `get_job(id)` → SELECT WHERE id
- [ ] `update_job_status(id, status, node_id, ...)` → BEGIN IMMEDIATE + UPDATE
- [ ] `cancel_job(id)` → 僅當 status='queued' 才 UPDATE → cancelled
- [ ] `save_job_result(id, gif_path, stats, elapsed_sec)` → UPDATE
- [ ] `upsert_node(node_id, status, current_job_id, last_heartbeat)`
- [ ] `get_all_nodes()` → SELECT

#### 3-3　routes/jobs.py

| Endpoint | 邏輯重點 |
|----------|---------|
| `POST /api/jobs` | 驗證欄位 → 產生 UUID v4 → `create_job()` → 觸發一次 dispatch → 回傳 job_id |
| `GET /api/jobs` | `get_all_jobs()` → 回傳陣列 |
| `DELETE /api/jobs/<id>` | `cancel_job()` → 若狀態非 queued 回傳 400 |
| `GET /api/jobs/<id>/image` | 讀取 `result_gif_path`，以 `send_file` 回傳 |
| `POST /api/jobs/<id>/complete` | 接收 multipart → 儲存 GIF 到 IMAGE_DIR → `save_job_result()` → 清除節點的 `current_job_id` → 觸發一次 dispatch |

- [ ] 所有 endpoint 回傳統一格式：`{"success": bool, "data": ..., "error": ...}`

#### 3-4　routes/nodes.py

- [ ] `GET /api/nodes`：`get_all_nodes()`
- [ ] `POST /api/nodes/<id>/heartbeat`：`upsert_node()` 更新 `last_heartbeat = time.time()`

#### 3-5　dispatcher.py

```python
def try_dispatch():
    # 1. 取得所有 status='queued' 的 job（按 submitted_at 排序）
    # 2. 取得 status='idle' 的節點
    # 3. BEGIN IMMEDIATE: UPDATE job status → running, node_id → node
    # 4. HTTP POST 節點 /run（帶 job 參數）
    # 5. 若 HTTP 失敗：rollback job status → queued, retry_count += 1
    #    若 retry_count >= MAX_RETRY：status → failed

def background_scanner():
    # 每 DISPATCH_INTERVAL 秒呼叫 try_dispatch()
    # 偵測 last_heartbeat 超過 NODE_TIMEOUT_SEC 的節點 → 標記 offline
    # 偵測 running 但節點 offline 的 job → 重排入 queued
```

- [ ] `try_dispatch()` 實作（含 BEGIN IMMEDIATE TRANSACTION）
- [ ] `background_scanner()` daemon thread，在 `wsgi.py` 啟動時以 `threading.Thread(daemon=True)` 啟動
- [ ] 事件觸發：在 `POST /api/jobs` 和 `POST /api/jobs/<id>/complete` 之後呼叫 `try_dispatch()`

#### 3-6　驗證

- [ ] 提交工作 → 自動分派到節點 → callback 後狀態變 done
- [ ] 同時提交 4 個工作 → 3 個分派出去，1 個排隊等待
- [ ] 排隊工作可以 DELETE 取消

---

### Phase 4　MAPF 計算引擎

**目標：** `compute.py` 能執行真正的 PBS MAPF 並產出 GIF。

#### 4-1　astar.py　Time-Expanded A*

```python
def tea_star(grid, start, goal, reserved, max_steps):
    """
    在 (x, y, t) 三維空間搜索
    grid: 2D list（0=走道, 1=牆, 2=貨架, 3=收銀台）
    start: (x, y)
    goal: (x, y)
    reserved: set of (x, y, t) 其他 agent 已佔用的時空點
    回傳: list of (x, y) 路徑，長度為抵達時間步數
    """
```

- [ ] 實作 priority queue（heapq），狀態 = `(f, g, x, y, t)`
- [ ] 鄰居：上下左右 + 等待原地（5 種動作）
- [ ] 邊界檢查 + 牆壁檢查 + reserved 集合衝突檢查
- [ ] 抵達 goal 後回傳路徑

#### 4-2　pbs.py　Priority-Based Search

```python
def pbs(grid, agents):
    """
    agents: list of {id, start, goals: [(x,y), ...], shopping_list}
    goals 為 multi-waypoint：各貨架依序 + 收銀台
    回傳: {agent_id: [(x, y), ...] 全程路徑}
    """
```

- [ ] 按優先序（剩餘購物清單長度，長的優先）依序規劃
- [ ] 每規劃完一個 agent，將其路徑加入 `reserved` 集合
- [ ] 庫存事件處理：到達貨架格時檢查庫存；若售罄，更新 `goals` 重新規劃當前 agent
- [ ] 記錄每個時步所有 agent 位置 → `frames: list[dict]`

#### 4-3　simulation.py　模擬主控

- [ ] 產生顧客購物清單（依 `seed` 隨機選 `list_size` 件商品）
- [ ] 貪婪 TSP 排序目標順序（先去最近的商品）
- [ ] 呼叫 `pbs()` 執行模擬
- [ ] 回傳 `frames`（每步快照）與 `stats`（購買率、完成率等）

#### 4-4　render.py　視覺化

```python
def render_gif(frames, grid, products, output_path):
    """
    frames: list of {agent_id: (x, y), inventory: {pos: count}}
    每幀產生一張 PNG，最後合成 GIF
    """
```

- [ ] 使用 `PIL.Image` 或 `matplotlib` 繪製格子地圖
- [ ] 顏色：黑=牆、棕=貨架（含庫存標籤）、黃=收銀台、彩色圓點=顧客、紅X=售罄
- [ ] 每幀 100ms，輸出 GIF（建議最多 200 幀，超過則每 N 幀取 1 幀）

#### 4-5　compute.py　subprocess 進入點

```python
# 使用方式：python mapf/compute.py '<job_json>'
# 完成後 POST callback 回 WEB_CALLBACK_URL
```

- [ ] 從命令列參數讀取 job JSON
- [ ] 呼叫 `simulation.py` → `render.py`
- [ ] `requests.post(callback_url, files={'gif': ...}, data={...})`，實作指數退避重試

#### 4-6　驗證

- [ ] 單機執行：`python mapf/compute.py '{"map_grid":...}'`，10–30 秒內產出 GIF
- [ ] 確認 GIF 可以正常播放，顧客移動可見

---

### Phase 5　前端

**目標：** 使用者可以在瀏覽器完成地圖設計、提交工作、監看進度、查看 GIF。

#### 5-1　index.html 版面（三區塊）

- [ ] 商場編輯區（Canvas + 工具列 + 參數輸入）
- [ ] 節點狀態區（三欄，各顯示 CPU/MEM/目前工作）
- [ ] 工作列表區（表格：ID、顧客數、狀態、節點、耗時、操作、GIF 縮圖）

#### 5-2　app.js 商場 Canvas 編輯器

- [ ] 繪製 60×60 格子（可縮小至畫面大小）
- [ ] 工具列：畫牆 / 畫貨架 / 放收銀台 / 清除；滑鼠拖曳批次繪製
- [ ] 點擊貨架格：彈出輸入框，設定商品名稱與庫存數量
- [ ] 「送出」按鈕：序列化 `map_grid`、`products`，連同其他參數呼叫 `POST /api/jobs`

#### 5-3　app.js 輪詢更新

```javascript
// 每 3 秒執行一次
async function poll() {
    const [jobs, nodes] = await Promise.all([
        fetch('/api/jobs').then(r => r.json()),
        fetch('/api/nodes').then(r => r.json())
    ])
    renderJobTable(jobs.data)
    renderNodeStatus(nodes.data)
}
setInterval(poll, 3000)
```

- [ ] 工作狀態依 `status` 顯示對應顏色徽章（排隊中 / 執行中 / 完成 / 失敗）
- [ ] 執行中工作顯示 `node_id`
- [ ] 完成工作：顯示 GIF 縮圖，點擊展開放大
- [ ] 排隊中工作：顯示「取消」按鈕，點擊呼叫 `DELETE /api/jobs/<id>`

#### 5-4　驗證

- [ ] 完整 end-to-end：在瀏覽器設計地圖 → 送出 → 等待 → GIF 自動出現

---

### Phase 6　整合測試

- [ ] 同時提交超過 3 個工作，確認排隊行為正確
- [ ] 取消排隊中工作，確認 running / done 工作無法取消
- [ ] 以 `docker stop node1` 模擬節點故障，確認 35 秒後標記 offline、工作重排
- [ ] 確認資源監控：各節點 CPU/MEM 數字顯示正確
- [ ] `docker compose down && docker compose up`：確認工作狀態從 SQLite 正確恢復

---

## 三、必要功能 vs 加分功能

### 必要功能（Phase 1–5 覆蓋）

| 功能 | 對應實作位置 |
|------|------------|
| 工作狀態監控（完成 / 執行中 / 排隊中） | dispatcher.py + 前端輪詢 |
| 執行中標明節點 | jobs 資料表 node_id 欄位 |
| CPU / 記憶體使用率顯示 | node /status endpoint + 前端 |
| 刪除排隊中工作 | DELETE /api/jobs/<id> |

### 加分功能（Phase 5 完成後視時間決定）

| 功能 | 難度 | 說明 |
|------|------|------|
| Heartbeat + Circuit Breaker | 低 | background_scanner 已規劃，可一同實作 |
| 工作失效重試 | 低 | dispatcher 已設計 retry_count 邏輯 |
| WHCA\* 升級 | 中 | 在 pbs.py 同目錄新增 whca.py，前端新增算法選項 |
| 多配置批次比較 | 中 | 前端支援一次提交多組 products 參數 |

---

## 四、各容器關鍵技術備忘

### Web container（Container 1）

```
Apache 設定要點：
- Listen 80
- LoadModule wsgi_module modules/mod_wsgi.so
- WSGIDaemonProcess webapp processes=2 threads=5 display-name=%{GROUP}
- WSGIProcessGroup webapp
- WSGIScriptAlias /api /var/www/app/wsgi.py

注意：靜態檔（HTML/JS）由 Apache 直接服務，不經過 WSGI
```

### Node container（Container 2/3/4）

```
Gunicorn 啟動：
gunicorn --workers 2 --bind 0.0.0.0:5000 --timeout 120 node_app:app

重點：
- /run endpoint 必須立即回傳 202，不可等待計算完成
- compute.py 透過 subprocess.Popen 啟動，不阻塞 worker
- 心跳 thread 需要設為 daemon=True，避免阻止程式結束
```

### SQLite 交易注意事項

```python
# 分派時的正確寫法
conn = sqlite3.connect(DB_PATH)
conn.execute("BEGIN IMMEDIATE")
try:
    job = conn.execute("SELECT * FROM jobs WHERE status='queued' LIMIT 1").fetchone()
    if job:
        conn.execute("UPDATE jobs SET status='running', node_id=? WHERE id=?", (node_id, job['id']))
        conn.execute("UPDATE nodes SET status='busy', current_job_id=? WHERE node_id=?", (job['id'], node_id))
    conn.commit()
except:
    conn.rollback()
    raise
```

---

*計畫文件，持續更新中*
