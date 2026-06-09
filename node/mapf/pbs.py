"""Priority-Based Search (PBS) — plans all agents in priority order.

Each agent plans a shortest path to its current target using Time-Expanded A*,
treating all higher-priority agents' paths as reserved cells.
"""
from .astar import astar


def _path_to_reserved(path, goal_reserve=200):
    """Convert a path [(r,c),...] to a set of (r,c,t) reserved cells."""
    s = set()
    for t, (r, c) in enumerate(path):
        s.add((r, c, t))
    # Agent stays at goal for goal_reserve extra steps after arriving
    if path and goal_reserve > 0:
        gr, gc = path[-1]
        last_t = len(path) - 1
        for extra in range(1, goal_reserve + 1):
            s.add((gr, gc, last_t + extra))
    return s


def plan_agents(grid, starts, targets, max_t=500, goal_reserve=200):
    """Plan paths for all agents using PBS (fixed priority = agent index order).

    Parameters
    ----------
    grid         : 2D list (rows x cols), cell values 0/1/2/3
    starts       : list of (r, c), one per agent
    targets      : list of (r, c), one per agent (current target)
    max_t        : time horizon
    goal_reserve : extra steps to hold the goal cell reserved after arrival

    Returns
    -------
    paths : list of paths (each a list of (r,c)), same length as starts.
            Failed agents get a single-cell path [start].
    """
    n = len(starts)
    paths = [None] * n
    reserved = set()

    for i in range(n):
        path = astar(grid, starts[i], targets[i], reserved, max_t)
        if path is None:
            # Fallback: stay in place
            path = [starts[i]] * min(10, max_t)
        paths[i] = path
        reserved |= _path_to_reserved(path, goal_reserve)

    return paths
