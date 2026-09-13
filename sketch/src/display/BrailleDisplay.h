#pragma once

#include "../braille/BrailleCharacter.h"

namespace BrailleQ {

class BrailleDisplay {
public:
  virtual ~BrailleDisplay() = default;
  virtual void begin() = 0;
  virtual void end() = 0;
  virtual void clear() = 0;
  virtual void draw(const BrailleCharacter&) = 0;
  virtual void drawPhotoIndicator(bool) = 0;
  virtual void drawLoading(int) = 0;
  virtual void drawBlurryCross(bool) = 0;
};

} // namespace BrailleQ