# -*- coding: utf-8 -*-
"""
Export a saved 7x7 matrix CSV as a self-contained interactive HTML replay.

The generated HTML embeds every CSV frame and provides a slider, play/pause,
and step controls. It uses browser canvas only, so it has no runtime
dependencies beyond a modern browser.
"""

import argparse
import csv
import json
from pathlib import Path

from .display import (
    BASELINE_SEC,
    COLORMAP_STOPS,
    DISPLAY_X_AXIS,
    DISPLAY_X_LABELS,
    DISPLAY_Y_AXIS,
    DISPLAY_Y_LABELS,
    MATRIX_COLS,
    MATRIX_ROWS,
    delta_scale,
    deformation_from_baseline,
)


DEFAULT_FRAME_INTERVAL_MS = 50


TEMPLATE_PATH = Path(__file__).with_name("templates") / "replay.html.in"


def latest_csv(data_dir):
    csv_files = sorted(data_dir.glob("matrix_7x7_*.csv"), key=lambda path: path.stat().st_mtime)
    if not csv_files:
        raise SystemExit(f"No matrix CSV files found in {data_dir}")
    return csv_files[-1]


def load_csv_data(csv_path, t_start=None, t_end=None, subsample_fps=None, play_interval_ms=None):
    value_columns = [f"R{i+1}C{j+1}" for i in range(MATRIX_ROWS) for j in range(MATRIX_COLS)]
    frames = []
    recorded_times = []
    device_times = []
    unit = "V"

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []
        missing_columns = [column for column in value_columns if column not in fieldnames]
        if missing_columns:
            raise SystemExit(f"{csv_path} is missing columns: {', '.join(missing_columns[:5])}")

        for index, row in enumerate(reader):
            if "elapsed_sec" in fieldnames and row.get("elapsed_sec"):
                recorded_time_sec = float(row["elapsed_sec"])
            else:
                recorded_time_sec = index * DEFAULT_FRAME_INTERVAL_MS / 1000
            if t_start is not None and recorded_time_sec < t_start:
                continue
            if t_end is not None and recorded_time_sec > t_end:
                continue
            values = [round(float(row[column]), 6) for column in value_columns]
            if row.get("value_unit"):
                unit = row["value_unit"]
            device_time_sec = (
                float(row["device_millis"]) / 1000
                if "device_millis" in fieldnames and row.get("device_millis")
                else None
            )
            recorded_times.append(recorded_time_sec)
            device_times.append(device_time_sec)
            frames.append(
                {
                    "timestamp": row.get("timestamp_iso", ""),
                    "device_frame": (
                        int(row["device_frame_index"])
                        if "device_frame_index" in fieldnames and row.get("device_frame_index")
                        else None
                    ),
                    "values": values,
                }
            )

    if not frames:
        raise SystemExit(f"{csv_path} has no matrix frames in the requested window")

    window_start = recorded_times[0]
    baseline_rows = [
        frames[i]["values"]
        for i, time_sec in enumerate(recorded_times)
        if time_sec - window_start <= BASELINE_SEC
    ]
    if not baseline_rows:
        baseline_rows = [frames[0]["values"]]
    n_base = len(baseline_rows)
    n_cells = MATRIX_ROWS * MATRIX_COLS
    baseline = [round(sum(row[idx] for row in baseline_rows) / n_base, 6) for idx in range(n_cells)]

    if subsample_fps and subsample_fps > 0 and len(frames) > 1:
        start_time = recorded_times[0]
        end_time = recorded_times[-1]
        step = 1.0 / subsample_fps
        targets = []
        t = start_time
        while t <= end_time + 1e-9:
            targets.append(t)
            t += step
        chosen = []
        used = set()
        for target in targets:
            idx = min(range(len(recorded_times)), key=lambda i: abs(recorded_times[i] - target))
            if idx in used:
                continue
            used.add(idx)
            chosen.append(idx)
        frames = [frames[i] for i in chosen]
        recorded_times = [recorded_times[i] for i in chosen]
        device_times = [device_times[i] for i in chosen]

    start_time = recorded_times[0]
    duration_sec = max(recorded_times[-1] - start_time, 0.0)
    if play_interval_ms is not None:
        frame_interval_ms = play_interval_ms
    else:
        frame_interval_ms = (
            duration_sec * 1000 / (len(frames) - 1)
            if len(frames) > 1 and duration_sec > 0
            else DEFAULT_FRAME_INTERVAL_MS
        )
    nominal_fps = 1000 / frame_interval_ms if frame_interval_ms > 0 else 0

    first_device_time = next((time for time in device_times if time is not None), None)
    for frame, time_sec, device_time_sec in zip(frames, recorded_times, device_times):
        frame["t"] = round(time_sec - start_time, 6)
        frame["elapsed_sec"] = round(time_sec, 6)
        frame["device_t"] = (
            round(device_time_sec - first_device_time, 6)
            if device_time_sec is not None and first_device_time is not None
            else None
        )

    deform_all = []
    for frame in frames:
        deform_all.extend(deformation_from_baseline(frame["values"], baseline).tolist())
    vmin, vmax = delta_scale(deform_all)

    return {
        "source_name": csv_path.name,
        "rows": MATRIX_ROWS,
        "cols": MATRIX_COLS,
        "vmin": round(vmin, 6),
        "vmax": round(vmax, 6),
        "min_scale_span": 0.25,
        "unit": f"Δ{unit}",
        "baseline": baseline,
        "baseline_sec": BASELINE_SEC,
        "x_labels": DISPLAY_X_LABELS,
        "y_labels": DISPLAY_Y_LABELS,
        "x_axis": DISPLAY_X_AXIS,
        "y_axis": DISPLAY_Y_AXIS,
        "color_stops": COLORMAP_STOPS,
        "duration_sec": round(duration_sec, 6),
        "frame_interval_ms": max(1, round(frame_interval_ms, 3)),
        "nominal_fps": round(nominal_fps, 3),
        "frames": frames,
    }


