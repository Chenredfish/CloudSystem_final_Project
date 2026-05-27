# 分組專題 (2) — 計畫草稿

> 建立日期：2026-05-27  
> 狀態：草稿

---

## 一、專題目標

建立一套分散式計算服務系統，包含：

- 一個 Web 版工作管理介面（供使用者提交、監控、刪除工作），以 Apache + Python 架設
- 三個計算節點容器（負責實際執行計算任務，以 Python 實作）
- 共計四個 Docker Container，透過 Docker Compose 統一管理

---

## 二、系統架構概覽

```
+------------------------------------------+
|     Web 管理介面容器 (Container 1)        |
|  Apache HTTP Server + Python (mod_wsgi)   |
|  - 工作提交介面 (HTML)                    |
|  - 工作狀態監控 (完成 / 執行中 / 排隊中)  |
|  - 各節點 CPU / 記憶體使用率顯示          |
|  - 排隊中工作刪除功能                     |
+-------------------+----------------------+
                    | HTTP (Docker 內部網路)
          +---------+---------+
          |         |         |
    [Node 1]   [Node 2]   [Node 3]
  Container2 Container3 Container4
  Python      Python      Python
  計算服務    計算服務    計算服務
```

所有容器位於同一 Docker 內部網路，容器間以 hostname 互相存取（如 `node1`、`node2`、`node3`）。Web 管理介面為唯一對外暴露 port 的容器。

---

## 三、確定技術棧

| 元件 | 採用技術 | 說明 |
|------|----------|------|
| 容器化 | Docker + Docker Compose | 統一管理四個容器的網路與啟動順序 |
| Web 伺服器 | Apache HTTP Server | 採傳統 Apache，處理 HTTP 請求 |
| 後端語言 | Python | 處理工作佇列、分派邏輯、與節點通訊 |
| 計算節點 | Python | 接收工作、執行計算、回報資源使用率 |
| 前端 | HTML + JavaScript | 定期輪詢後端 API 更新頁面狀態 |

---

## 四、必要功能

### 4.1 工作狀態監控

管理介面須同時呈現三種工作狀態：

| 狀態 | 說明 |
|------|------|
| 排隊中 | 已提交但尚未分配給任何節點的工作 |
| 執行中 | 已分配至某節點且正在計算，需標明所在節點（Node 1 / 2 / 3） |
| 執行完成 | 已完成的工作清單，含完成時間與所屬節點 |

### 4.2 資源使用率監控

- 於各計算節點上執行 `top -bn 1 -i -c`，解析 CPU 與記憶體使用數據
- Web 介面以表格或儀表板形式分別顯示三個節點的即時資源狀態
- 管理端定期向各節點查詢，建議更新間隔為 5 秒

### 4.3 刪除排隊中的工作

- 使用者可對狀態為「排隊中」的工作執行刪除
- 狀態為「執行中」或「執行完成」的工作不可刪除
- 刪除後須立即反映於工作列表

---

## 五、發想功能（加分項目）

### 系統層面

| 功能 | 說明 | 複雜度 |
|------|------|--------|
| 節點當機偵測 | 以定期 heartbeat 偵測節點是否存活，連續缺席則標記 offline | 中 |
| 工作重新分配 | 節點當機時，將其執行中工作移回佇列重新分派 | 高 |
| 動態剔除節點 | 手動或自動將失效節點移出分派清單 | 中 |
| 負載感知分派 | 依節點目前 CPU 使用率決定工作分配對象 | 中 |
| 工作執行日誌 | 記錄各工作的詳細執行紀錄與輸出結果 | 低 |

### 計算任務層面

