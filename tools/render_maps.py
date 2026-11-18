"""Rebuild the README figures from an analytic signal on a 7 × 7 grid."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from PIL import Image

from tactile.display import deformation_from_baseline, orient_matrix, upsample_bilinear

FIGURES = Path(__file__).resolve().parents[1] / "docs" / "figures"
BACKGROUND, TEXT, MUTED = "#ffffff", "#1d1d1f", "#5d6068"
SCALE = Normalize(-0.65, 0.65)
PALETTE = LinearSegmentedColormap.from_list(
    "voltage",
    ["#1163ce", "#579ef1", "#a1c9f0", "#dcdde1", "#f4c6ab", "#f18e62", "#ce512c"],
)
ROW, COL = np.indices((7, 7), dtype=float)
LATTICE_X, LATTICE_Y = np.meshgrid(np.arange(1, 8), np.arange(1, 8))
FINE_X, FINE_Y = np.meshgrid(np.linspace(1, 7, 37), np.linspace(1, 7, 37))


def simulated_frame(phase):
    """Two moving voltage lobes, sampled at the scanner's 49 cell centers."""
    angle = 2 * np.pi * phase
    x1, y1 = 2.1 + 0.85 * np.cos(angle), 2.0 + 0.85 * np.sin(angle)
    x2, y2 = 4.4 - 0.65 * np.sin(angle), 4.1 - 0.7 * np.cos(angle)
    warm = 0.68 * np.exp(-((ROW - x1) ** 2 / 1.55 + (COL - y1) ** 2 / 2.1))
    cool = 0.55 * np.exp(-((ROW - x2) ** 2 / 1.9 + (COL - y2) ** 2 / 1.5))
    rest = np.full(ROW.shape, 1.65)
    return orient_matrix(deformation_from_baseline(rest + warm - cool, rest))


def make_figure():
    fig = plt.figure(figsize=(11.2, 5), dpi=105, facecolor=BACKGROUND)
    fig.text(0.055, 0.89, "2D sensor array", color=TEXT, size=20, weight="semibold")
    fig.text(0.535, 0.89, "3D voltage surface", color=TEXT, size=20, weight="semibold")
    fig.text(0.055, 0.83, "One dot per sensing cell", color=MUTED, size=11)
    fig.text(0.535, 0.83, "Dots mark the same 49 samples", color=MUTED, size=11)
    fig.add_artist(
        Line2D([0.483, 0.483], [0.16, 0.93], transform=fig.transFigure, color="#dbe2e8", lw=0.8)
    )

    heat = fig.add_axes([0.063, 0.173, 0.355, 0.60], facecolor=BACKGROUND)
    heat.set_aspect("equal")
    heat.set_xlim(0.5, 7.5)
    heat.set_ylim(7.5, 0.5)
    heat.set_xticks(range(1, 8), labels=[f"R{i}" for i in range(1, 8)])
    heat.set_yticks(range(1, 8), labels=[f"C{i}" for i in range(1, 8)])
    heat.tick_params(colors=MUTED, length=0, labelsize=9, pad=5)
    heat.spines[:].set_visible(False)
    dots = heat.scatter(
        LATTICE_X.ravel(),
        LATTICE_Y.ravel(),
        c=np.zeros(LATTICE_X.size),
        s=158,
        cmap=PALETTE,
        norm=SCALE,
        edgecolors="none",
    )

    ax = fig.add_axes([0.507, 0.081, 0.46, 0.735], projection="3d", facecolor=BACKGROUND,
                      computed_zorder=False)
    ax.set_proj_type("ortho")
    ax.view_init(elev=30, azim=-61)
    ax.set_box_aspect((1.25, 1, 0.82), zoom=1.07)
    ax.set(xlim=(1, 7), ylim=(7, 1), zlim=(-0.7, 0.7))
    ax.set_xticks([1, 4, 7], ["R1", "R4", "R7"])
    ax.set_yticks([1, 4, 7], ["C1", "C4", "C7"])
    ax.set_zticks([-0.6, 0, 0.6], ["−0.6 V", "0", "+0.6 V"])
    ax.tick_params(colors=MUTED, labelsize=8, pad=0)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor(BACKGROUND)
        axis.pane.set_edgecolor("#cbd5de")
        axis.line.set_color("#78899a")
        axis._axinfo["grid"].update(color="#c6d1dc", linewidth=0.45)

    fig.text(0.055, 0.058, "ΔV (V)", color=TEXT, size=10, weight="bold")
    bar_ax = fig.add_axes([0.13, 0.065, 0.237, 0.015])
    bar = fig.colorbar(dots, cax=bar_ax, orientation="horizontal", ticks=[-0.65, 0, 0.65])
    bar.ax.set_xticklabels(["−0.65", "0", "+0.65"])
    bar.ax.tick_params(labelsize=8, colors=MUTED, length=0, pad=3)
    bar.outline.set_visible(False)
    fig.text(0.956, 0.052, "Synthetic signal", ha="right", size=10, color=MUTED)
    return fig, dots, ax


def render():
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, dots, ax = make_figure()
    layers = []
    frames = []
    for index in range(48):
        for layer in layers:
            layer.remove()
        values = simulated_frame(index / 48)
        dots.set_array(values.ravel())
        surface = ax.plot_surface(
            FINE_X,
            FINE_Y,
            upsample_bilinear(values, 6),
            cmap=PALETTE,
            norm=SCALE,
            linewidth=0,
            antialiased=False,
        )
        samples = ax.scatter(
            LATTICE_X.ravel(), LATTICE_Y.ravel(), values.ravel(),
            c=values.ravel(), s=23, cmap=PALETTE, norm=SCALE, depthshade=False,
            edgecolors=BACKGROUND, linewidths=0.8, zorder=3,
        )
        layers = [surface, samples]
        if index == 0:
            fig.savefig(FIGURES / "tactile-maps.png", dpi=160, facecolor=BACKGROUND)
        fig.canvas.draw()
        frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()))
    plt.close(fig)
    # Share one palette across the loop so stationary labels keep their color.
    palette = frames[0].quantize(colors=256)
    images = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    # Quantization can turn the white canvas light gray. Keep its GIF swatch exact.
    colors = images[0].getpalette()
    start = 3 * images[0].getpixel((0, 0))
    colors[start : start + 3] = [255, 255, 255]
    for image in images:
        image.putpalette(colors)
    images[0].save(
        FIGURES / "tactile-maps.gif",
        save_all=True,
        append_images=images[1:],
        duration=90,
        loop=0,
        disposal=1,
        optimize=True,
    )


if __name__ == "__main__":
    render()
