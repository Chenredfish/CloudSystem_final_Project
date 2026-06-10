"""Simulation controller for the shopping MAPF scenario.

Runs the full multi-agent shopping simulation with staggered spawn from entrance cells:
  1. Build shelf/cashier/entrance index (row-major scan order → S1/C1/E1 labels)
  2. BFS reachability check: raise ValueError if any shelf/cashier is unreachable
  3. Generate shopping lists; greedy nearest-neighbor sort to minimise travel
  4. Staggered spawn: first num_entrances agents at step 0, then one per spawn_interval
     Entrance retry: if assigned entrance is blocked too long, try alternate entrance
  5. PBS planning loop: each spawned agent pursues its current target
  6. Inventory events: first arrival claims stock; sold-out shelves are skipped
  7. Dynamic cashier selection at checkout: score = dist + queue_count × goal_reserve
  Returns frames for GIF rendering + expanded stats dict
"""
import random
from collections import deque

from .pbs import plan_agents

EMPTY, WALL, SHELF, CASHIER, ENTRANCE = 0, 1, 2, 3, 4


def _find_cells(grid, cell_type):
    out = []
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v == cell_type:
                out.append((r, c))
    return out


def _build_index(cells, prefix):
    """Build {label: 'r,c'} dict in row-major scan order, starting at 1."""
    return {f"{prefix}{i+1}": f"{r},{c}" for i, (r, c) in enumerate(cells)}


def _to_pos(rc_str):
    r, c = rc_str.split(',')
    return (int(r), int(c))


def _bfs_reachable(grid, starts):
    """Return set of all (r,c) reachable from any cell in starts (BFS, ignores walls)."""
    rows, cols = len(grid), len(grid[0])
    visited = set(starts)
    q = deque(starts)
    while q:
        r, c = q.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited and grid[nr][nc] != WALL:
                visited.add((nr, nc))
                q.append((nr, nc))
    return visited


def _greedy_sort(positions, start):
    """Greedy nearest-neighbor ordering of positions starting from start (Manhattan)."""
    remaining = list(positions)
    result = []
    cur = start
    while remaining:
        nearest = min(remaining, key=lambda p: abs(p[0] - cur[0]) + abs(p[1] - cur[1]))
        result.append(nearest)
        remaining.remove(nearest)
        cur = nearest
    return result


