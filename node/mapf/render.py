"""GIF renderer for the MAPF shopping simulation."""
import io
import math

from PIL import Image, ImageDraw

# Map cell colours
_BG = (232, 232, 232)       # EMPTY
_WALL = (51, 65, 85)        # WALL  (#334155)
_SHELF = (59, 130, 246)     # SHELF (#3b82f6)
_CASHIER = (34, 197, 94)    # CASHIER (#22c55e)
_SOLD_OUT = (239, 68, 68)   # red X overlay

CELL = 9  # pixels per grid cell (matches frontend)

# 20 distinct agent colours (cycling if more agents)
_AGENT_COLORS = [
    (255, 87, 34), (33, 150, 243), (76, 175, 80), (255, 193, 7),
    (156, 39, 176), (0, 188, 212), (255, 152, 0), (233, 30, 99),
    (0, 150, 136), (103, 58, 183), (244, 67, 54), (63, 81, 181),
    (139, 195, 74), (255, 235, 59), (121, 85, 72), (96, 125, 139),
    (230, 74, 25), (21, 101, 192), (46, 125, 50), (249, 168, 37),
]


def _cell_color(cell_val):
    return [_BG, _WALL, _SHELF, _CASHIER][cell_val] if 0 <= cell_val <= 3 else _BG


def _draw_base(grid, initial_inventory):
    """Render the static map as a PIL Image."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    img = Image.new('RGB', (cols * CELL, rows * CELL), _BG)
    draw = ImageDraw.Draw(img)
    for r in range(rows):
        for c in range(cols):
            color = _cell_color(grid[r][c])
            x0, y0 = c * CELL, r * CELL
            draw.rectangle([x0, y0, x0 + CELL - 1, y0 + CELL - 1], fill=color)
    return img


def _draw_frame(base_img, grid, frame_data, initial_inventory, frame_idx):
    """Composite one frame on top of the base map."""
    img = base_img.copy()
    draw = ImageDraw.Draw(img)

    inventory = frame_data['inventory']
    positions = frame_data['positions']
    done = frame_data['done']

    # Draw sold-out X on shelves with 0 stock
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 2:
                key = (r, c)
                if inventory.get(key, 1) == 0:
                    x0, y0 = c * CELL, r * CELL
                    draw.line([x0, y0, x0 + CELL - 1, y0 + CELL - 1], fill=_SOLD_OUT, width=2)
                    draw.line([x0 + CELL - 1, y0, x0, y0 + CELL - 1], fill=_SOLD_OUT, width=2)

    # Draw agents as coloured circles
    radius = max(2, CELL // 2 - 1)
    for i, (r, c) in enumerate(positions):
        color = _AGENT_COLORS[i % len(_AGENT_COLORS)]
        cx, cy = c * CELL + CELL // 2, r * CELL + CELL // 2
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
        if done[i]:
            # White dot in centre for "done" agents
            draw.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=(255, 255, 255))

    return img


def render_gif(grid, frames, products, frame_duration_ms=100, max_frames=300):
    """Render simulation frames into a GIF bytes object.

    Parameters
    ----------
    grid              : 2D list of cell values
    frames            : list of frame dicts from simulation.run_simulation
    products          : original products dict (for initial inventory reference)
    frame_duration_ms : ms per frame
    max_frames        : cap to avoid huge GIFs

    Returns
    -------
    bytes of the GIF file
    """
    # Parse initial inventory from products
    initial_inventory = {}
    for key, info in products.items():
        parts = key.split(',')
        pos = (int(parts[0]), int(parts[1]))
        initial_inventory[pos] = int(info.get('stock', 1))

    base = _draw_base(grid, initial_inventory)

    step = max(1, math.ceil(len(frames) / max_frames))
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
