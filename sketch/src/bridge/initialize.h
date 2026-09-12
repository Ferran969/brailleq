#pragma once

#include <Arduino_RouterBridge.h>

#include "ProvisionedText.h"

#include <utility>

namespace BrailleQ::bridge {

ProvisionedText displayText;
  
void initialize() {
  Bridge.begin();
  // Display text handler.
  Bridge.provide_safe("display_text", [](String text) {
    displayText.provide(text.c_str());
  });
}

} // namespace BrailleQ::bridge