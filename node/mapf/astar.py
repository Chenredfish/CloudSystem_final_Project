"""Time-Expanded A* for a single agent with reserved-cell constraints."""
import heapq


def heuristic(r, c, goal_r, goal_c):
    return abs(r - goal_r) + abs(c - goal_c)


# (dr, dc) for wait + 4 moves
_MOVES = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]


def astar(grid, start, goal, reserved, max_t=500):
    """Return path as list of (r, c) from start to goal (inclusive), or None.

    grid      : 2D list, 0=passable EMPTY, 1=WALL, 2=SHELF, 3=CASHIER
                Cells with type SHELF/CASHIER are treated as obstacles UNLESS
                they are the goal cell.
    start     : (r, c)
    goal      : (r, c)
    reserved  : set of (r, c, t) that are occupied by other agents.
    max_t     : time horizon (abort if exceeded).
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    def passable(r, c):
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return False
        cell = grid[r][c]
        if (r, c) == goal:
            return True
        return cell in (0, 4)  # EMPTY and ENTRANCE are traversable mid-path

    sr, sc = start
    gr, gc = goal

    if not passable(sr, sc) and (sr, sc) != start:
        return None

    # heap: (f, g, r, c, t, parent_index)
    # We store states in a list and use indices for parent tracking
    open_heap = []
    h0 = heuristic(sr, sc, gr, gc)
    heapq.heappush(open_heap, (h0, 0, sr, sc, 0, -1))

    states = []  # list of (r, c, t, parent_idx)
    visited = {}  # (r, c, t) -> g

    while open_heap:
        f, g, r, c, t, par = heapq.heappop(open_heap)

        state_key = (r, c, t)
        if state_key in visited and visited[state_key] <= g:
            continue
        visited[state_key] = g

        idx = len(states)
        states.append((r, c, t, par))

        if (r, c) == (gr, gc):
            path = []
            i = idx
            while i != -1:
                sr2, sc2, _, pi = states[i]
                path.append((sr2, sc2))
                i = pi
            path.reverse()
            return path

        if t >= max_t:
            continue

        nt = t + 1
        for dr, dc in _MOVES:
            nr, nc = r + dr, c + dc
            if not passable(nr, nc):
                continue
            if (nr, nc, nt) in reserved:
                continue
            # vertex conflict: check if another agent sits there at nt
            # edge conflict: check swap (r,c) ↔ (nr,nc) between t and nt
            if (r, c, nt) in reserved and (nr, nc) == (r, c):
                continue
            ng = g + 1
            if (nr, nc, nt) in visited and visited[(nr, nc, nt)] <= ng:
                continue
            nh = heuristic(nr, nc, gr, gc)
            heapq.heappush(open_heap, (ng + nh, ng, nr, nc, nt, idx))

    return None  # no path found
