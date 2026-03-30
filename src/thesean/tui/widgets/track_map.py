"""Braille-rasterized track map for progress visualization."""

from __future__ import annotations

from rich.text import Text

# Braille dot positions: (col_offset, row_offset) -> bit index
# Unicode braille: U+2800 + bitmask
# Dot layout per cell (2 cols x 4 rows):
#   (0,0)=0x01  (1,0)=0x08
#   (0,1)=0x02  (1,1)=0x10
#   (0,2)=0x04  (1,2)=0x20
#   (0,3)=0x40  (1,3)=0x80
_DOT_MAP = {
    (0, 0): 0x01, (1, 0): 0x08,
    (0, 1): 0x02, (1, 1): 0x10,
    (0, 2): 0x04, (1, 2): 0x20,
    (0, 3): 0x40, (1, 3): 0x80,
}


def _bresenham(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Integer Bresenham line rasterization."""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return points


class BrailleTrackRaster:
    """Pre-rasterize a track shape into a braille pixel grid.

    Each pixel records its progress value (0.0–1.0) along the track.
    Rendering sweeps the grid, coloring pixels before the cutoff bright
    and after it dim.
    """

    def __init__(
        self,
        points: list[tuple[float, float]],
        cols: int = 25,
        rows: int = 10,
    ) -> None:
        self.cols = cols
        self.rows = rows
        # Pixel grid dimensions (2 dots per col, 4 dots per row)
        self.px_w = cols * 2
        self.px_h = rows * 4

        # pixel_progress: maps (px, py) -> progress float (0.0–1.0)
        self.pixel_progress: dict[tuple[int, int], float] = {}

        if len(points) < 2:
            return

        # Normalize points to pixel grid, preserving aspect ratio
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        range_x = max_x - min_x or 1.0
        range_y = max_y - min_y or 1.0

        # Preserve aspect ratio
        scale = min((self.px_w - 1) / range_x, (self.px_h - 1) / range_y)
        # Center in the grid
        off_x = (self.px_w - 1 - range_x * scale) / 2
        off_y = (self.px_h - 1 - range_y * scale) / 2

        def to_px(x: float, y: float) -> tuple[int, int]:
            px = int((x - min_x) * scale + off_x)
            py = int((y - min_y) * scale + off_y)
            return (
                max(0, min(self.px_w - 1, px)),
                max(0, min(self.px_h - 1, py)),
            )

        # Walk consecutive pairs, rasterize with Bresenham
        n = len(points)
        for i in range(n - 1):
            x0, y0 = to_px(*points[i])
            x1, y1 = to_px(*points[i + 1])
            progress_start = i / (n - 1)
            progress_end = (i + 1) / (n - 1)
            line_pts = _bresenham(x0, y0, x1, y1)
            for j, (px, py) in enumerate(line_pts):
                t = progress_start + (progress_end - progress_start) * (j / max(len(line_pts) - 1, 1))
                if (px, py) not in self.pixel_progress:
                    self.pixel_progress[(px, py)] = t

    def render(
        self,
        progress: float,
        color: str = "cyan",
        dim_color: str = "grey37",
    ) -> Text:
        """Render the track with pixels up to `progress` in color, rest dim."""
        text = Text()
        for row in range(self.rows):
            for col in range(self.cols):
                mask = 0
                min_prog = 2.0  # sentinel > 1.0
                for (dc, dr), bit in _DOT_MAP.items():
                    px = col * 2 + dc
                    py = row * 4 + dr
                    if (px, py) in self.pixel_progress:
                        mask |= bit
                        p = self.pixel_progress[(px, py)]
                        if p < min_prog:
                            min_prog = p

                if mask == 0:
                    text.append(" ")
                else:
                    ch = chr(0x2800 + mask)
                    style = color if min_prog <= progress else dim_color
                    text.append(ch, style=style)

            if row < self.rows - 1:
                text.append("\n")

        return text
