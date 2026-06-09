# Feature v2 設計文件

> 狀態：**✅ 完成**（2026-06-05 實作並驗證）  
> 涉及檔案：`web/frontend/index.html`、`web/frontend/app.js`、`node/mapf/simulation.py`、`node/mapf/render.py`

---

## 功能一：入口格子（ENTRANCE）

### 概念

在地圖中新增第四種格子類型「入口」。所有顧客只會在入口格子上產生，不再隨機散落在走道格。

### 格子定義

| 類型 | 數值 | 顏色 | 說明 |
|------|------|------|------|
| EMPTY   | 0 | `#e8e8e8` 淺灰 | 可走動的走道（既有）|
| WALL    | 1 | `#334155` 深藍灰 | 不可通行（既有）|
| SHELF   | 2 | `#3b82f6` 藍 | 貨架（既有）|
| CASHIER | 3 | `#22c55e` 綠 | 收銀台（既有）|
| ENTRANCE| 4 | `#f97316` 橘 | **新增**：顧客起點 |

### 前端修改（app.js / index.html）

- 工具列新增「入口」按鈕，點擊後切換為入口工具
- `CELL_COLOR` 陣列加入第五個顏色（index 4）
- Canvas 繪製邏輯：ENTRANCE 格渲染橘色
- `buildProducts()` 不變（只掃貨架格）
- `gridToArray()` 不變（直接帶值 4 給後端）

### 後端修改（simulation.py）

- `_gen_starts()` 優先使用 `grid[r][c] == 4` 的入口格
- 若入口格數量 ≥ `num_agents`：從入口格中隨機（seed 控制）選取，不重複
- 若入口格數量 < `num_agents`：入口格循環分配（多位顧客可共用一格起點，PBS 仍保障衝突避免）
- 若地圖完全沒有入口格：**fallback** 維持舊行為（隨機走道格），並在 stats 中加 `"warn_no_entrance": true`

### 預設地圖調整（app.js）

三個 preset 的 `genSmall/genMedium/genLarge` 函式各在下方（靠近收銀台的走道）加入一排入口格，讓 demo 效果直觀。

---

## 功能二：模擬資訊面板（Simulation Info Panel）

### 目標

讓使用者在看 GIF 的同時，能查閱一份結構化的「模擬說明書」，包含：
- 每個貨架 / 收銀台 / 入口的編號
- 每位顧客的購物清單（用編號表示）和分配到的收銀台編號
- 每個貨架的庫存變化
- 若某顧客因售罄而從清單移除某貨架，明確標出

### 2-1 編號規則

**通用原則：** 所有格子類型按**行優先（row-major）掃描**順序，從左上到右下，依出現順序分配編號，從 1 開始。

| 類型 | 編號變數名 | 範例 |
|------|------------|------|
| 貨架   | S1、S2、S3… | S1 位於 (3,3)、S2 位於 (3,4) |
| 收銀台 | C1、C2、C3… | C1 位於 (17,2) |
| 入口   | E1、E2、E3… | E1 位於 (18,5) |

這個編號方式與前端 `buildProducts()` 的掃描順序完全一致，所以前端看到的 S1 和後端 simulation 的 S1 指的是同一格。

### 2-2 後端回傳的新資料

在 `run_simulation()` 結果的 `stats` dict 中新增以下欄位（job 完成後可從 `GET /api/jobs` 取得）：

```json
{
  "agents": 5,
  "makespan": 73,
  "sum_of_costs": 251,
  "agents_done": 5,
  "stub": false,

  "shelf_index":    {"S1": "3,3", "S2": "3,4", ...},
  "cashier_index":  {"C1": "17,2", "C2": "17,5", ...},
  "entrance_index": {"E1": "18,5", ...},

  "agent_plans": [
    {
      "id": 0,
      "start": "18,5",
      "start_label": "E1",
      "shopping_list": ["S3", "S7", "S12"],
      "assigned_cashier": "C2",
      "skipped_shelves": ["S7"]
    },
    ...
  ],

  "shelf_stock": {
    "S1": {"initial": 3, "final": 2, "sold_out": false},
    "S7": {"initial": 3, "final": 0, "sold_out": true}
  }
}
```

### 2-3 前端：模擬資訊面板

在 GIF Modal 旁（或 Modal 內）加入一個「模擬資訊」區塊，job 狀態變為 `done` 且使用者點擊 GIF 縮圖時一起顯示。

**顧客摘要表（上半部）**

| 顧客 | 起點 | 購物清單 | 分配收銀台 | 備註 |
|------|------|---------|-----------|------|
| 顧客 1 | E1 | S3 → S7 → S12 | C2 | S7 售罄，清單自動移除 |
| 顧客 2 | E1 | S1 → S5 | C1 | 全數購得 |
| 顧客 3 | E2 | S7 → S2 | C3 | S7 售罄，清單自動移除 |

- 購物清單中，被移除的項目用 `~~S7~~`（刪除線）顯示
- 若顧客未在 max_steps 內完成，備註欄標「超時未完成」

**貨架庫存表（下半部）**

| 貨架 | 初始庫存 | 最終庫存 | 狀態 |
|------|---------|---------|------|
| S1 | 3 | 2 | 正常 |
| S7 | 3 | 0 | 售罄 ⚠️ |

### 2-4 地圖格子標籤（Canvas 上顯示編號）

