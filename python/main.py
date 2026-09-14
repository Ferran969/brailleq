import time
from datetime import datetime
from pathlib import Path

from arduino.app_utils import App, Bridge

from paddle_ocr import recognize
from v4l2_capture import capture_image
from braille import BrailleClient

print("Hello world!")

braille_translator = BrailleClient()

picture_requested = False
MIN_TEXT_SHARPNESS = 500.0

# TEMPORARY DEBUG CODE: remove this capture archive after camera diagnostics.
DEBUG_CAPTURE_DIR = Path("debug_captures")


def save_debug_capture(image: bytes) -> None:
    try:
        DEBUG_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        capture_path = DEBUG_CAPTURE_DIR / f"capture_{timestamp}.jpg"
        capture_path.write_bytes(image)
        print(
            f"[DEBUG CAPTURE] Fotografía guardada en {capture_path.resolve()}",
            flush=True,
        )
    except OSError as error:
        # Saving a debug copy must not prevent OCR from processing the image.
        print(
            f"[DEBUG CAPTURE] No se pudo guardar la fotografía: {error}",
            flush=True,
        )


def loop():
    global picture_requested
    """This function is called repeatedly by the App framework."""
    # You can replace this with any code you want your App to run repeatedly.
    if picture_requested:
        picture_requested = False

        # TEMPORARY PERFORMANCE DIAGNOSTICS: remove after OCR profiling.
        phase_started = time.perf_counter()
        image = capture_image(5)
        print(
            "[PERF] Application - camera capture: "
            f"{time.perf_counter() - phase_started:.3f} s",
            flush=True,
        )

        phase_started = time.perf_counter()
        save_debug_capture(image)
        print(
            "[PERF] Application - raw debug capture save: "
            f"{time.perf_counter() - phase_started:.3f} s",
            flush=True,
        )

        phase_started = time.perf_counter()
        text, text_sharpness = recognize(image)
        print(
            "[PERF] Application - complete OCR call: "
            f"{time.perf_counter() - phase_started:.3f} s",
            flush=True,
        )

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

            Bridge.notify("blurry_picture");

            # TODO(LED): sustituir el print por una notificación al sketch
            # para indicar mediante los LEDs que debe repetirse la fotografía.
            # Bridge.call("photo_quality", False)
            return

        print(
            "[PHOTO QUALITY] La fotografía ha salido bien "
            f"(nitidez del texto: {text_sharpness:.3f}; "
            f"mínimo: {MIN_TEXT_SHARPNESS:.0f}). "
            "No es necesario repetirla.",
            flush=True,
        )

        # TODO(LED): sustituir el print por una notificación al sketch para
        # indicar mediante los LEDs que la fotografía ha sido aceptada.
        # Bridge.call("photo_quality", True)

        print("Recognized text:")
        print(text)
        sanitized = sanitize_english_ocr(text)
        print("Sanitized text:")
        print(sanitized)
        translation = braille_translator.translate(sanitized)
        braille_cells = bytes(translation.cells)
        
        display_braille(braille_cells)


# See: https://docs.arduino.cc/software/app-lab/tutorials/getting-started/#app-run
# App.run(user_loop=loop)

# Provision always before running.
def take_picture() -> None:
    global picture_requested
    print("Take picture")
    picture_requested = True


import string
import unicodedata


ALLOWED_CHARS = set(
    string.ascii_letters +
    string.digits +
    string.punctuation +
    " \n\t"
)


def sanitize_english_ocr(text: str) -> str:
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
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    for start in range(0, len(data), max_bytes):
        yield data[start:start + max_bytes]

transfer_id = 1


def display_braille(cells: bytes) -> None:
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
