#pragma once

#include <cstdint>
#include <vector>
#include <utility>

namespace BrailleQ::bridge {

/// Assemble one validated, ordered Braille transfer from the Linux App.
///
/// A completed translation is published only after the transfer ID, offsets,
/// and final size have all been verified.
class BrailleReceiver {
public:
  /// Start a transfer and reserve space for its declared number of cells.
  bool begin(uint32_t id, size_t size) {
    m_id = id;
    m_expectedSize = size;

    m_buffer.clear();
    m_buffer.reserve(size);

    m_receiving = true;
    return true;
  }

  /// Append the next chunk when its transfer ID and offset are exact.
  bool chunk(uint32_t id, size_t offset, const MsgPack::bin_t<uint8_t>& chunk) {
    if (!m_receiving)
      return false;

    if (id != m_id)
      return false;

    if (offset != m_buffer.size())
      return false;

    const auto bufferOffset = m_buffer.size();
    m_buffer.resize(bufferOffset + chunk.size());
    std::copy(
      chunk.begin(),
      chunk.end(),
      m_buffer.begin() + bufferOffset
    );

    return true;
  }

  /// Commit the transfer only when all declared cells have arrived.
  bool end(uint32_t id) {
    if (!m_receiving)
      return false;

    if (id != m_id)
      return false;

    if (m_buffer.size() != m_expectedSize)
      return false;

    m_receiving = false;

    m_completedText = std::move(m_buffer);
    m_updated = true;

    return true;
  }

  /// Consume the one-shot flag indicating that a new translation is ready.
  bool takeUpdate() {
    bool updated = m_updated;
    m_updated = false;
    return updated;
  }

  /// Return the last complete translation; partial input is never exposed.
  const std::vector<uint8_t>& braille() const & {
    return m_completedText;
  }

private:
  uint32_t m_id{0};
  size_t m_expectedSize{0};

  bool m_receiving{false};
  bool m_updated{false};

  std::vector<uint8_t> m_buffer;
  std::vector<uint8_t> m_completedText;
};

} // namespace BrailleQ::bridge