| 功能 | 說明 | 複雜度 |
|------|------|--------|
| WHCA\* 升級 | 將 PBS 升級為 Windowed HCA\*，加入滑動時間窗口，計算品質更高 | 中 |
| 多配置批次比較 | 使用者一次提交多個商品擺放方案，各方案作為獨立 job 分散到不同節點，完成後比較結果（平均購物完成時間、衝突次數、商品售罄率） | 中 |
| 配置最佳化搜索 | 以模擬退火（Simulated Annealing）自動尋找最優商品擺放：擾動當前配置 → 提交 job 取得評分 → 機率決定是否接受 → 迭代。分散式節點天然成為評估函數的平行執行器。注意：此功能本身即為完整研究課題，建議僅實作概念驗證版本 | 高 |
| Iterative Decoupled MAPF | 同一場景的顧客分為三組，三節點並行規劃各自的路徑，管理端偵測跨組衝突後迭代重新規劃。不保證最優解，但展示計算層級的分散。注意：顧客之間存在真實衝突，分組會產生組間衝突遺漏，需在報告中說明此限制 | 高 |

---

## 六、交期與里程碑

| 日期 | 事項 | 說明 |
|------|------|------|
| 5/27 | 確定題目 | 決定後不可更換題目，第一頁須填寫題目、組員姓名、學號 |
| 5/27 下課前 | 上傳架構分析報告 (佔 30%) | A4 PDF，5 至 10 頁 |
| 6/3 | 期末考試 | — |
| 6/10 下課前 | 報告 + 上傳資料 (佔 70%) | — |

---

## 七、架構分析報告大綱（5/27 繳交）

> A4 PDF，5 至 10 頁，比較市面上一個功能相似的分散式系統

1. 本系統架構說明
   - 整體架構圖與資料流說明
   - 各元件職責與互動方式

2. 本系統優點
   - 以 Docker 容器化，部署與擴展簡便
   - 工作狀態可視化，操作直覺
   - 資源使用率即時監控，便於觀察系統負載

3. 本系統缺點與限制
   - 管理節點為單點失效風險（Single Point of Failure）
   - 工作狀態若未持久化，容器重啟後將遺失
   - 內部通訊未加密，不適合生產環境

4. 比較對象（擇一進行深入比較）
   - 候選系統：HTCondor、Apache Spark、Kubernetes Jobs、SLURM
   - 比較維度：系統架構、擴展性、容錯機制、易用性、適用規模

5. 結論
   - 本系統與比較系統的適用情境對比
   - 本系統於教學與小規模部署的價值

---

## 八、工作分配（待填）

| 姓名 | 學號 | 負責項目 |
|------|------|----------|
| — | — | Web 前端介面 |
| — | — | Apache 設定、Python 後端邏輯 |
| — | — | 計算節點 Python 服務、Docker 設定 |
| — | — | 資源監控整合、報告撰寫 |

---

## 九、待辦事項

- [ ] 確認題目，填寫第一頁題目、組員姓名、學號
- [ ] 決定架構分析報告的比較對象
- [ ] 分配組員工作項目
- [ ] 完成架構分析報告並於 5/27 下課前上傳
- [ ] 建立 Git Repository，初始化專案目錄結構
- [ ] 確認以下各項設計決策（見第十節）

---

## 十、已確定的架構決策

| 決策項目 | 採用方案 | 關鍵原因 |
|----------|----------|----------|
| Python 與 Apache 整合 | mod_wsgi（daemon mode） | CGI 每次請求重啟程序，無法維護狀態；daemon mode 允許背景執行緒 |
| 佇列與狀態儲存 | SQLite + WAL mode | 四容器限制排除 Redis；WAL 模式允許讀寫並發；Python 內建支援 |
| 工作傳送方式 | Push 模式（管理端呼叫節點 API） | 唯一能讓管理端明確記錄「工作在哪個節點」的方式 |
| 計算節點伺服器 | Flask + Gunicorn | 業界標準 WSGI 部署方式，不使用 Flask 內建開發伺服器 |
| 分派策略 | Round-Robin 掃描空閒節點，每節點一次一工作 | 三態語意清晰，適合 demo 展示佇列行為 |
| 資源監控取得 | 節點 `/status` endpoint 回傳 top 解析結果 | 避免 Docker socket 掛載的安全問題 |

---

## 十一、關於「分散」的定義確認

在開始細節決策前，需要先確認系統的分散性質，避免實作方向與作業要求錯位。

### 兩種「分散」的區別

