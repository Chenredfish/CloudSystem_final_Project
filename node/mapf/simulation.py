"""Simulation controller for the shopping MAPF scenario.

Runs the full multi-agent shopping simulation with staggered spawn from entrance cells:
  1. Build shelf/cashier/entrance index (row-major scan order → S1/C1/E1 labels)
  2. Generate shopping lists and assign cashiers (seed-controlled)
  3. Staggered spawn: first num_entrances agents at step 0, then one per spawn_interval
  4. PBS planning loop: each spawned agent pursues its current target
  5. Inventory events: first arrival claims stock; sold-out shelves are skipped
  6. Returns frames for GIF rendering + expanded stats dict
"""
import random

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


def run_simulation(grid, products, num_agents, list_size, max_steps, seed,
                   spawn_interval=0, min_t_floor=50, goal_reserve=200):
    """Run the shopping simulation with staggered spawn from entrance cells.

    Raises ValueError if no entrance cells or no cashier cells are found.

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

    # Build label dicts (row-major scan order)
    shelf_index    = _build_index(shelf_cells,    'S')
    cashier_index  = _build_index(cashier_cells,  'C')
    entrance_index = _build_index(entrance_cells, 'E')

    # Reverse lookups: (r,c) → label
    pos_to_shelf_lbl    = {_to_pos(rc): lbl for lbl, rc in shelf_index.items()}
    pos_to_cashier_lbl  = {_to_pos(rc): lbl for lbl, rc in cashier_index.items()}
    pos_to_entrance_lbl = {_to_pos(rc): lbl for lbl, rc in entrance_index.items()}

    # Inventory: (r,c) → stock
    inventory = {}
    for key, info in products.items():
        inventory[_to_pos(key)] = int(info.get('stock', 1))

    init_stock = {lbl: inventory.get(_to_pos(rc), 3) for lbl, rc in shelf_index.items()}

    # Generate per-agent shopping lists (S-labels)
    rng = random.Random(seed)
    shelf_labels   = list(shelf_index.keys())
    cashier_labels = list(cashier_index.keys())

    original_lists = []
    for _ in range(num_agents):
        chosen = rng.sample(shelf_labels, min(list_size, len(shelf_labels))) if shelf_labels else []
        original_lists.append(list(chosen))

    # Working todo queues as (r,c) tuples
    agent_todos = [[_to_pos(shelf_index[lbl]) for lbl in lst] for lst in original_lists]

    # Assign one cashier per agent
    rng_cashier = random.Random(seed + 2)
    agent_cashier_lbl = [rng_cashier.choice(cashier_labels) for _ in range(num_agents)]
    agent_cashier_pos = [_to_pos(cashier_index[lbl]) for lbl in agent_cashier_lbl]

    # Staggered spawn schedule
    num_entrances = len(entrance_cells)
    if spawn_interval <= 0:
        spawn_interval = max(3, 60 // num_agents)
    rng_spawn      = random.Random(seed + 1)
    shuffled_ent   = list(entrance_cells)
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

    # Simulation state
    positions     = [None] * num_agents   # None = not yet spawned
    agent_done    = [False] * num_agents
    agent_phase   = ['shop'] * num_agents  # 'shop' or 'checkout'
    agent_target  = [None] * num_agents
    agent_skipped = [[] for _ in range(num_agents)]  # S-labels skipped (sold-out)

    frames = []
    sum_of_costs = 0

    def _assign_target(i):
        """Return next target (r,c) for agent i. Skips sold-out shelves in-place."""
        while agent_todos[i]:
            tgt = agent_todos[i][0]
            if inventory.get(tgt, 0) > 0:
                return tgt
            # Sold out — skip and record
            lbl = pos_to_shelf_lbl.get(tgt, f"{tgt[0]},{tgt[1]}")
            if lbl not in agent_skipped[i]:
                agent_skipped[i].append(lbl)
            agent_todos[i].pop(0)
        # All items done → go to assigned cashier
        agent_phase[i] = 'checkout'
        return agent_cashier_pos[i]

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
                agent_target[i] = _assign_target(i)

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
                        agent_target[i] = _assign_target(i)
                    elif agent_phase[i] == 'checkout':
                        agent_done[i] = True
                        sum_of_costs += step + 1

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
        pos = _to_pos(rc)
        final = inventory.get(pos, 0)
        initial = init_stock[lbl]
        shelf_stock[lbl] = {
            'initial': initial,
            'final': final,
            'sold_out': final == 0 and initial > 0,
        }

    # Per-agent plan records
    agent_plans = []
    for i in range(num_agents):
        ep  = agent_entrance_pos[i]
        plan = {
            'id': i,
            'start': f"{ep[0]},{ep[1]}",
            'start_label': pos_to_entrance_lbl.get(ep, '?'),
            'shopping_list': original_lists[i],
            'assigned_cashier': agent_cashier_lbl[i],
            'skipped_shelves': agent_skipped[i],
        }
        if not agent_done[i]:
            plan['note'] = '超時未完成'
        agent_plans.append(plan)

    stats = {
        'agents': num_agents,
        'makespan': makespan,
        'sum_of_costs': sum_of_costs,
        'agents_done': sum(agent_done),
        'stub': False,
        'shelf_index':    shelf_index,
        'cashier_index':  cashier_index,
        'entrance_index': entrance_index,
        'agent_plans': agent_plans,
        'shelf_stock': shelf_stock,
    }
    return frames, stats
