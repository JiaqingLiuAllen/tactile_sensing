"""Decode the ESP32 scanner's little-endian M7XB serial frames."""

import struct
from typing import NamedTuple

from .display import MATRIX_COLS, MATRIX_ROWS

MAGIC = b"M7XB"
HEADER = struct.Struct("<BBBBII")  # Version, dimensions, payload type, sequence, millis
SAMPLES = struct.Struct(f"<{MATRIX_ROWS * MATRIX_COLS}H")
CHECKSUM = struct.Struct("<H")
FRAME_BYTES = len(MAGIC) + HEADER.size + SAMPLES.size + CHECKSUM.size


class Frame(NamedTuple):
    sequence: int
    millis: int
    samples: tuple


class FrameDecoder:
    """Keep incomplete frames across reads and resynchronize after damaged bytes."""

    def __init__(self):
        self.pending = bytearray()
        self.invalid_frames = 0

    def feed(self, chunk):
        self.pending.extend(chunk)
        while True:
            start = self.pending.find(MAGIC)
            if start < 0:
                # A read can end partway through the four-byte synchronization word.
                del self.pending[: max(0, len(self.pending) - len(MAGIC) + 1)]
                return
            del self.pending[:start]
            if len(self.pending) < FRAME_BYTES:
                return

            body = self.pending[len(MAGIC) : FRAME_BYTES - CHECKSUM.size]
            (checksum,) = CHECKSUM.unpack_from(self.pending, FRAME_BYTES - CHECKSUM.size)
            version, rows, cols, kind, sequence, millis = HEADER.unpack_from(body)
            if (version, rows, cols, kind) != (1, MATRIX_ROWS, MATRIX_COLS, 1) or sum(
                body
            ) & 0xFFFF != checksum:
                self.invalid_frames += 1
                del self.pending[0]
                continue

            samples = SAMPLES.unpack_from(body, HEADER.size)
            del self.pending[:FRAME_BYTES]
            yield Frame(sequence, millis, samples)
