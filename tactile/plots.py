"""Matplotlib views shared by live capture and file replay."""

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

from .display import (
    MATRIX_ROWS,
    MATRIX_COLS,
    DISPLAY_X_AXIS,
    DISPLAY_X_LABELS,
    DISPLAY_Y_AXIS,
    DISPLAY_Y_LABELS,
    make_colormap,
    upsample_bilinear,
)


SHOW_NUMBERS = True
DECIMALS = 2
BAR_WIDTH = 0.75
TEXT_Z_OFFSET_FRACTION = 0.02


def create_view(first_matrix, vmin, vmax):
    cmap = make_colormap()
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    fig = plt.figure(figsize=(18.5, 7.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.82, 0.82, 1.85], wspace=0.16)
    ax_matrix = fig.add_subplot(gs[0, 0])
    ax_bar = fig.add_subplot(gs[0, 1], projection="3d")
    ax_surf = fig.add_subplot(gs[0, 2], projection="3d")

    heatmap = ax_matrix.imshow(
        first_matrix, cmap=cmap, norm=norm, origin="upper", interpolation="nearest"
    )
    fig.colorbar(
        heatmap, ax=[ax_matrix, ax_bar, ax_surf], shrink=0.75, pad=0.03, label="ΔV from rest (V)"
    )

    ax_matrix.set_xticks(np.arange(MATRIX_COLS))
    ax_matrix.set_yticks(np.arange(MATRIX_ROWS))
    ax_matrix.set_xticklabels(DISPLAY_X_LABELS)
    ax_matrix.set_yticklabels(DISPLAY_Y_LABELS)
    ax_matrix.set_xlabel(DISPLAY_X_AXIS)
    ax_matrix.set_ylabel(DISPLAY_Y_AXIS)
    ax_matrix.set_xticks(np.arange(-0.5, MATRIX_COLS, 1), minor=True)
    ax_matrix.set_yticks(np.arange(-0.5, MATRIX_ROWS, 1), minor=True)
    ax_matrix.grid(which="minor", color="white", linewidth=0.5)
    ax_matrix.tick_params(axis="x", labelrotation=45)

    x_positions, y_positions = np.meshgrid(np.arange(MATRIX_COLS), np.arange(MATRIX_ROWS))
    x_positions = x_positions.ravel()
    y_positions = y_positions.ravel()
    z_positions = np.zeros(MATRIX_ROWS * MATRIX_COLS)
    dx = np.full(MATRIX_ROWS * MATRIX_COLS, BAR_WIDTH)
    dy = np.full(MATRIX_ROWS * MATRIX_COLS, BAR_WIDTH)
    surf_y, surf_x = np.meshgrid(
        np.linspace(0, MATRIX_ROWS - 1, (MATRIX_ROWS - 1) * 3 + 1),
        np.linspace(0, MATRIX_COLS - 1, (MATRIX_COLS - 1) * 3 + 1),
        indexing="ij",
    )

    ax_bar.set_xlabel(DISPLAY_X_AXIS)
    ax_bar.set_ylabel(DISPLAY_Y_AXIS)
    ax_bar.set_zlabel("ΔV from rest (V)")
    ax_bar.set_xlim(-0.25, MATRIX_COLS - 0.25)
    ax_bar.set_ylim(MATRIX_ROWS - 0.25, -0.25)
    ax_bar.set_zlim(vmin, vmax)
    ax_bar.set_xticks(np.arange(MATRIX_COLS) + BAR_WIDTH / 2)
    ax_bar.set_yticks(np.arange(MATRIX_ROWS) + BAR_WIDTH / 2)
    ax_bar.set_xticklabels(DISPLAY_X_LABELS)
    ax_bar.set_yticklabels(DISPLAY_Y_LABELS)
    ax_bar.tick_params(axis="x", labelrotation=45)
    ax_bar.view_init(elev=30, azim=-55)

    ax_surf.set_xlabel(DISPLAY_X_AXIS)
    ax_surf.set_ylabel(DISPLAY_Y_AXIS)
    ax_surf.set_zlabel("ΔV from rest (V)")
    ax_surf.set_xlim(0, MATRIX_COLS - 1)
    ax_surf.set_ylim(MATRIX_ROWS - 1, 0)
    ax_surf.set_zlim(vmin, vmax)
    ax_surf.view_init(elev=28, azim=-55)

    def draw_bars(matrix):
        heights = matrix.ravel()
        colors = cmap(norm(heights))
        return ax_bar.bar3d(
            x_positions, y_positions, z_positions, dx, dy, heights, color=colors, shade=True
        )

    def draw_surface(matrix):
        z_up = upsample_bilinear(matrix, 3)
        return ax_surf.plot_surface(
            surf_x,
            surf_y,
            z_up,
            cmap=cmap,
            norm=norm,
            linewidth=0,
            antialiased=True,
            shade=True,
        )

    matrix_labels = []
    bar_labels = []
    if SHOW_NUMBERS:
        for row in range(MATRIX_ROWS):
            for col in range(MATRIX_COLS):
                matrix_labels.append(
                    ax_matrix.text(
                        col, row, "", ha="center", va="center", color="black", fontsize=8
                    )
                )

    bar_collection = draw_bars(first_matrix)
    surface_collection = draw_surface(first_matrix)

    def update(matrix, title, limits=None):
        nonlocal bar_collection, surface_collection, bar_labels
        if limits is not None:
            lo, hi = limits
            heatmap.set_clim(lo, hi)
            ax_bar.set_zlim(lo, hi)
            ax_surf.set_zlim(lo, hi)
        heatmap.set_data(matrix)
        bar_collection.remove()
        surface_collection.remove()
        for label in bar_labels:
            label.remove()
        bar_labels = []
        bar_collection = draw_bars(matrix)
        surface_collection = draw_surface(matrix)

        artists = [heatmap, bar_collection, surface_collection]
        if SHOW_NUMBERS:
            z_offset = max(norm.vmax - norm.vmin, 1.0) * TEXT_Z_OFFSET_FRACTION
            for row in range(MATRIX_ROWS):
                for col in range(MATRIX_COLS):
                    label_index = row * MATRIX_COLS + col
                    value = matrix[row, col]
                    matrix_labels[label_index].set_text(f"{value:+.{DECIMALS}f}")
                    artists.append(matrix_labels[label_index])
                    bar_labels.append(
                        ax_bar.text(
                            col + BAR_WIDTH / 2,
                            row + BAR_WIDTH / 2,
                            value + z_offset if value >= 0 else value - z_offset,
                            f"{value:+.{DECIMALS}f}",
                            ha="center",
                            va="bottom" if value >= 0 else "top",
                            fontsize=6,
                            color="black",
                        )
                    )
            artists.extend(bar_labels)

        fig.suptitle(title)
        return artists

    return fig, update
