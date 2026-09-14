#pragma once

#include <Arduino_RouterBridge.h>

namespace BrailleQ::bridge {

void take_picture() {
  // The Linux App owns capture and OCR; the sketch only sends the request.
  Bridge.notify("take_picture");
}

} // namespace BrailleQ::bridge