**任務層級分散（Task Parallelism）**：不同工作分配給不同節點執行，每個節點從頭到尾完整計算一個工作。這是本系統的設計。

```
Job A ──► Node 1（完整計算 Job A）
Job B ──► Node 2（完整計算 Job B）
Job C ──► Node 3（完整計算 Job C）
```

**計算層級分散（Data Parallelism）**：單一工作被拆成多份，同時送給多個節點各算一部分，最後合併。

```
Job A 拆成三份
  片段 A1 ──► Node 1
  片段 A2 ──► Node 2   ──► 管理端合併 ──► Job A 完整結果
  片段 A3 ──► Node 3
```

### 本系統採用哪種？是否符合作業要求？

本系統採用任務層級分散。對照作業要求：

- 「提供一種計算服務」：符合，提交一個計算工作，由節點執行後回傳結果
- 「新增三個計算節點」：符合，三個節點並行處理不同工作
- 「監看執行完成、執行中（標明正在哪一個節點）、排隊中」：這條需求本身就預設了「每個工作在某一個節點上執行」的模型，與任務層級分散完全對應

作業要求符合。任務層級分散也是業界真實系統（SLURM、Kubernetes Jobs、Celery）的主流設計。

### 是否可以同時支援計算層級分散？

可以，且 A* 算法有一個在遊戲業界真實使用的分散式變體可以自然地實現這一點。這部分在細節 1 的強化版 A* 方案中說明。

---

## 十二、待決定的具體細節

---

### 細節 1：計算任務的內容 — 商場購物搶購模擬（MAPF）

**核心概念**

使用者設計一個商場場景：放置貨架、決定商品位置與庫存數量。系統模擬多個顧客同時入場搶購，每位顧客持有不同的購物清單，全員使用 Multi-Agent Pathfinding with Conflict Resolution（MAPF）算法規劃不互撞的移動路徑，搶先到達貨架者取得商品。模擬完成後輸出各時步的 PNG 序列（合成 GIF）。

這個場景直接對應真實業界應用：Amazon 倉庫的 Kiva 機器人、IKEA 自動揀貨系統，使用的算法家族與此相同。

---

**MAPF 深度選擇**

本專題可以在以下算法中選擇落點，越深技術難度越高，計算時間也越長：

| 層級 | 算法 | 技術描述 | 計算時間（30人，60×60）| 實作難度 |
|------|------|----------|----------------------|----------|
| L2 | PBS（Priority-Based Search） | 依優先序依次規劃，前者為後者的動態障礙 | 10–25 秒 | 低 |
| L3 | WHCA\*（Windowed HCA\*） | 滑動時間窗協調，兼顧效率與品質 | 15–40 秒 | 中 |
| L4 | CBS（Conflict-Based Search） | 二層搜索，保證最優解 | 30–120 秒 | 中–高 |

**建議落點：PBS 實作、WHCA\* 為優化目標**。PBS 邏輯清楚，約 150–200 行可完成；WHCA\* 是業界實用系統的主流，可作為 bonus 升級。CBS 保證最優解但指數級最壞情況，僅建議 agent 數量 < 20 時採用。

---

**遊戲設計**

**Phase 1：使用者設計商場場景（前端 Canvas）**

```
商場地圖（60×60 格），使用者可操作：

  [畫牆] [畫貨架] [清除] [放出口]

  ┌──────────────────────────────────────────┐
  │ 入口                                     │
  │ ████  A[3]  ████  B[5]  ████  C[2]  ████ │
  │                                          │
  │ ████  D[4]  ████  E[1]  ████  F[8]  ████ │
  │                                          │
  │ ████  G[6]  ████  H[3]  ████  I[2]  ████ │
  │                                 收銀台    │
  └──────────────────────────────────────────┘

  A[3] = 商品 A，庫存 3 個

使用者設定：
  - 顧客人數：[30]
  - 每位顧客的購物清單長度：[3] 至 [5] 件
  - 購物清單生成方式：隨機 / 手動指定
  - 模擬時步上限：[200]
```

**Phase 2：節點計算（MAPF 核心）**

節點接收商場地圖、商品位置與庫存、顧客數量與各自的購物清單，執行以下步驟：

