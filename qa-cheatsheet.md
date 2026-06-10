# QA 小抄（私人版）

> 報告當天備用，涵蓋所有可能被問的技術細節

---

## 一、系統架構類

**Q: SQLite WAL mode 是什麼？為什麼用它？**
WAL（Write-Ahead Log）是 SQLite 的日誌模式。寫入時先寫 WAL 檔，不直接改主資料庫，所以多個讀者可以同時讀（不需等寫完）。適合我們「多節點頻繁讀 + 偶爾寫」的場景。生產環境才需要換 PostgreSQL。

**Q: Dispatcher 怎麼避免兩個節點接到同一個 job？**
用 `BEGIN IMMEDIATE` 交易：進入後其他連線無法寫入，確保「找 idle 節點 + 找 pending job + 更新狀態」這三步是原子操作，不會被插隊。

**Q: background_scanner 做什麼？**
每 5 秒執行一次：
1. 偵測超過 15s 未 heartbeat 的節點 → 標為 offline，該節點 running job 重排為 pending
2. 偵測節點已 idle 但 job 仍 running（重啟場景）→ 同樣重排

**Q: 為什麼 Gunicorn 用 `--workers 1`？**
節點執行的是 CPU 密集型計算（MAPF 模擬），多 worker 會造成多個 job 同時搶 CPU，反而更慢。單 worker 確保一次只跑一個 job，heartbeat 用 background thread 獨立運作，互不干擾。

**Q: Web 用 Apache + mod_wsgi，節點用 Gunicorn，為什麼不統一？**
Web 容器原本規劃用 Apache（老師可能要求）；節點是輕量計算服務，Gunicorn 配置更簡單。兩者都是標準 WSGI 介面，Flask app 不需改動。

**Q: 新增第四個節點 node4 需要改什麼？**
只要在 `docker-compose.yml` 複製 node3 service，改名 node4、設定 `SELF_ID=node4`。不需改 Web 或 Dispatcher 的程式碼，Dispatcher 發現新 heartbeat 後自動加入排程。

**Q: 為什麼用 Docker Compose 不是 Kubernetes？**
課程範疇是 Docker Compose，3 節點量級 Compose 完全夠用。Kubernetes 適合幾十個 Pod 以上的生產規模，引入 K8s 反而增加複雜度而無實際效益。

---

## 二、MAPF 算法類

**Q: PBS 的時間複雜度？**
每個規劃輪次：n 個 agent 各跑一次 A*，A* 最差 O(R×C×T)，所以單輪 O(n × R × C × T)。模擬跑 max_steps 輪，總計 O(max_steps × n × R × C × T)。T 由 `max(max_steps - step, min_t_floor)` 決定。

**Q: Time-Expanded A* 的搜索空間有多大？**
(rows × cols × max_t) 個節點。60×60 地圖、max_t=300 → 最多 1,080,000 個狀態。實際因牆壁和早期到達大幅縮減。

**Q: goal_reserve 設太高會發生什麼？**
高優先 agent 到達收銀台後，該格被 reserved 的時間超過後來 agent 的 A* 搜索視窗，A* 回傳 None → 後來 agent 原地靜止，直到 max_steps 耗盡。本系統已自動 clamp 至 max_steps÷4 防止這種情況。

**Q: 對穿衝突（swap conflict）怎麼修正的？**
`pbs._path_to_reserved()` 除了產生頂點 reserved 集合，還額外產生 `edge_reserved`：對路徑中每個實際移動 (r1,c1)→(r2,c2)，記錄反向邊 `(r2,c2,r1,c1,t)`。`astar()` 展開節點時，若考慮移動 (r,c)→(nr,nc) 且 `(nr,nc,r,c,t) in edge_reserved`，就禁止這個移動。

