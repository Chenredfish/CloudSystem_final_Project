"""Simulation controller for the shopping MAPF scenario.

Runs the full multi-agent shopping simulation:
  1. Generate shopping lists (seed-controlled)
  2. PBS planning loop: each agent pursues its current target
  3. Inventory events: first arrival claims stock; others re-plan
  4. All agents end at any cashier
  5. Returns frame list for GIF rendering
"""
import random

from .pbs import plan_agents


def _find_cells(grid, cell_type):
    out = []
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v == cell_type:
                out.append((r, c))
    return out


def _gen_shopping_lists(products, num_agents, list_size, seed):
    """Generate per-agent shopping lists from available shelf cells."""
    rng = random.Random(seed)
    shelf_keys = list(products.keys())
    if not shelf_keys:
        return [[] for _ in range(num_agents)]
    lists = []
    for _ in range(num_agents):
        chosen = rng.sample(shelf_keys, min(list_size, len(shelf_keys)))
        lists.append(list(chosen))
    return lists


def _gen_starts(grid, num_agents, cashier_cells, seed):
    """Place agent starts on empty cells near cashiers (or random empty cells)."""
    rng = random.Random(seed + 1)
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    empty = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 0]
    rng.shuffle(empty)
    # prefer cells not at cashier positions
    cashier_set = set(cashier_cells)
    preferred = [p for p in empty if p not in cashier_set]
    pool = (preferred + [p for p in empty if p in cashier_set])[:num_agents * 3]
    used = set()
    starts = []
    for p in pool:
        if p not in used:
            starts.append(p)
            used.add(p)
        if len(starts) == num_agents:
            break
    # pad if not enough
    while len(starts) < num_agents:
        starts.append(starts[0] if starts else (1, 1))
    return starts


def run_simulation(grid, products, num_agents, list_size, max_steps, seed):
    """Run the full shopping simulation.

    Returns
    -------
    frames  : list of dicts, one per simulated timestep:
              {
                'positions': [(r,c), ...],    # per-agent position
                'inventory': {key: stock},    # remaining stock (copy)
                'done': [bool, ...],          # agent finished?
              }
    stats   : dict with makespan, sum_of_costs, agents_done
    """
    SHELF, CASHIER = 2, 3
    cashier_cells = _find_cells(grid, CASHIER)
    if not cashier_cells:
        # Create a fallback cashier at bottom-left empty cell
        for r in range(len(grid) - 2, 0, -1):
            for c in range(1, len(grid[0]) - 1):
                if grid[r][c] == 0:
                    cashier_cells = [(r, c)]
                    break
            if cashier_cells:
                break

    # Parse products keys from "r,c" strings to (r,c) tuples
    inventory = {}
    for key, info in products.items():
        parts = key.split(',')
        pos = (int(parts[0]), int(parts[1]))
        inventory[pos] = int(info.get('stock', 1))

    shopping_lists = _gen_shopping_lists(products, num_agents, list_size, seed)
    # Convert string keys to tuple keys in shopping lists
    agent_todos = []
    for lst in shopping_lists:
        todo = []
        for key in lst:
            parts = key.split(',')
            todo.append((int(parts[0]), int(parts[1])))
        agent_todos.append(todo)

    starts = _gen_starts(grid, num_agents, cashier_cells, seed)
    positions = list(starts)
    agent_done = [False] * num_agents

    # Current target for each agent (None = needs assignment)
    agent_target = [None] * num_agents
    agent_phase = ['shop'] * num_agents  # 'shop' or 'checkout'

    frames = []
    sum_of_costs = 0

    # Assign initial targets
    rng_cashier = random.Random(seed + 2)

    def _assign_target(i):
        if agent_todos[i]:
            # Next shelf target from shopping list
            target = agent_todos[i][0]
            if inventory.get(target, 0) <= 0:
                # Out of stock — skip it
                agent_todos[i].pop(0)
                return _assign_target(i)
            return target
        else:
            # Go to a cashier
            agent_phase[i] = 'checkout'
            return rng_cashier.choice(cashier_cells)

    for i in range(num_agents):
        agent_target[i] = _assign_target(i)

    for step in range(max_steps):
        active = [i for i in range(num_agents) if not agent_done[i]]
        if not active:
            break

        # Plan one step for all active agents simultaneously
        active_starts = [positions[i] for i in active]
        active_targets = [agent_target[i] for i in active]

        paths = plan_agents(grid, active_starts, active_targets, max_t=max(max_steps - step, 50))

        # Advance one step: each agent moves to paths[j][1] if available, else stays
        new_positions = list(positions)
        for j, i in enumerate(active):
            path = paths[j]
            if len(path) > 1:
                new_positions[i] = path[1]
            # else stay put

        # Detect arrivals (agents at their target)
        for j, i in enumerate(active):
            pos = new_positions[i]
            tgt = agent_target[i]

            if pos == tgt:
                if agent_phase[i] == 'shop':
                    # Try to claim item
                    if agent_todos[i] and agent_todos[i][0] == tgt:
                        if inventory.get(tgt, 0) > 0:
                            inventory[tgt] -= 1
                            agent_todos[i].pop(0)
                    # Get next target
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

    # Agents not done by max_steps
    for i in range(num_agents):
        if not agent_done[i]:
            sum_of_costs += max_steps

    makespan = len(frames)
    stats = {
        'agents': num_agents,
        'makespan': makespan,
        'sum_of_costs': sum_of_costs,
        'agents_done': sum(agent_done),
        'stub': False,
    }
    return frames, stats
