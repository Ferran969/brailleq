#pragma once

#include <string>
#include <utility>

namespace BrailleQ::bridge {

class ProvisionedText {
public:
  void provide(std::string text) {
    m_text = std::move(text);
    m_update = true;
  }
  bool update() {
    bool value = m_update;
    m_update = false;
    return value;
  }
  const std::string& text() const { return m_text; }
private:
  std::string m_text{};
  bool m_update{false};
};

} // namespace BrailleQ::bridge