```
1. 初始化：所有顧客從入口出發，各自持有購物清單

2. 計算每位顧客的目標序列（Multi-Waypoint）：
   購物清單 [商品A, 商品C, 商品F] → 需依序拜訪三個貨架位置，最後前往收銀台
   目標順序：貪婪 TSP（先去最近的商品，再去下一件）

3. 時步迴圈（PBS 算法）：
   for t in range(max_steps):
       依優先序排列顧客（可依剩餘購物清單長度）
       for agent in sorted_agents:
           規劃下一步：A*（time-expanded），將已規劃 agent 的路徑視為障礙
           若目標格有商品且庫存 > 0：取走商品，庫存 -1，更新購物清單
           若庫存已空：重新規劃前往下一個目標
       記錄本時步所有 agent 位置

4. 輸出：各時步的狀態快照，生成 PNG 序列
```

**Phase 3：輸出視覺化**

每一個時步輸出一張 PNG，合成 GIF（約 200 幀，每幀 100ms，總長 20 秒）。

```
PNG 顏色編碼：
  黑色格子   = 牆壁
  棕色格子   = 貨架（貼上商品標籤與庫存數字）
  黃色收銀台 = 出口區域
  彩色圓形   = 各顧客（每人一個獨立顏色，30 人對應 30 種色）
  顏色深淺   = 購物清單完成度（淺=剛開始，深=快完成）
  紅色 X     = 庫存售罄的貨架
  軌跡線     = 每位顧客過去 5 步的移動軌跡（漸隱）
  數字標籤   = 顧客剩餘待購商品數
```

**動態事件（增加觀察趣味）：**
- 顧客同時到達同一貨架：庫存按到達先後分配，後到者顯示「失望」動畫後重新規劃
- 庫存清空事件：貨架標記紅 X，正在前往該貨架的顧客立即重新規劃路線
- 顧客完成購物進入收銀台：顯示完成時間
- 結算畫面：統計每件商品的購買率、最快完成購物的顧客、平均等待步數

---

**計算量分析**

| 商場規模 | 顧客數 | 購物清單長度 | 算法 | 預估時間 |
|----------|--------|------------|------|----------|
| 40×40 | 15 人 | 3 件 | PBS | 8–15 秒 |
| 60×60 | 30 人 | 4 件 | PBS | 15–35 秒 |
| 60×60 | 30 人 | 4 件 | WHCA\* | 20–45 秒 |
| 80×80 | 50 人 | 5 件 | PBS | 40–90 秒 |

Multi-waypoint 的計算瓶頸在於 Time-Expanded A*（TEA\*）：agent 在 `(x, y, t)` 三維空間搜索，空間大小為 `grid_cells × max_steps`，60×60 地圖 200 步 = 720,000 個節點，30 個 agent 共需處理 2,160 萬節點。

---

**分散式設計**

任務層級分散：每個提交的場景是一個 job，多個使用者提交不同場景分散到三個節點。

計算層級分散（bonus）：同一場景下，將顧客依 ID 分成三組，各節點使用 PBS 規劃自己負責的那組顧客路徑（以其他節點已規劃的路徑作為靜態障礙），管理端整合三份計劃後執行模擬。此設計實現 agent-level 的計算分散，對應 RHCR（Rolling Horizon Collision Resolution）在空間上的分區概念。

---

**技術背景引述**

- Amazon Kiva 機器人系統（現 Amazon Robotics）：倉庫內數百台機器人同時移動，使用 WHCA\* 變體
- IKEA 自動化倉庫（Automated Storage and Retrieval System）：類似顧客搶貨的多 agent 協調問題
- 電玩：《Among Us》的 NPC 移動、《Stardew Valley》的 NPC 路徑規劃均使用 MAPF 簡化版本

---

**工作參數結構**

