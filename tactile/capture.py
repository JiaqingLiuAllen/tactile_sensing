"""Record the scanner's serial stream and display the most recent frame."""

import argparse
import csv
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event
from time import monotonic

import numpy as np
import serial

from .display import (
    BASELINE_SEC,
    MATRIX_COLS,
    MATRIX_ROWS,
    delta_scale,
    deformation_from_baseline,
    orient_matrix,
)
from .export import export_csv_to_html
from .protocol import FrameDecoder

BAUD = {"stable": 921600, "fast": 1500000}
VOLTS_PER_COUNT = 3.3 / 4095
CSV_HEADER = [
    "timestamp_iso",
    "elapsed_sec",
    "host_frame_index",
    "device_frame_index",
    "device_millis",
    "value_unit",
] + [f"R{r+1}C{c+1}" for r in range(MATRIX_ROWS) for c in range(MATRIX_COLS)]


def record(port, stream, stop, latest):
    decoder = FrameDecoder()
    writer = csv.writer(stream)
    writer.writerow(CSV_HEADER)
    start = None
    baseline = np.zeros((MATRIX_ROWS, MATRIX_COLS))
    baseline_count = 0
    received = gaps = 0
    previous = None
    while not stop.is_set():
        chunk = port.read(min(8192, port.in_waiting or 1))
        for frame in decoder.feed(chunk):
            now = monotonic()
            if start is None:
                start = now
            elapsed = now - start
            received += 1
            if previous is not None:
                advance = (frame.sequence - previous) % (2**32)
                if 1 < advance < 2**31:
                    gaps += advance - 1
            previous = frame.sequence
            volts = np.asarray(frame.samples) * VOLTS_PER_COUNT
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="milliseconds"),
                    f"{elapsed:.6f}",
                    received,
                    frame.sequence,
                    frame.millis,
                    "V",
                    *(f"{v:.6f}" for v in volts),
                ]
            )
            if received % 50 == 0:
                stream.flush()

            if latest is not None:
                matrix = volts.reshape(MATRIX_ROWS, MATRIX_COLS)
                if elapsed <= BASELINE_SEC:
                    baseline_count += 1
                    baseline += (matrix - baseline) / baseline_count
                latest.append(
                    (orient_matrix(deformation_from_baseline(matrix, baseline)), elapsed, gaps)
                )
    return received, gaps, decoder.invalid_frames


def show_live(latest, recorder, interval):
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    from .plots import create_view

    fig, draw = create_view(np.zeros((MATRIX_ROWS, MATRIX_COLS)), -0.25, 0.25)

    def update(_):
        if recorder.done():
            plt.close(fig)
        elif latest:
            matrix, elapsed, gaps = latest.pop()
            draw(
                matrix,
                f"Tactile matrix  |  {elapsed:.2f} s  |  {gaps} missing frames",
                delta_scale(matrix, min_span=0.5),
            )

    # The figure owns the animation until its window closes.
    fig.tactile_animation = FuncAnimation(fig, update, interval=interval, cache_frame_data=False)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Serial port, e.g. /dev/ttyUSB0 or COM3.")
    parser.add_argument(
        "--mode", choices=BAUD, default="stable", help="Match the firmware profile."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("recordings"))
    parser.add_argument(
        "--no-view", action="store_true", help="Record until interrupted without a plot window."
    )
    args = parser.parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = args.output_dir / f"matrix_7x7_{args.mode}_{timestamp}.csv"
    stop = Event()
    latest = None if args.no_view else deque(maxlen=1)
    try:
        with serial.Serial(args.port, BAUD[args.mode], timeout=0.2) as port:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            with path.open("x", newline="", encoding="utf-8") as stream, ThreadPoolExecutor(
                max_workers=1
            ) as pool:
                print(
                    f"Recording to {path}. Keep the array unloaded for the first second.",
                    flush=True,
                )
                recorder = pool.submit(record, port, stream, stop, latest)
                try:
                    if args.no_view:
                        while not recorder.done():
                            stop.wait(0.2)
                    else:
                        show_live(latest, recorder, 16 if args.mode == "fast" else 33)
                except KeyboardInterrupt:
                    pass
                finally:
                    stop.set()
                count, gaps, invalid = recorder.result()
    except (OSError, serial.SerialException) as exc:
        parser.exit(1, f"Capture stopped: {exc}\n")
    print(f"Received {count} frames, {gaps} missing sequence numbers, {invalid} invalid packets.")
    if count:
        print(f"Replay saved to {export_csv_to_html(path)}")


if __name__ == "__main__":
    main()
