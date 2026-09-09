#pragma once

#include <Arduino_RouterBridge.h>

namespace BrailleQ::bridge {

void take_picture() {
  Bridge.notify("take_picture");
}

} // namespace BrailleQ::bridge