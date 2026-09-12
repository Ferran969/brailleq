#pragma once

#include <Arduino_RouterBridge.h>

#include "TextReceiver.h"

#include <utility>

namespace BrailleQ::bridge {

TextReceiver displayText;
  
void initialize() {
  Bridge.begin();
  
  Bridge.provide_safe(
    "text_begin",
    [](uint32_t id, uint32_t size) {
      return displayText.begin(id, size);
    }
  );

  Bridge.provide_safe(
    "text_chunk",
    [](uint32_t id, uint32_t offset, String chunk) {
      return displayText.chunk(id, offset, chunk);
    }
  );

  Bridge.provide_safe(
    "text_end",
    [](uint32_t id) {
      return displayText.end(id);
    }
  );
}

} // namespace BrailleQ::bridge