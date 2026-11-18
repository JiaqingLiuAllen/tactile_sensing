"""Exercise the scanner-to-replay path using generated protocol frames."""

import csv
import io
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from threading import Event
import unittest

from tactile.capture import record
from tactile.export import export_csv_to_html, load_csv_data
from tactile.protocol import FrameDecoder


def packet(sequence, kind=1):
    # Construct the byte sequence independently of the host decoder.
    header = bytes((1, 7, 7, kind)) + struct.pack("<II", sequence, 1234)
    readings = struct.pack("<49H", *([0, 4095] + [2048] * 47))
    checksum = (sum(header) + sum(readings)) % 65536
    return b"M7XB" + header + readings + struct.pack("<H", checksum)


class StreamTests(unittest.TestCase):
    def test_split_at_every_byte(self):
        data = packet(37)
        self.assertEqual(len(data), 116)
        for split in range(len(data) + 1):
            decoder = FrameDecoder()
            result = list(decoder.feed(data[:split])) + list(decoder.feed(data[split:]))
            self.assertEqual(len(result), 1)
            self.assertEqual((result[0].sequence, result[0].millis), (37, 1234))
            self.assertEqual(result[0].samples[:2], (0, 4095))

    def test_recover_after_corruption_and_unsupported_type(self):
        damaged = bytearray(packet(0))
        damaged[-1] ^= 0xFF
        decoder = FrameDecoder()
        frames = list(decoder.feed(b"noise" + damaged + packet(1, kind=2) + packet(2)))
        self.assertEqual([f.sequence for f in frames], [2])
        self.assertEqual(decoder.invalid_frames, 2)

    def test_capture_and_export(self):
        stop = Event()
        wire = io.BytesIO(packet(0xFFFFFFFF) + packet(0) + packet(2))

        class TestPort:
            in_waiting = 23

            def read(self, size):
                chunk = wire.read(size)
                if not chunk:
                    stop.set()
                return chunk

        with TemporaryDirectory() as folder:
            path = Path(folder) / "matrix_7x7_sample.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                self.assertEqual(record(TestPort(), stream, stop, None), (3, 1, 0))
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 3)
            self.assertEqual([rows[0]["R1C1"], rows[0]["R1C2"]], ["0.000000", "3.300000"])
            data = load_csv_data(path)
            self.assertEqual(len(data["frames"]), 3)
            self.assertEqual(data["frames"][-1]["device_frame"], 2)
            html = export_csv_to_html(path).read_text(encoding="utf-8")
            self.assertIn('"source_name":"matrix_7x7_sample.csv"', html)
            self.assertNotIn("__DATA_JSON__", html)


if __name__ == "__main__":
    unittest.main()