def export_csv_to_html(
    csv_path, output_path=None, t_start=None, t_end=None, subsample_fps=None, play_interval_ms=None
):
    csv_path = Path(csv_path)
    output_path = Path(output_path) if output_path else csv_path.with_suffix(".html")
    data = load_csv_data(
        csv_path,
        t_start=t_start,
        t_end=t_end,
        subsample_fps=subsample_fps,
        play_interval_ms=play_interval_ms,
    )
    html = TEMPLATE_PATH.read_text(encoding="utf-8").replace(
        "__DATA_JSON__", json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(description="Export 7x7 matrix CSV data to interactive HTML.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help="CSV file to export. Defaults to newest recordings/matrix_7x7_*.csv",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("recordings"),
        help="Directory used when csv_path is omitted.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML path. Defaults to CSV path with .html suffix.",
    )
    parser.add_argument(
        "--t-start", type=float, default=None, help="Keep frames with elapsed_sec >= this value."
    )
    parser.add_argument(
        "--t-end", type=float, default=None, help="Keep frames with elapsed_sec <= this value."
    )
    parser.add_argument(
        "--subsample-fps",
        type=float,
        default=None,
        help="Downsample to this many frames per recorded second.",
    )
    parser.add_argument(
        "--play-interval-ms",
        type=float,
        default=None,
        help="HTML playback interval between displayed frames.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    csv_path = args.csv_path or latest_csv(args.data_dir)
    output_path = export_csv_to_html(
        csv_path,
        args.output,
        t_start=args.t_start,
        t_end=args.t_end,
        subsample_fps=args.subsample_fps,
        play_interval_ms=args.play_interval_ms,
    )
    print(f"Exported interactive replay to {output_path}")


if __name__ == "__main__":
    main()
