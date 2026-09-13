import time

from arduino.app_utils import App, Bridge

from paddle_ocr import recognize
from v4l2_capture import capture_image
from braille import BrailleClient

print("Hello world!")

braille_translator = BrailleClient()

picture_requested = False
MIN_TEXT_SHARPNESS = 500.0

def loop():
    global picture_requested
    """This function is called repeatedly by the App framework."""
    # You can replace this with any code you want your App to run repeatedly.
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
        translation = braille_translator.translate(text)
        braille_cells = bytes(translation.cells)
        
        display_braille(braille_cells)


# See: https://docs.arduino.cc/software/app-lab/tutorials/getting-started/#app-run
# App.run(user_loop=loop)

# Provision always before running.
def take_picture() -> None:
    global picture_requested
    print("Take picture")
    picture_requested = True

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