在前端 Canvas 上，對每個有編號的格子，在格子中央用白色小字顯示編號（例如「S1」「C1」「E1」）。

**技術限制說明：**  
目前每格只有 9×9 px，無法清晰顯示文字。因此採用以下方案：

- **Canvas 上不顯示文字**（字太小看不清）
- 改在右側新增「圖例表格」，列出每個編號對應的格子座標與顏色方塊
- 使用者點擊圖例中的某個貨架，Canvas 會短暫高亮該格（閃爍效果，維持 1 秒）

### 2-5 GIF 顯示編號（可選，建議保留作未來升級）

目前 GIF 的 9px cell 無法顯示文字。若未來升級到更大格子，可用 `ImageFont` 在格子上繪製編號。本次 v2 不實作，但 render.py 預留 `show_labels` 參數介面。

---

## 修改範圍彙整

| 檔案 | 修改內容 |
|------|---------|
| `web/frontend/app.js` | 新增 ENTRANCE=4、顏色、工具按鈕、圖例表格、高亮邏輯、Modal 資訊面板 |
| `web/frontend/index.html` | 工具列加入口按鈕、新增圖例區塊、Modal 內加資訊分頁 |
| `node/mapf/simulation.py` | `_gen_starts` 支援入口格、建立 shelf/cashier/entrance 編號、tracking skipped shelves、events 欄位加入 stats |
| `node/mapf/render.py` | 預留 `show_labels` 參數，無實際改動 |

---

## 實作順序（已確認，可執行）

1. **simulation.py**
   - 移除舊 fallback；不含入口/收銀台直接 raise（前端已擋，這是防線二）
   - `_gen_starts` → 改為 staggered spawn，回傳 `{agent_id: spawn_step, agent_id: entrance_pos}`
   - 建立 `shelf_index` / `cashier_index` / `entrance_index` 編號 dict
   - 追蹤 `skipped_shelves`（售罄移除事件）、`assigned_cashier` per agent
   - `stats` 加入 `agent_plans`、`shelf_stock`、三個 index dict

2. **app.js**
   - 新增 `ENTRANCE=4`、`CELL_COLOR[4]='#f97316'`
   - 工具列加「入口」按鈕
   - `syncSubmitInfo()` 加入入口/收銀台檢查，缺少時禁用提交按鈕並顯示提示
   - Canvas 下方渲染圖例表格（S1/C1/E1 + 座標 + 顏色方塊）
   - 點擊圖例項目高亮 Canvas 對應格子（1 秒閃爍）
   - 任務列 `done` job 加「查看資訊」按鈕，展開顧客摘要表 + 貨架庫存表
   - Modal 內 GIF 下方加相同資訊表

3. **index.html**
   - 工具列加入口按鈕 HTML
   - 圖例容器 `<div id="legend">` 放在 Canvas 下方
   - 任務列新增可展開的 info row 結構

4. **三個 preset 地圖（app.js 內 genSmall/genMedium/genLarge）**
   - 各在收銀台上方一排（走道格）加入口格，數量與收銀台數相等

5. **rebuild node + web containers，端對端驗證**

---

## 已確認設計決策

### 決策一：無入口或無收銀台 → 禁止提交

地圖必須同時具備 **至少一個入口格** 與 **至少一個收銀台格**，缺少任一就在前端阻擋提交，並顯示明確提示：

- 「地圖缺少入口（橘色格），請至少放置一個入口後再提交。」
- 「地圖缺少收銀台（綠色格），請至少放置一個收銀台後再提交。」

不再有 fallback 行為，`simulation.py` 的 fallback 邏輯一併移除。

---

### 決策二：圖例位置 → 左欄 Canvas 下方

圖例表格（貨架 S1/S2…、收銀台 C1/C2…、入口 E1/E2…）放在 Canvas 正下方，與編輯工具同欄，保持右欄（節點卡 + 任務表）不變，版面不會畸形。

---

### 決策三：顧客資訊顯示時機 → 兩處都顯示

1. **任務列常駐**：job 狀態一變為 `done`，任務列的該行就多一個「查看資訊」按鈕，點擊後展開顧客摘要表 + 貨架庫存表（inline 展開，不跳 Modal）。
2. **GIF Modal 內**：點擊縮圖開 Modal 時，GIF 下方同樣顯示相同的資訊表（Modal 版，捲動顯示）。

---

### 決策四：入口不夠人數 → 分批延遲進場

若入口格數量 < `num_agents`，採用**分批進場（staggered spawn）**機制，符合現實中顧客陸續進店的情境：

- 第 0 步：前 `num_entrances` 位顧客同時從各入口進場（每個入口各一人）
- 之後每隔 `spawn_interval` 步，再讓一位顧客從隨機入口進場
- `spawn_interval` 預設 = `max(3, 60 // num_agents)`（人數越多進場越快，最慢 3 步一人）
- 尚未進場的顧客不參與 PBS 規劃，也不佔任何格子

**實作方式（simulation.py）：**
- 新增 `pending_agents` 佇列，依進場時間排序
- 主迴圈每步檢查是否有 agent 到達進場時間，有則加入 `active` 清單並放置在對應入口格
- 若該入口格在 spawn 時被其他人佔用，等到入口格空出後再進場（避免初始碰撞）

**GIF 呈現：**
尚未進場的顧客不會出現在任何一幀，進場後才開始顯示圓點，視覺上就像顧客從入口一批一批湧入。