| 參數 | 型態 | 說明 |
|------|------|------|
| `map_grid` | 2D array | 商場地圖（0=走道, 1=牆, 2=貨架, 3=收銀台）|
| `products` | dict | `{貨架座標: {名稱, 庫存數量}}`|
| `num_agents` | int | 顧客人數（建議 20–40）|
| `list_size` | int | 每位顧客的購物清單長度（建議 3–5）|
| `max_steps` | int | 模擬時步上限（建議 200）|
| `algorithm` | string | `"PBS"` / `"WHCA"` |
| `seed` | int | 隨機種子（控制購物清單生成，確保可重現）|

**分散方式**：不同 job（不同商場配置或不同 seed）分配到不同節點完整計算，為任務層級並行。Iterative Decoupled MAPF 與多配置最佳化搜索已移至第五節發想功能，視時間決定是否實作。

---

### 細節 2–9：實作規格摘要

**Job ID 與資料表**

- Job ID 使用 UUID v4（非自增整數）：防止洩漏工作總量，支援冪等提交
- SQLite 啟用 WAL mode（`PRAGMA journal_mode=WAL`）：允許讀寫並發
- `cancelled` 狀態用於刪除排隊工作，保留歷史記錄（audit trail），不做物理刪除

```sql
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,    -- UUID v4
    map_grid        TEXT NOT NULL,       -- JSON 二維陣列（地圖）
    products        TEXT NOT NULL,       -- JSON {座標: {名稱, 庫存}}
    num_agents      INTEGER NOT NULL,
    list_size       INTEGER NOT NULL DEFAULT 4,
    max_steps       INTEGER NOT NULL DEFAULT 200,
    algorithm       TEXT NOT NULL DEFAULT 'PBS',
    seed            INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    -- queued / running / done / failed / cancelled
    node_id         TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    result_gif_path TEXT,               -- 模擬動畫 GIF 路徑
    stats           TEXT,               -- JSON 統計結果（購買率、衝突次數等）
    elapsed_sec     REAL,
    error_msg       TEXT,
    submitted_at    REAL NOT NULL,
    dispatched_at   REAL,
    completed_at    REAL
);
CREATE INDEX idx_jobs_status ON jobs(status);

CREATE TABLE nodes (
    node_id          TEXT PRIMARY KEY,   -- node1 / node2 / node3
    status           TEXT NOT NULL DEFAULT 'unknown',
    current_job_id   TEXT,
    last_heartbeat   REAL,
    consecutive_miss INTEGER NOT NULL DEFAULT 0
);
```

**工作狀態機**

```
queued ──(使用者取消)──► cancelled
  │
  └─(dispatcher 分派)──► running
                            │
                ┌───────────┴───────────┐
          (callback 成功)       (失敗 / timeout)
                │                       │
              done              retry_count < 3?
                                   是 → queued
                                   否 → failed
```

所有狀態轉換在 `BEGIN IMMEDIATE TRANSACTION` 內完成，防止競態條件。

**Dispatcher 設計（雙軌觸發）**

| 觸發時機 | 說明 |
|----------|------|
| 工作提交時 | 立刻嘗試一次分派（有空閒節點則直接執行） |
| 節點 callback 收到時 | 立刻再嘗試一次（不等下一個週期） |
| 背景 daemon thread | 每 5 秒兜底掃描，補救 callback 失敗的滯留工作 |

分派順序：先 commit DB（status → running），再 HTTP push 節點。HTTP 失敗時 UPDATE 回 queued，不會有狀態不一致。

**節點完成通知（Callback + Fallback）**

節點完成後：`POST /api/jobs/<job_id>/complete`，body 含 `node_id`、`elapsed_sec`、GIF 檔案（multipart/form-data）。
失敗重試：指數退避 1s → 2s → 4s，三次失敗後 GIF 暫存節點本地，等 dispatcher 兜底偵測。

**節點健康（主動 Heartbeat + Circuit Breaker）**

節點每 10 秒向管理端 `POST /api/nodes/<node_id>/heartbeat`（含目前狀態與 job_id）。
超過 35 秒無心跳（連續 3 次缺席）→ 標記 `offline`，dispatcher 跳過，不分派工作，直到心跳恢復。

**節點部署（Flask + Gunicorn）**

```
gunicorn --workers 2 --bind 0.0.0.0:5000 --timeout 120 node_app:app
```