def run_simulation(grid, products, num_agents, list_size, max_steps, seed,
                   spawn_interval=0, min_t_floor=50, goal_reserve=200):
    """Run the shopping simulation with staggered spawn from entrance cells.

    Raises ValueError if no entrance/cashier cells are found, or if any
    shelf/cashier is unreachable from all entrances.

    Returns
    -------
    frames  : list of dicts {positions, inventory, done}
              positions[i] is (r,c) or None (agent not yet spawned)
    stats   : dict with makespan, sum_of_costs, agent_plans, shelf_stock, etc.
    """
    shelf_cells    = _find_cells(grid, SHELF)
    cashier_cells  = _find_cells(grid, CASHIER)
    entrance_cells = _find_cells(grid, ENTRANCE)

    if not cashier_cells:
        raise ValueError("地圖缺少收銀台格，無法執行模擬")
    if not entrance_cells:
        raise ValueError("地圖缺少入口格，無法執行模擬")

    # --- Fix #2: clamp goal_reserve to prevent guaranteed cashier deadlock ---
    goal_reserve = min(goal_reserve, max(1, max_steps // 4))

    # Build label dicts (row-major scan order)
    shelf_index    = _build_index(shelf_cells,    'S')
    cashier_index  = _build_index(cashier_cells,  'C')
    entrance_index = _build_index(entrance_cells, 'E')

    # Reverse lookups: (r,c) → label
    pos_to_shelf_lbl    = {_to_pos(rc): lbl for lbl, rc in shelf_index.items()}
    pos_to_cashier_lbl  = {_to_pos(rc): lbl for lbl, rc in cashier_index.items()}
    pos_to_entrance_lbl = {_to_pos(rc): lbl for lbl, rc in entrance_index.items()}

    # --- Fix #1: BFS reachability pre-check ---
    reachable = _bfs_reachable(grid, entrance_cells)
    unreachable_shelves  = [lbl for lbl, rc in shelf_index.items()   if _to_pos(rc) not in reachable]
    unreachable_cashiers = [lbl for lbl, rc in cashier_index.items() if _to_pos(rc) not in reachable]
    if unreachable_shelves or unreachable_cashiers:
        parts = []
        if unreachable_shelves:  parts.append(f"貨架 {', '.join(unreachable_shelves)}")
        if unreachable_cashiers: parts.append(f"收銀台 {', '.join(unreachable_cashiers)}")
        raise ValueError(f"以下格子從入口無法到達：{'; '.join(parts)}")

    # Inventory: (r,c) → stock
    inventory = {}
    for key, info in products.items():
        inventory[_to_pos(key)] = int(info.get('stock', 1))

    init_stock = {lbl: inventory.get(_to_pos(rc), 3) for lbl, rc in shelf_index.items()}

    # Generate per-agent shopping lists (S-labels)
    rng = random.Random(seed)
    shelf_labels = list(shelf_index.keys())

    original_lists = []
    for _ in range(num_agents):
        chosen = rng.sample(shelf_labels, min(list_size, len(shelf_labels))) if shelf_labels else []
        original_lists.append(list(chosen))

    # Working todo queues as (r,c) tuples (will be greedy-sorted after spawn schedule)
    agent_todos = [[_to_pos(shelf_index[lbl]) for lbl in lst] for lst in original_lists]

    # Dynamic cashier state (assigned at checkout time, not at spawn)
    agent_cashier_lbl   = [None] * num_agents
    agent_cashier_pos   = [None] * num_agents
    cashier_queue_count = {pos: 0 for pos in cashier_cells}

    # Staggered spawn schedule
    num_entrances = len(entrance_cells)
    if spawn_interval <= 0:
        spawn_interval = max(3, 60 // num_agents)
    rng_spawn    = random.Random(seed + 1)
    shuffled_ent = list(entrance_cells)
    rng_spawn.shuffle(shuffled_ent)

    agent_spawn_step   = []
    agent_entrance_pos = []
    for i in range(num_agents):
        if i < num_entrances:
            agent_spawn_step.append(0)
            agent_entrance_pos.append(shuffled_ent[i])
        else:
            batch = i - num_entrances
            agent_spawn_step.append(spawn_interval * (batch + 1))
            agent_entrance_pos.append(shuffled_ent[i % num_entrances])

    # --- Fix #4: greedy nearest-neighbor sort of each agent's shopping list ---
    for i in range(num_agents):
        if len(agent_todos[i]) > 1:
            sorted_pos = _greedy_sort(agent_todos[i], agent_entrance_pos[i])
            agent_todos[i] = sorted_pos
            original_lists[i] = [pos_to_shelf_lbl[p] for p in sorted_pos]

    # Simulation state
    positions      = [None] * num_agents  # None = not yet spawned
    agent_done     = [False] * num_agents
    agent_phase    = ['shop'] * num_agents  # 'shop' or 'checkout'
    agent_target   = [None] * num_agents
    agent_skipped  = [[] for _ in range(num_agents)]
    agent_spawn_wait = [0] * num_agents   # steps spent waiting at a blocked entrance

    frames = []
    sum_of_costs = 0

    # --- Fix #6+#10: best cashier = nearest with lowest queue weight ---
    def _best_cashier(current_pos):
        best_pos   = cashier_cells[0]
        best_score = float('inf')
        for pos in cashier_cells:
            dist  = abs(pos[0] - current_pos[0]) + abs(pos[1] - current_pos[1])
            score = dist + cashier_queue_count[pos] * max(1, goal_reserve)
            if score < best_score:
                best_score = score
                best_pos   = pos
        return best_pos

    def _assign_target(i, current_pos):
        """Return next target (r,c) for agent i. Skips sold-out shelves in-place.
        current_pos is used only when transitioning to checkout (cashier selection).
        """
        while agent_todos[i]:
            tgt = agent_todos[i][0]
            if inventory.get(tgt, 0) > 0:
                return tgt
            lbl = pos_to_shelf_lbl.get(tgt, f"{tgt[0]},{tgt[1]}")
            if lbl not in agent_skipped[i]:
                agent_skipped[i].append(lbl)
            agent_todos[i].pop(0)
        # All items done → dynamically choose nearest least-busy cashier
        agent_phase[i] = 'checkout'
        best_pos = _best_cashier(current_pos)
        agent_cashier_pos[i] = best_pos
        lbl = pos_to_cashier_lbl.get(best_pos, f"{best_pos[0]},{best_pos[1]}")
        agent_cashier_lbl[i] = lbl
        cashier_queue_count[best_pos] += 1
        return best_pos

    for step in range(max_steps):
        # Spawn agents whose scheduled step has arrived (FIFO, entrance-conflict-aware)
        ready = sorted(
            [i for i in range(num_agents) if positions[i] is None and agent_spawn_step[i] <= step],
            key=lambda i: agent_spawn_step[i],
        )
        occupied = {pos for pos in positions if pos is not None}
        for i in ready:
            ep = agent_entrance_pos[i]
            if ep not in occupied:
                positions[i] = ep
                occupied.add(ep)
                agent_spawn_wait[i] = 0
                agent_target[i] = _assign_target(i, ep)
            else:
                # --- Fix #7: entrance congestion retry after timeout ---
                agent_spawn_wait[i] += 1
                if agent_spawn_wait[i] >= max(spawn_interval, 3) * 2:
                    for alt_ep in entrance_cells:
                        if alt_ep not in occupied:
                            positions[i] = alt_ep
                            occupied.add(alt_ep)
                            agent_entrance_pos[i] = alt_ep
                            agent_spawn_wait[i] = 0
                            agent_target[i] = _assign_target(i, alt_ep)
                            break

        active  = [i for i in range(num_agents) if positions[i] is not None and not agent_done[i]]
        pending = [i for i in range(num_agents) if positions[i] is None]

        if not active and not pending:
            break

        if active:
            paths = plan_agents(
                grid,
                [positions[i] for i in active],
                [agent_target[i] for i in active],
                max_t=max(max_steps - step, min_t_floor),
                goal_reserve=goal_reserve,
            )

            new_positions = list(positions)
            for j, i in enumerate(active):
                if len(paths[j]) > 1:
                    new_positions[i] = paths[j][1]

            for j, i in enumerate(active):
                pos = new_positions[i]
                tgt = agent_target[i]
                if pos == tgt:
                    if agent_phase[i] == 'shop':
                        if agent_todos[i] and agent_todos[i][0] == tgt:
                            if inventory.get(tgt, 0) > 0:
                                inventory[tgt] -= 1
                                agent_todos[i].pop(0)
                        agent_target[i] = _assign_target(i, pos)
                    elif agent_phase[i] == 'checkout':
                        agent_done[i] = True
                        sum_of_costs += step + 1
                        cashier_queue_count[pos] = max(0, cashier_queue_count.get(pos, 0) - 1)

            positions = new_positions

        frames.append({
            'positions': list(positions),
            'inventory': dict(inventory),
            'done': list(agent_done),
        })

    for i in range(num_agents):
        if not agent_done[i]:
            sum_of_costs += max_steps

    makespan = len(frames)

    # Shelf stock summary
    shelf_stock = {}
    for lbl, rc in shelf_index.items():
        pos     = _to_pos(rc)
        final   = inventory.get(pos, 0)
        initial = init_stock[lbl]
        shelf_stock[lbl] = {
            'initial':  initial,
            'final':    final,
            'sold_out': final == 0 and initial > 0,
        }

    # Per-agent plan records
    agent_plans = []
    for i in range(num_agents):
        ep   = agent_entrance_pos[i]
        plan = {
            'id':               i,
            'start':            f"{ep[0]},{ep[1]}",
            'start_label':      pos_to_entrance_lbl.get(ep, '?'),
            'shopping_list':    original_lists[i],
            'assigned_cashier': agent_cashier_lbl[i] if agent_cashier_lbl[i] else '尚未分配',
            'skipped_shelves':  agent_skipped[i],
        }
        if not agent_done[i]:
            plan['note'] = '超時未完成'
        agent_plans.append(plan)

    stats = {
        'agents':        num_agents,
        'makespan':      makespan,
        'sum_of_costs':  sum_of_costs,
        'agents_done':   sum(agent_done),
        'stub':          False,
        'shelf_index':   shelf_index,
        'cashier_index': cashier_index,
        'entrance_index': entrance_index,
        'agent_plans':   agent_plans,
        'shelf_stock':   shelf_stock,
    }
    return frames, stats
