# -*- coding: utf-8 -*-
"""
Replay saved 7x7 matrix CSV data.

Default: export/open the interactive HTML replay in the browser.
Use --matplotlib for the slower matplotlib animation.
"""

import argparse
import csv
import webbrowser
from pathlib import Path

from .export import DEFAULT_FRAME_INTERVAL_MS, export_csv_to_html, latest_csv
from .display import (
    BASELINE_SEC,
    MATRIX_COLS,
    MATRIX_ROWS,
    delta_scale,
    deformation_from_baseline,
    orient_matrix,
)


def load_frames(csv_path):
    import numpy as np

    value_columns = [f"R{i+1}C{j+1}" for i in range(MATRIX_ROWS) for j in range(MATRIX_COLS)]
    frames = []
    display_times = []
    timestamps = []

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        missing_columns = [column for column in value_columns if column not in fieldnames]
        if missing_columns:
            raise SystemExit(f"{csv_path} is missing columns: {', '.join(missing_columns[:5])}")

        for row in reader:
            values = [float(row[column]) for column in value_columns]
            frames.append(np.array(values, dtype=float).reshape((MATRIX_ROWS, MATRIX_COLS)))
            if "elapsed_sec" in fieldnames and row.get("elapsed_sec"):
                display_times.append(float(row["elapsed_sec"]))
            else:
                display_times.append(len(frames) * DEFAULT_FRAME_INTERVAL_MS / 1000)
            timestamps.append(row.get("timestamp_iso", ""))

    if not frames:
        raise SystemExit(f"{csv_path} has no matrix frames")

    return frames, display_times, timestamps


def choose_frame_interval_ms(display_times, speed, fixed_interval_ms):
    if fixed_interval_ms is not None:
        return fixed_interval_ms
    if len(display_times) < 2:
        return DEFAULT_FRAME_INTERVAL_MS

    duration_sec = display_times[-1] - display_times[0]
    if duration_sec <= 0:
        return DEFAULT_FRAME_INTERVAL_MS

    frame_interval_ms = duration_sec * 1000 / (len(display_times) - 1) / speed
    return max(1, int(round(frame_interval_ms)))


def build_animation(frames, display_times, timestamps, frame_interval_ms, source_name):
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt
    import numpy as np

    from .plots import create_view

    display_frames = []
    t0 = display_times[0]
    baseline_mats = [frame for frame, t in zip(frames, display_times) if t - t0 <= BASELINE_SEC]
    if not baseline_mats:
        baseline_mats = [frames[0]]
    baseline = np.mean(np.stack(baseline_mats), axis=0)
    for frame in frames:
        display_frames.append(orient_matrix(deformation_from_baseline(frame, baseline)))
    vmin, vmax = delta_scale(np.stack(display_frames))
    fig, draw = create_view(display_frames[0], vmin, vmax)

    def update(frame_index):
        elapsed = display_times[frame_index] - t0
        timestamp = timestamps[frame_index]
        title = f"{source_name} | t={elapsed:.3f}s"
        if timestamp:
            title += f" | {timestamp}"
        return draw(display_frames[frame_index], title)

    update(0)
    ani = animation.FuncAnimation(
        fig,
        update,
        frames=len(frames),
        interval=frame_interval_ms,
        blit=False,
        repeat=True,
        cache_frame_data=False,
    )
    return fig, ani


def html_path_for_csv(csv_path):
    return csv_path.with_suffix(".html")


def resolve_source_path(path, data_dir):
    if path is None:
        return latest_csv(data_dir)
    if path.suffix.lower() == ".html":
        csv_path = path.with_suffix(".csv")
        if not csv_path.exists() and not path.exists():
            raise SystemExit(f"Neither {path} nor {csv_path} exists")
        return csv_path if csv_path.exists() else path
    return path


def ensure_html(csv_path):
    html_path = html_path_for_csv(csv_path)
    if html_path.exists() and html_path.stat().st_mtime >= csv_path.stat().st_mtime:
        return html_path
    return export_csv_to_html(csv_path, html_path)


def open_html(html_path):
    import subprocess
    import sys

    html_path = html_path.resolve()
    if sys.platform == "darwin":
        subprocess.run(["open", str(html_path)], check=False)
        return
    opened = webbrowser.open(html_path.as_uri())
    if not opened:
        raise SystemExit(f"Could not open {html_path} in a browser")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replay saved 7x7 matrix data. Defaults to opening HTML in the browser."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help="CSV or HTML file to replay. Defaults to the newest recordings/matrix_7x7_*.csv",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("recordings"),
        help="Directory used when csv_path is omitted.",
    )
    parser.add_argument(
        "--matplotlib",
        action="store_true",
        help="Use the slower matplotlib animation instead of HTML.",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Export HTML if needed, but do not open the browser."
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Matplotlib playback speed multiplier. Every CSV frame is still shown.",
    )
    parser.add_argument(
        "--interval-ms",
        type=int,
        default=None,
        help="Matplotlib per-frame interval. Every CSV frame is still shown.",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Optional matplotlib output path ending in .gif or .mp4.",
    )
    parser.add_argument(
        "--show", action="store_true", help="Show the matplotlib animation window after saving."
    )
    return parser.parse_args()


def replay_html(source_path, open_browser):
    if source_path.suffix.lower() == ".html":
        html_path = source_path
    else:
        html_path = ensure_html(source_path)
    print(f"HTML replay: {html_path}")
    if open_browser:
        open_html(html_path)
        print(f"Opened {html_path} in the browser")
    else:
        print("HTML is ready. Pass without --no-open to launch it in the browser.")


def replay_matplotlib(csv_path, args):
    import matplotlib.pyplot as plt

    if args.speed <= 0:
        raise SystemExit("--speed must be greater than 0")
    if csv_path.suffix.lower() != ".csv":
        raise SystemExit("--matplotlib requires a CSV file")

    frames, display_times, timestamps = load_frames(csv_path)
    frame_interval_ms = choose_frame_interval_ms(display_times, args.speed, args.interval_ms)

    print(f"Replaying {len(frames)} frames from {csv_path}")
    print(f"CSV duration: {display_times[-1] - display_times[0]:.3f} s")
    print(f"Per-frame interval: {frame_interval_ms} ms")
    print("Replay displays every CSV frame in order without skipping.")

    fig, ani = build_animation(frames, display_times, timestamps, frame_interval_ms, csv_path.name)

    if args.save:
        suffix = args.save.suffix.lower()
        if suffix == ".gif":
            ani.save(args.save, writer="pillow", fps=max(1, int(1000 / frame_interval_ms)))
        elif suffix == ".mp4":
            ani.save(args.save, writer="ffmpeg", fps=max(1, int(1000 / frame_interval_ms)))
        else:
            raise SystemExit("--save output must end in .gif or .mp4")
        print(f"Saved animation to {args.save}")

    if args.show or args.save is None:
        plt.show()
    else:
        plt.close(fig)


def main():
    args = parse_args()
    source_path = resolve_source_path(args.csv_path, args.data_dir)

    if args.matplotlib or args.save is not None:
        replay_matplotlib(source_path, args)
        return

    replay_html(source_path, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