**Q: 動態收銀台選擇的 score formula 是什麼？**
```
score = manhattan_dist(agent_current_pos, cashier_pos)
      + cashier_queue_count[cashier_pos] × max(1, goal_reserve)
```
距離近 + 排隊少 = 分數低 = 優先選。在 `_assign_target` 的 checkout 轉換時刻才計算，而不是 spawn 時。

**Q: 貪婪最近鄰排序的原理和限制？**
從入口出發，每次選剩餘貨架中 Manhattan 距離最近的，逐一加入清單。是 Greedy Nearest Neighbor 的 mini-TSP 近似解，O(n²) 成本低，通常比隨機順序好 30~50%。最壞情況（環狀分佈）可能比最優解差，但對小購物清單（2~5 件）效果已很好。

**Q: WHCA* 和 PBS 的具體差別？**
| | PBS | WHCA* |
|--|--|--|
| 規劃範圍 | 全步數 | 滑動視窗（固定長度） |
| 優先序 | 固定（agent 索引） | 每視窗重新競爭 |
| 公平性 | agent 0 永遠最優 | 所有人平等 |
| 最優性 | 不保證 | 不保證（視窗限制） |
| 複雜度 | 低 | 中 |

**Q: 為什麼選 PBS 不是 CBS（Conflict-Based Search）？**
CBS 以衝突樹（constraint tree）搜索，可保證全域最優解，但實作複雜度顯著更高，且最壞情況是指數級。PBS 夠用於展示場景，且教學價值清楚（優先序概念直觀）。

---

## 三、功能細節類

**Q: 地圖最大支援多大？**
理論上沒有硬限制，但 60×60 已是目前 Canvas 尺寸（每格 9px = 540px）。更大的地圖可以縮小 CELL 大小，或讓 Canvas 捲動。

**Q: 如果提交的地圖根本連不到某個貨架怎麼辦？**
模擬開始前會執行 BFS 可達性預檢，從所有入口出發，確認所有貨架和收銀台都可達。不可達的格子會附帶標籤（如「貨架 S3」）回傳 ValueError，前端顯示錯誤，不會啟動模擬。

**Q: GIF 是怎麼生成的？**
用 Pillow 的 GIF save 功能。每個模擬 frame 轉成一張 PIL Image（9px/cell，彩色圓表示 agent，紅 X 表示售罄），最後串成 GIF。貨架/收銀台/入口標籤用 5×3 點陣字直接 draw.point() 畫像素，不依賴字型檔案。右側 88px 圖例欄顯示顏色對應表。

**Q: 多個 job 同時跑，result GIF 會不會混淆？**
不會。job 完成時透過 multipart POST 將 GIF bytes 和 stats JSON 回傳給 web，web 依 job_id 存入 SQLite blob 欄位。前端按 job_id 請求 `/api/jobs/<id>/image`，獨立取得各自結果。

**Q: spawn_interval=0 是什麼意思？**
自動計算：`max(3, 60 // num_agents)`。人數多時間隔小（可以更密集進場），人數少時保持最低 3 步間隔，避免入口擁擠。

---

## 四、可能被追問的設計決策

**Q: 為什麼不用 WebSocket 做即時串流，而是輪詢？**
輪詢（3s 間隔）實作簡單，不需要維持長連線。模擬本身需要幾秒到幾十秒，輪詢延遲完全可接受。WebSocket 在多節點 + 反向代理的架構下需要額外的 sticky session 設定，複雜度不值得。

**Q: SQLite blob 存 GIF，大型 GIF 會不會很慢？**
目前 GIF 最多 300 幀，60×60+圖例 = 648px 寬，實測約 200~500 KB。SQLite blob 讀寫在這個大小下毫秒級。若需要更大 GIF，可改為存在 volume 路徑，SQLite 只存檔案路徑。

**Q: 為什麼購物清單是亂數生成而不是讓使用者輸入？**
目的是展示算法行為（多人同時搶購），清單由 seed 控制可以重現。允許使用者輸入清單對展示沒有額外價值，反而增加 UI 複雜度。
