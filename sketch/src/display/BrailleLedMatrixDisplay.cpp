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
    {1, 9},
    {3, 9},
    {5, 9},
    {1, 11},
    {3, 11},
    {5, 11},
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

void BrailleLedMatrixDisplay::drawPhotoIndicator(bool enabled) {
  constexpr std::uint8_t on = 7;
  constexpr std::uint8_t off = 0;

  // Same three positions used by drawLoading().
  constexpr std::pair<std::size_t, std::size_t> positions[3] = {
      {3, 1},
      {3, 3},
      {3, 5},
  };

  // Clear all three, then optionally light only the middle one.
  for (const auto& [row, column] : positions) {
    m_frame[row][column] = off;
  }

  if (enabled) {
    const auto [row, column] = positions[1];
    m_frame[row][column] = on;
  }

  m_matrix.draw(&m_frame[0][0]);
}

void BrailleLedMatrixDisplay::drawLoading(int phase) {
  constexpr std::uint8_t on = 7;
  constexpr std::uint8_t off = 0;

  constexpr std::pair<std::size_t, std::size_t> positions[3] = {
      {3, 1},
      {3, 3},
      {3, 5},
  };

  for (std::size_t i = 0; i < 3; ++i) {
    const auto [row, column] = positions[i];
    m_frame[row][column] = (i < phase) ? on : off;
  }

  m_matrix.draw(&m_frame[0][0]);
}

void BrailleLedMatrixDisplay::drawBlurryCross(bool enabled) {
  constexpr std::uint8_t on = 7;
  constexpr std::uint8_t off = 0;

  constexpr std::pair<std::size_t, std::size_t> positions[] = {
      {1, 1},
      {1, 5},
      {2, 2},
      {2, 4},
      {3, 3},
      {4, 2},
      {4, 4},
      {5, 1},
      {5, 5},
  };

  for (const auto& [row, column] : positions) {
    m_frame[row][column] = enabled ? on : off;
  }

  m_matrix.draw(&m_frame[0][0]);
}

} // namespace BrailleQ
