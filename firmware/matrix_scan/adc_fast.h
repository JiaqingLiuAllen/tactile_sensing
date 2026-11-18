#pragma once

#include "soc/gpio_struct.h"

constexpr uint32_t BAUD_RATE = 1500000;
constexpr uint16_t SETTLE_DELAY_US = 1;

const uint32_t AD7276_SCLK_MASK = 1UL << AD7276_SCLK;
const uint32_t AD7276_MISO_MASK = 1UL << AD7276_MISO;
const uint32_t AD7276_CS_MASK = 1UL << AD7276_CS;

inline void shortAdcDelay() {
  asm volatile(
    "nop\n nop\n nop\n nop\n"
    "nop\n nop\n nop\n nop\n"
    "nop\n nop\n nop\n nop\n"
    "nop\n nop\n nop\n nop\n"
  );
}

uint16_t readAD7276() {
  uint16_t rawWord = 0;

  GPIO.out_w1tc = AD7276_CS_MASK;
  shortAdcDelay();

  for (int bit = 0; bit < 16; bit++) {
    GPIO.out_w1ts = AD7276_SCLK_MASK;
    shortAdcDelay();
    rawWord = (rawWord << 1) | ((GPIO.in & AD7276_MISO_MASK) ? 1 : 0);
    GPIO.out_w1tc = AD7276_SCLK_MASK;
    shortAdcDelay();
  }

  GPIO.out_w1ts = AD7276_CS_MASK;

  return (rawWord >> 2) & 0x0FFF;
}

inline uint16_t sampleCell() {
  return readAD7276();
}
