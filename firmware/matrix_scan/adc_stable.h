#pragma once

constexpr uint32_t BAUD_RATE = 921600;
constexpr uint16_t SETTLE_DELAY_US = 50;
constexpr uint8_t SAMPLES_PER_CHANNEL = 3;

uint16_t readAD7276() {
  uint16_t rawWord = 0;

  digitalWrite(AD7276_CS, LOW);
  delayMicroseconds(1);

  for (int bit = 0; bit < 16; bit++) {
    digitalWrite(AD7276_SCLK, HIGH);
    delayMicroseconds(1);
    rawWord = (rawWord << 1) | (digitalRead(AD7276_MISO) ? 1 : 0);
    digitalWrite(AD7276_SCLK, LOW);
    delayMicroseconds(1);
  }

  digitalWrite(AD7276_CS, HIGH);
  return (rawWord >> 2) & 0x0FFF;
}

uint16_t sampleCell() {
  uint32_t sum = 0;
  for (int i = 0; i < SAMPLES_PER_CHANNEL; i++) {
    sum += readAD7276();
    delayMicroseconds(2);
  }
  return (sum + (SAMPLES_PER_CHANNEL / 2)) / SAMPLES_PER_CHANNEL;
}
