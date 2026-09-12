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

def display_text(text: str) -> None:
    Bridge.notify("display_text", text)

Bridge.provide("take_picture", take_picture)

# Run and let the sketch work.
App.run(user_loop=loop)