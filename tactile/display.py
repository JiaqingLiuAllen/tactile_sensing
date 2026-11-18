# -*- coding: utf-8 -*-
"""
Shared 7x7 display helpers: panel orientation, high-contrast colormap, scaling.
"""

MATRIX_ROWS = 7
MATRIX_COLS = 7
MIN_SCALE_SPAN_V = 0.25
BASELINE_SEC = 1.0

# Physical panel corners, as currently printed before orientation:
#   top left  = C1R1, top right  = C1R7
#   low left  = C7R1, low right  = C7R7
# Transpose so the printed heatmap matches the panel:
#   x (left -> right) = R1..R7, y (top -> bottom) = C1..C7
DISPLAY_X_LABELS = [f"R{j + 1}" for j in range(MATRIX_ROWS)]
DISPLAY_Y_LABELS = [f"C{i + 1}" for i in range(MATRIX_COLS)]
DISPLAY_X_AXIS = "Row (panel left → right)"
DISPLAY_Y_AXIS = "Column (panel top → bottom)"

# Diverging colormap centered at zero change. Resting cells stay near gray.
COLORMAP_STOPS = [
    (0.00, "#08306b"),
    (0.18, "#2171b5"),
    (0.34, "#9ecae1"),
    (0.47, "#c5d0dc"),
    (0.53, "#c5d0dc"),
    (0.66, "#fcae91"),
    (0.82, "#ef3b2c"),
    (1.00, "#99000d"),
]


def orient_matrix(matrix):
    """Return a copy whose on-screen layout matches the physical panel."""
    return matrix.T.copy()


def make_colormap():
    import matplotlib.colors as mcolors

    colors = [color for _, color in COLORMAP_STOPS]
    positions = [stop for stop, _ in COLORMAP_STOPS]
    return mcolors.LinearSegmentedColormap.from_list(
        "tactile_contrast", list(zip(positions, colors))
    )


def deformation_from_baseline(values, baseline):
    import numpy as np

    delta = np.asarray(values, dtype=float) - np.asarray(baseline, dtype=float)
    return delta - np.median(delta)


def delta_scale(values, min_span=MIN_SCALE_SPAN_V, percentile=98):
    import numpy as np

    flat = np.abs(np.asarray(values, dtype=float).ravel())
    if flat.size == 0:
        half = 0.5 * min_span
        return -half, half
    half = max(float(np.percentile(flat, percentile)), 0.5 * min_span)
    pad = 0.08 * half
    return -(half + pad), half + pad


def upsample_bilinear(matrix, factor=4):
    import numpy as np

    rows, cols = matrix.shape
    ys = np.linspace(0, rows - 1, (rows - 1) * factor + 1)
    xs = np.linspace(0, cols - 1, (cols - 1) * factor + 1)
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    y1 = np.clip(y0 + 1, 0, rows - 1)
    x1 = np.clip(x0 + 1, 0, cols - 1)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    z00 = matrix[np.ix_(y0, x0)]
    z01 = matrix[np.ix_(y0, x1)]
    z10 = matrix[np.ix_(y1, x0)]
    z11 = matrix[np.ix_(y1, x1)]
    return z00 * (1 - fy) * (1 - fx) + z01 * (1 - fy) * fx + z10 * fy * (1 - fx) + z11 * fy * fx
