"""GIF renderer for the MAPF shopping simulation."""
import io
import math

from PIL import Image, ImageDraw

# Map cell colours
_BG       = (232, 232, 232)   # EMPTY    (#e8e8e8)
_WALL     = (51, 65, 85)      # WALL     (#334155)
_SHELF    = (59, 130, 246)    # SHELF    (#3b82f6)
_CASHIER  = (34, 197, 94)     # CASHIER  (#22c55e)
_ENTRANCE = (249, 115, 22)    # ENTRANCE (#f97316)
_SOLD_OUT = (239, 68, 68)     # red X overlay

CELL = 9  # pixels per grid cell

# 20 distinct agent colours (cycling if >20 agents)
_AGENT_COLORS = [
    (255, 87, 34), (33, 150, 243), (76, 175, 80), (255, 193, 7),
    (156, 39, 176), (0, 188, 212), (255, 152, 0), (233, 30, 99),
    (0, 150, 136), (103, 58, 183), (244, 67, 54), (63, 81, 181),
    (139, 195, 74), (255, 235, 59), (121, 85, 72), (96, 125, 139),
    (230, 74, 25), (21, 101, 192), (46, 125, 50), (249, 168, 37),
]

# ── Pixel-art 5×3 digit bitmaps ───────────────────────────────────────────────
# Each entry: list of (row, col) pixels that are lit, in a 5-row × 3-col grid.
_PX_DIG = {
    '0': [(0,1),(1,0),(1,2),(2,0),(2,2),(3,0),(3,2),(4,1)],
    '1': [(0,1),(1,0),(1,1),(2,1),(3,1),(4,0),(4,1),(4,2)],
    '2': [(0,0),(0,1),(1,2),(2,0),(2,1),(3,0),(4,0),(4,1),(4,2)],
    '3': [(0,0),(0,1),(1,2),(2,1),(2,2),(3,2),(4,0),(4,1)],
    '4': [(0,0),(0,2),(1,0),(1,2),(2,0),(2,1),(2,2),(3,2),(4,2)],
    '5': [(0,0),(0,1),(0,2),(1,0),(2,0),(2,1),(3,2),(4,0),(4,1)],
    '6': [(0,1),(0,2),(1,0),(2,0),(2,1),(3,0),(3,2),(4,1)],
    '7': [(0,0),(0,1),(0,2),(1,2),(2,1),(3,1),(4,1)],
    '8': [(0,1),(1,0),(1,2),(2,1),(3,0),(3,2),(4,1)],
    '9': [(0,1),(1,0),(1,2),(2,1),(2,2),(3,2),(4,1)],
}

def _tiny_num(draw, n, x, y, fill=(255, 255, 255)):
    """Draw integer n as 5-px-tall pixel-art digits starting at pixel (x, y)."""
    dx = 0
    for ch in str(n):
        for pr, pc in _PX_DIG.get(ch, []):
            draw.point((x + dx + pc, y + pr), fill=fill)
        dx += 4  # 3 px wide + 1 px gap

def _num_width(n):
    """Pixel-art width of integer n."""
    return len(str(n)) * 4 - 1  # last char has no trailing gap

# ── Agent legend (right strip) constants ─────────────────────────────────────
_LEG_ROW_H  = 13   # px per legend row
_LEG_COL_W  = 44   # px per legend column
_LEG_COLS   = 2    # number of legend columns
_LEG_W      = _LEG_COL_W * _LEG_COLS  # total extra width on right


def _cell_color(cell_val):
    _MAP = {0: _BG, 1: _WALL, 2: _SHELF, 3: _CASHIER, 4: _ENTRANCE}
    return _MAP.get(cell_val, _BG)


