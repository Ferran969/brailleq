#include "../braille/BrailleCharacter.h"
#include "BrailleDisplay.h"
#include "BrailleLedMatrixDisplay.h"

#include <utility>

namespace BrailleQ {

BrailleLedMatrixDisplay::BrailleLedMatrixDisplay(Arduino_LED_Matrix& matrix) : m_matrix(matrix) {}

void BrailleLedMatrixDisplay::begin() {
  m_matrix.begin();
  clearInternalFrame();
}

void BrailleLedMatrixDisplay::end() {
  m_matrix.end();
  clearInternalFrame();
}

void BrailleLedMatrixDisplay::clear() {
  m_matrix.clear();
  clearInternalFrame();
}

void BrailleLedMatrixDisplay::draw(const BrailleCharacter& character) {
  constexpr std::uint8_t on = 7;
  constexpr std::uint8_t off = 0;

  constexpr std::pair<std::size_t, std::size_t> dotPositions[6] = {
      {1, 5},
      {3, 5},
      {5, 5},
      {1, 7},
      {3, 7},
      {5, 7},
  };

  for (std::size_t dot = 0; dot < 6; ++dot) {
    const auto [row, column] = dotPositions[dot];
    m_frame[row][column] = character[dot] ? on : off;
  }

  m_matrix.draw(&m_frame[0][0]);
}

void BrailleLedMatrixDisplay::clearInternalFrame() {
  for (std::size_t i = 0; i < rows; ++i) {
    for (std::size_t j = 0; j < columns; ++j) {
      m_frame[i][j] = 0;
    }
  }
}

} // namespace BrailleQ