兩個 worker：一個跑長時間計算（subprocess.Popen 獨立程序），一個回應 `/status` 與 heartbeat。
計算以 subprocess 執行避免 GIL；`/run` endpoint 收到請求後立即回傳 202，計算在背景完成後 callback。

**API 規範**

```
POST   /api/jobs                     提交工作（UUID 由前端生成帶入）
GET    /api/jobs                     列出所有工作
DELETE /api/jobs/<id>                取消排隊中工作（→ cancelled）
GET    /api/jobs/<id>/image          取得結果 GIF
POST   /api/jobs/<id>/complete       節點 callback
GET    /api/nodes                    列出節點狀態
POST   /api/nodes/<id>/heartbeat     節點心跳
```

統一回傳格式：`{ "success": bool, "data": {...} | null, "error": {"code": "...", "message": "..."} | null }`

**環境變數（`.env` + Docker Compose 注入）**

```dotenv
NODE_URLS=http://node1:5000,http://node2:5000,http://node3:5000
DB_PATH=/data/jobs.db
IMAGE_DIR=/data/images
DISPATCH_INTERVAL=5
MAX_RETRY=3
NODE_TIMEOUT_SEC=35
NODE_ID=node1          # 各節點容器覆寫此值
WEB_CALLBACK_URL=http://web:80
```

**前端設計（單頁，三區塊）**

```
+--[ 商場編輯區 ]-----------------------------------------------+
|  [畫牆] [畫貨架] [放收銀台] [清除]  地圖大小: [60]x[60]      |
|                                                               |
|  ████  A[3]  ████  B[5]  ████  C[2]  ████                    |
|                                        點擊格子切換地形       |
|  ████  D[4]  ████  E[1]  ████  F[8]  ████                    |
|                                        貨架格可設商品名稱     |
|  ████  G[6]  ████  H[3]  ████  收銀台 ████                   |
|                                                               |
|  顧客人數: [30]  購物清單長度: [4]  步數上限: [200]  [送出]   |
+---------------------------------------------------------------+

+--[ 節點狀態 ]----+  +--[ 節點狀態 ]----+  +--[ 節點狀態 ]----+
| node1            |  | node2            |  | node3            |
| CPU: 87%         |  | CPU: 12%         |  | CPU: 91%         |
| MEM: 23%         |  | MEM: 18%         |  | MEM: 25%         |
| 執行中: a3f2..   |  | 閒置             |  | 執行中: 9c1d..   |
+------------------+  +------------------+  +------------------+

+--[ 工作列表 ]----------------------------------------------------------------+
| ID(短) | 顧客數 | 步數 | 狀態   | 節點  | 耗時   | 操作   | 結果動畫         |
| a3f2   |   30   | 200  | 完成   | node2 | 28.4s  | —      | [GIF 縮圖]       |
| 9c1d   |   30   | 200  | 執行中 | node1 | —      | —      | —                |
| b7e1   |   40   | 200  | 排隊中 | —     | —      | [取消] | —                |
+------------------------------------------------------------------------------+
```

JavaScript 每 3 秒以 `fetch` 輪詢 `GET /api/jobs` 與 `GET /api/nodes` 更新 DOM（不整頁重整）。完成工作的 GIF 縮圖點擊可展開放大，顯示完整的顧客移動動畫與搶購過程。

---

## 十三、容器職責總覽

**Container 1 — Web 管理介面**
- Apache HTTP Server + mod_wsgi
- Python 處理工作提交、分派、狀態查詢、刪除邏輯
- SQLite 資料庫（掛載 volume 持久化）
- 定期輪詢三個計算節點的 `/status` endpoint
- 對外暴露 HTTP port（如 8080）

**Container 2 / 3 / 4 — 計算節點**
- Python Flask HTTP server（內部 port，如 8000）
- `POST /run`：接收工作參數，啟動計算子程序
- `GET /status`：執行 `top -bn 1 -i -c`，回傳 CPU、記憶體使用率及當前工作 ID
- 不對外暴露 port，僅限 Docker 內部網路存取

---

*草稿，持續更新中*
