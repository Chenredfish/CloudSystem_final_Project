# PBS 算法已知問題與待解清單

> 建立於 2026-06-09，最後更新 2026-06-09
> 現況：PBS（Priority-Based Search）+ Time-Expanded A*
> 已規劃升級：WHCA*（Windowed Hierarchical Cooperative A*）
> 標記說明：✅ 已修復 | 🔲 待實作 | — 設計決定不需修

---

## 一、對話中發現的問題

### 1. ✅ 無法到達的目標 → 無聲超時
**現象：** 若貨架或收銀台被牆圍死，A* 回傳 None，agent fallback 原地等待，直到步數耗盡才顯示「超時」，使用者看不到原因。

**修復（simulation.py）：** `_bfs_reachable()` 從所有入口做 BFS，模擬開始前驗證全部貨架/收銀台可達性；不可達者即 raise ValueError 附帶格子標籤，前端顯示錯誤訊息。

---

### 2. ✅ goalReserve 造成收銀台永久死鎖
**現象：** 多人被分配到同一個收銀台格時，先到者保留步數過長，後到者的 A* 視窗內永遠看不到格子空出來，只能原地等到超時。goalReserve 設定值若 ≥ max_steps，死鎖必然發生。

**修復（simulation.py）：** 進入模擬前自動 clamp：`goal_reserve = min(goal_reserve, max(1, max_steps // 4))`，配合問題 #6 的動態收銀台分配，死鎖條件從根本消除。

---

### 3. 🔲 低優先 agent 隨人數增加非線性變慢
**現象：** PBS 固定優先序（agent 索引），最後一位 agent 必須繞開所有人的保留路徑，人數越多可用路徑越少，超時機率急速上升。對展示「公平性」不利。

**建議解法：** 每個規劃輪次動態重排優先序（如依剩餘路徑長度排序），或改用 CBS（Conflict-Based Search）提供理論最優解；WHCA* 升級後此問題大幅改善。

---

### 4. ✅ 購物清單順序完全未最佳化
**現象：** 清單由亂數生成後照原順序執行，不考慮各貨架間距離。運氣不好時 agent 來回折返，大幅浪費步數。

**修復（simulation.py）：** `_greedy_sort()` 從 agent 入口出發，貪婪最近鄰重排清單；spawn schedule 建立後套用，`original_lists` 同步更新供 stats 顯示。

---

### 5. ✅ 交換衝突（對穿）未處理
**現象：** 兩 agent 對向互換相鄰格子時，目前 A* 只檢查頂點衝突（同格同時），不攔截對穿，動畫會出現兩人穿越彼此的視覺錯誤。

**修復（astar.py + pbs.py）：** `pbs._path_to_reserved()` 現在額外回傳 `edge_reserved` 集合，記錄每個實際移動的反向邊 `(r2,c2,r1,c1,t)`。`astar()` 新增 `edge_reserved` 參數，展開節點時檢查 `(nr,nc,r,c,t) in edge_reserved`，禁止對穿。

---

## 二、額外發現的潛在問題

### 6. ✅ 收銀台分配三重缺陷（分配時機錯誤、不考慮距離、不考慮排隊）
**現象：** 目前分配邏輯有三個根本問題：

1. **時機錯誤**：收銀台在 spawn 時一次性隨機指定（`simulation.py` 第 89–91 行），此時 agent 距離結帳還很遠，當下的「最近」不等於購完物後的「最近」。
2. **不考慮距離**：完全用 `rng.choice()` 隨機選，不計算 agent 購物結束後到各收銀台的距離。
3. **不考慮排隊人數**：多人可能集中同一個收銀台，其他收銀台閒置，造成不必要等待。

實際情境下，顧客會在購物完畢走向出口時，**同時**考慮「哪個收銀台離我近」和「哪個隊比較短」。

**建議解法：** 在 `_assign_target` 的 `agent_phase[i] = 'checkout'` 轉換時刻才動態選收銀台，依以下分數取最低者：

```
score(cashier) = manhattan_dist(agent_current_pos, cashier_pos)
              + queue_count[cashier_pos] × goal_reserve
```