def _draw_base(grid, initial_inventory,
               shelf_index=None, cashier_index=None, entrance_index=None,
               num_agents=0):
    """Render the static map with cell-index labels and a static agent legend."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    grid_w = cols * CELL
    grid_h = rows * CELL
    total_w = grid_w + (_LEG_W if num_agents > 0 else 0)

    img = Image.new('RGB', (total_w, grid_h), (30, 41, 59))  # dark bg
    draw = ImageDraw.Draw(img)

    # ── Grid cells ──────────────────────────────────────────────────────────
    for r in range(rows):
        for c in range(cols):
            color = _cell_color(grid[r][c])
            x0, y0 = c * CELL, r * CELL
            draw.rectangle([x0, y0, x0 + CELL - 1, y0 + CELL - 1], fill=color)

    # ── Cell index labels ───────────────────────────────────────────────────
    def _label(index_dict):
        if not index_dict:
            return
        for lbl, rc_str in index_dict.items():
            r, c = map(int, rc_str.split(','))
            num = int(lbl[1:])   # 'S12' → 12
            nw  = _num_width(num)
            nx  = c * CELL + max(0, (CELL - nw) // 2)
            ny  = r * CELL + (CELL - 5) // 2
            _tiny_num(draw, num, nx + 1, ny + 1, fill=(0, 0, 0))    # shadow
            _tiny_num(draw, num, nx,     ny,     fill=(255, 255, 255))  # white

    _label(shelf_index)
    _label(cashier_index)
    _label(entrance_index)

    # ── Static agent legend (right strip) ───────────────────────────────────
    if num_agents > 0:
        max_per_col = max(1, grid_h // _LEG_ROW_H)
        for i in range(num_agents):
            col_idx = i // max_per_col
            if col_idx >= _LEG_COLS:
                break
            row_idx = i % max_per_col
            lx = grid_w + 4 + col_idx * _LEG_COL_W
            ly = row_idx * _LEG_ROW_H + 4

            color = _AGENT_COLORS[i % len(_AGENT_COLORS)]
            # Colour swatch circle
            draw.ellipse([lx, ly + 1, lx + 7, ly + 8], fill=color)
            # Agent number label
            _tiny_num(draw, i + 1, lx + 10, ly + 3, fill=(200, 200, 200))

    return img


def _draw_frame(base_img, grid, frame_data, initial_inventory, frame_idx):
    """Composite one frame on top of the base map."""
    img = base_img.copy()
    draw = ImageDraw.Draw(img)

    inventory = frame_data['inventory']
    positions = frame_data['positions']
    done      = frame_data['done']

    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    # ── Sold-out X on shelves ────────────────────────────────────────────────
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 2 and inventory.get((r, c), 1) == 0:
                x0, y0 = c * CELL, r * CELL
                draw.line([x0, y0, x0 + CELL - 1, y0 + CELL - 1], fill=_SOLD_OUT, width=2)
                draw.line([x0 + CELL - 1, y0, x0, y0 + CELL - 1], fill=_SOLD_OUT, width=2)

    # ── Agent circles + index numbers ────────────────────────────────────────
    radius = max(2, CELL // 2 - 1)
    for i, pos in enumerate(positions):
        if pos is None:
            continue
        r, c = pos
        color = _AGENT_COLORS[i % len(_AGENT_COLORS)]
        cx = c * CELL + CELL // 2
        cy = r * CELL + CELL // 2

        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
        if done[i]:
            draw.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=(255, 255, 255))

        # Draw agent number centred on circle
        n  = i + 1
        nw = _num_width(n)
        nx = cx - nw // 2
        ny = cy - 2
        _tiny_num(draw, n, nx + 1, ny + 1, fill=(0, 0, 0))      # shadow
        _tiny_num(draw, n, nx,     ny,     fill=(255, 255, 255)) # white

    return img


def render_gif(grid, frames, products, stats=None, frame_duration_ms=100, max_frames=300):
    """Render simulation frames into a GIF bytes object.

    Parameters
    ----------
    grid              : 2D list of cell values
    frames            : list of frame dicts from simulation.run_simulation
    products          : original products dict (for initial inventory reference)
    stats             : optional stats dict (provides shelf/cashier/entrance index)
    frame_duration_ms : ms per frame
    max_frames        : cap to avoid huge GIFs
    """
    # Parse initial inventory
    initial_inventory = {}
    for key, info in products.items():
        parts = key.split(',')
        pos = (int(parts[0]), int(parts[1]))
        initial_inventory[pos] = int(info.get('stock', 1))

    num_agents = len(frames[0]['positions']) if frames else 0

    shelf_index    = (stats or {}).get('shelf_index')
    cashier_index  = (stats or {}).get('cashier_index')
    entrance_index = (stats or {}).get('entrance_index')

    base = _draw_base(grid, initial_inventory,
                      shelf_index, cashier_index, entrance_index,
                      num_agents)

    step     = max(1, math.ceil(len(frames) / max_frames))
    selected = frames[::step]

    pil_frames = []
    for f in selected:
        pil_frames.append(_draw_frame(base, grid, f, initial_inventory, len(pil_frames)))

    if not pil_frames:
        pil_frames = [base]

    buf = io.BytesIO()
    pil_frames[0].save(
        buf,
        format='GIF',
        save_all=True,
        append_images=pil_frames[1:],
        duration=frame_duration_ms,
        loop=0,
        optimize=False,
    )
    return buf.getvalue()
