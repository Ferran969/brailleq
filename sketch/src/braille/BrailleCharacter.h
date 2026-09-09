#pragma once

#include <cstddef>

namespace BrailleQ {

/// For now this is standard literary braille.
class BrailleCharacter {
public:
  static constexpr std::size_t rows = 3;
  static constexpr std::size_t columns = 2;
  static constexpr std::size_t dotCount = rows * columns;

  constexpr BrailleCharacter(bool d0, bool d1, bool d2, bool d3, bool d4, bool d5) {
    m_dots[0] = d0;
    m_dots[1] = d1;
    m_dots[2] = d2;
    m_dots[3] = d3;
    m_dots[4] = d4;
    m_dots[5] = d5;
  }

  bool& operator[](std::size_t dot) {
    return m_dots[dot];
  }

  const bool& operator[](std::size_t dot) const {
    return m_dots[dot];
  }

private:
  bool m_dots[dotCount]{};
};

} // namespace BrailleQ