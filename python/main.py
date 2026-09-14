"""Coordinate capture, OCR, quality validation, Braille, and display output.

The Arduino sketch notifies ``take_picture`` through the Router Bridge. The App
loop then performs one synchronous processing cycle and sends either a retry
notification or a validated sequence of six-dot Braille cells back to the
sketch.
"""

import string
import unicodedata

from arduino.app_utils import App, Bridge

from braille import BrailleClient
from paddle_ocr import recognize
from v4l2_capture import capture_image

braille_translator = BrailleClient()

picture_requested = False

# Application-level acceptance threshold. This must be recalibrated when the
# camera, capture resolution, lighting, or document presentation changes.
MIN_TEXT_SHARPNESS = 500.0


def loop():
    """This function is called repeatedly by the App framework."""
    global picture_requested
    if picture_requested:
        picture_requested = False

        image = capture_image(5)
        text, text_sharpness = recognize(image)

        if (
            text_sharpness is None
            or text_sharpness < MIN_TEXT_SHARPNESS
        ):
            measured_value = (
                "no disponible"
                if text_sharpness is None
                else f"{text_sharpness:.3f}"
            )
            print(
                "[PHOTO QUALITY] La fotografía ha salido mal "
                f"(nitidez del texto: {measured_value}; "
                f"mínimo: {MIN_TEXT_SHARPNESS:.0f}). "
                "Realice una nueva fotografía.",
                flush=True,
            )

            Bridge.notify("blurry_picture")
            return

        print(
            "[PHOTO QUALITY] La fotografía ha salido bien "
            f"(nitidez del texto: {text_sharpness:.3f}; "
            f"mínimo: {MIN_TEXT_SHARPNESS:.0f}). "
            "No es necesario repetirla.",
            flush=True,
        )

        sanitized = sanitize_english_ocr(text)
        translation = braille_translator.translate(sanitized)
        braille_cells = bytes(translation.cells)

        display_braille(braille_cells)


def take_picture() -> None:
    """Mark one sketch-originated photograph request for the App loop."""
    global picture_requested
    picture_requested = True


ALLOWED_CHARS = set(
    string.ascii_letters +
    string.digits +
    string.punctuation +
    " \n\t"
)


def sanitize_english_ocr(text: str) -> str:
    """Normalize OCR text and retain only the supported English character set."""
    # Normalize things such as full-width ASCII characters.
    text = unicodedata.normalize("NFKC", text)

    cleaned = []

    for char in text:
        if char in ALLOWED_CHARS:
            cleaned.append(char)
        else:
            # Don't accidentally join words together.
            cleaned.append(" ")

    # Clean up excessive spaces while preserving lines.
    lines = [
        " ".join(line.split())
        for line in "".join(cleaned).splitlines()
    ]

    return "\n".join(line for line in lines if line)


MAX_CHUNK_BYTES = 180


def byte_chunks(data: bytes, max_bytes: int):
    """Yield ordered slices no larger than the Router Bridge payload limit."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    for start in range(0, len(data), max_bytes):
        yield data[start:start + max_bytes]


transfer_id = 1


def display_braille(cells: bytes) -> None:
    """Transfer one complete six-dot translation atomically to the sketch."""
    global transfer_id

    current_id = transfer_id
    transfer_id += 1

    Bridge.call("braille_begin", current_id, len(cells))

    offset = 0

    for chunk in byte_chunks(cells, MAX_CHUNK_BYTES):
        Bridge.call(
            "braille_chunk",
            current_id,
            offset,
            chunk,
        )
        offset += len(chunk)

    Bridge.call("braille_end", current_id)


Bridge.provide("take_picture", take_picture)

# Run and let the sketch work.
App.run(user_loop=loop)