- `manhattan_dist`：路徑距離近似（不需真正跑 A*）
- `queue_count`：目前已分配但尚未結帳的人數
- `× goal_reserve`：每多一人預計多等 goal_reserve 步

需新增 `cashier_queue_count` dict，結帳完成時 decrement。

**修復（simulation.py）：** 移除 spawn-time 隨機分配；新增 `_best_cashier(current_pos)` 以上述 score 選最佳收銀台，在 `_assign_target` 進入 checkout 時呼叫；`cashier_queue_count` 動態追蹤，完成結帳時 decrement。

---

### 7. ✅ 入口擁塞時晚進場 agent 無窮等待
**現象：** 入口格已被他人佔用時，預定進場的 agent 靜默略過本輪、下輪再試，無重試上限。若入口長期被堵（如某 agent stuck 在入口），後續所有 agent 永遠無法進場。

**修復（simulation.py）：** 新增 `agent_spawn_wait[]` 計數器；每步等待 +1，超過 `spawn_interval × 2` 步後掃描所有入口，找到第一個空閒者強制進場並更新 `agent_entrance_pos[i]`。

---

### 8. — 庫存競爭後重規劃可能無貨可買
**現象：** agent 抵達貨架才發現已售罄（被高優先 agent 搶走），此時 `_assign_target` 跳到下一個目標。若所有清單商品均售罄，agent 直接跳收銀台，購物清單等同放棄，stats 裡只顯示「售罄」，未做任何補救嘗試（如換同類商品）。

**不需解決：** 此為設計決定（搶購情境即有人空手而歸），stats 已記錄 skipped_shelves，視為正常結果。

---

### 10. ✅ 收銀台被佔時 agent 完全原地不動
**現象：** agent 進入 checkout 階段後，若目標收銀台格因 `goal_reserve` 被長期保留，A* 在整個搜索視窗內都找不到可達路徑，回傳 `None`。此時 `len(paths[j]) > 1` 為 False，`new_positions[i]` 保持原值，**agent 完全靜止**直到 max_steps 耗盡。

即使沒有 goal_reserve，若收銀台物理上被其他 agent 佔據，A* 也只能找到「在附近踱步等待」的路徑，浪費大量步數。

此問題與問題 #2（goalReserve 死鎖）和問題 #6（分配機制不良）相互加劇：若多人被分配到同一收銀台，先到者的 goal_reserve 會讓後到者的 A* 完全看不到出口，立即靜止。

**建議解法：**
- 短期：結合問題 #6 的動態分配（選隊最短+最近的收銀台），從根源減少排隊碰撞
- 根本：在 checkout 等待超過一定步數後，允許重新評估並切換到其他收銀台（動態重分配）

---

### 9. 🔲 PBS 優先序固定導致 agent 0 永遠最優
**現象：** agent 0 每輪都最先規劃，路徑永遠最短，其他人替他讓路。同一場模擬跑多次（不同 seed）結果差異大，但 agent 0 幾乎不可能超時，末位 agent 幾乎必然最慢。

**不需解決（待 WHCA* 升級）：** WHCA* 以滑動視窗重規劃，所有人在每個視窗內平等競爭，此問題自然消失。

---

## 三、進度快照（最後更新 2026-06-09）

| 項目 | 狀態 |
|------|------|
| Phase 1–6 核心功能 | ✅ 完成 |
| Feature v2（入口格、資訊面板、GIF 標籤） | ✅ 完成 |
| CPU/MEM 節點監控 | ✅ 完成 |
| Preset max_steps 調整（超時 hotfix） | ✅ 完成 |
| 三個算法參數暴露至前端進階面板 | ✅ 完成 |
| 小小超市方案（20×20，goalReserve=10） | ✅ 完成 |
| **算法問題修復（#1/#2/#4/#5/#6/#7/#10）** | ✅ 完成 |
| PBS 低優先變慢 (#3) / 優先序偏袒 (#9) | 🔲 待 WHCA* |
| WHCA* 升級 | 🔲 視時間決定 |
