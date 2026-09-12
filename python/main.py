import time

from arduino.app_utils import App, Bridge

from paddle_ocr import recognize
from v4l2_capture import capture_image

print("Hello world!")

picture_requested = False

def loop():
    global picture_requested
    """This function is called repeatedly by the App framework."""
    # You can replace this with any code you want your App to run repeatedly.
    if picture_requested:
        picture_requested = False
        image = capture_image(5)
        text = recognize(image)
        print("Recognized text:")
        print(text)
        display_text(text)


# See: https://docs.arduino.cc/software/app-lab/tutorials/getting-started/#app-run
# App.run(user_loop=loop)

# Provision always before running.
def take_picture() -> None:
    global picture_requested
    print("Take picture")
    picture_requested = True

MAX_CHUNK_BYTES = 180


def utf8_chunks(text: str, max_bytes: int):
    chunk = []
    chunk_bytes = 0

    for char in text:
        encoded_size = len(char.encode("utf-8"))

        if chunk and chunk_bytes + encoded_size > max_bytes:
            yield "".join(chunk)
            chunk = []
            chunk_bytes = 0

        chunk.append(char)
        chunk_bytes += encoded_size

    if chunk:
        yield "".join(chunk)

transfer_id = 1


def display_text(text: str) -> None:
    global transfer_id

    current_id = transfer_id
    transfer_id += 1

    total_bytes = len(text.encode("utf-8"))

    Bridge.call(
        "text_begin",
        current_id,
        total_bytes,
    )

    offset = 0

    for chunk in utf8_chunks(text, MAX_CHUNK_BYTES):
        Bridge.call(
            "text_chunk",
            current_id,
            offset,
            chunk,
        )

        offset += len(chunk.encode("utf-8"))

    Bridge.call(
        "text_end",
        current_id,
    )

Bridge.provide("take_picture", take_picture)

# Run and let the sketch work.
App.run(user_loop=loop)