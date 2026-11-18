# Scanner hardware

The firmware targets the original ESP32 Dev Module. Both profiles select a row and a column, let the analog input settle, and read the AD7276 at the voltage-divider node.

| Connection | ESP32 GPIO |
| --- | --- |
| Column CD74HC4067, S0 → S3 | 33, 25, 26, 27 |
| Row CD74HC4067, S0 → S3 | 21, 22, 23, 14 |
| AD7276 SCLK / SDATA / CS | 18 / 19 / 4 |

Connect the ADC VIN to the matrix divider output and use a common ground. The host converts the 12-bit counts to volts assuming a 3.3 V full scale.

## Flash

Use Arduino CLI with the Espressif ESP32 board package (built with 3.3.10). Set the port to your board.

```sh
PORT=/dev/ttyUSB0
arduino-cli compile --upload --port "$PORT" --fqbn esp32:esp32:esp32 firmware/matrix_scan
```

| Profile | Reads per cell | MUX settling delay per selection | Serial baud |
| --- | ---: | ---: | ---: |
| Stable (default) | 3, averaged | 50 µs | 921,600 |
| Fast | 1 | 1 µs | 1,500,000 |

Fast mode clocks the ADC through the ESP32 GPIO registers. Use matching settings on the host.

```sh
arduino-cli compile --upload --port "$PORT" --fqbn esp32:esp32:esp32 \
  --build-property compiler.cpp.extra_flags=-DTACTILE_FAST=1 firmware/matrix_scan
python -m tactile.capture --port "$PORT" --mode fast
```

## Serial frame

The firmware sends a 116-byte little-endian frame after each sweep. ADC values are stored in row-major order, from R1C1 through R7C7.

| Byte offset | Size | Contents |
| ---: | ---: | --- |
| 0 | 4 | ASCII sync word `M7XB` |
| 4 | 4 | Protocol version = 1, rows = 7, columns = 7, payload type = 1 |
| 8 | 4 | Unsigned frame sequence |
| 12 | 4 | Device uptime in milliseconds |
| 16 | 98 | 49 unsigned 16-bit words, each carrying a 12-bit ADC count |
| 114 | 2 | Sum of bytes 4–113 modulo 65,536 |

The display follows the physical panel labels, with row numbers increasing left to right and column numbers increasing from top to bottom.
