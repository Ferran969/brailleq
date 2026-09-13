#pragma once

#include "../braille/BrailleCharacter.h"
#include "BrailleDisplay.h"

#include <Arduino_LED_Matrix.h>

namespace BrailleQ {

class BrailleLedMatrixDisplay : public BrailleDisplay {
public:
  BrailleLedMatrixDisplay(Arduino_LED_Matrix&);
  ~BrailleLedMatrixDisplay() override = default;
  void begin() override;
  void end() override;
  void clear() override;
  void draw(const BrailleCharacter&) override;
  void drawPhotoIndicator(bool) override;
  void drawLoading(int) override;
  void drawBlurryCross(bool) override;
  static constexpr std::size_t rows = 8;
  static constexpr std::size_t columns = 13;
private:
  void clearInternalFrame();
  Arduino_LED_Matrix& m_matrix;
  uint8_t m_frame[rows][columns]{};
};

} // namespace BrailleQ