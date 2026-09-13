#pragma once

#include <Arduino_RouterBridge.h>

#include "BrailleReceiver.h"

#include <utility>

namespace BrailleQ::bridge {

BrailleReceiver displayText;

bool blurryPicture = false;

void initialize() {
  Bridge.begin();
  
  Bridge.provide_safe(
    "braille_begin",
    [](uint32_t id, uint32_t size) {
      return displayText.begin(id, size);
    }
  );

  Bridge.provide_safe(
    "braille_chunk",
    [](uint32_t id, uint32_t offset, MsgPack::bin_t<uint8_t> chunk) {
      return displayText.chunk(id, offset, chunk);
    }
  );

  Bridge.provide_safe(
    "braille_end",
    [](uint32_t id) {
      return displayText.end(id);
    }
  );

  Bridge.provide_safe(
    "blurry_picture",
    []() { blurryPicture = true; }
  );
}

} // namespace BrailleQ::bridge
