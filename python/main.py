import time

from arduino.app_utils import App, Bridge

print("Hello world!")


def loop():
    """This function is called repeatedly by the App framework."""
    # You can replace this with any code you want your App to run repeatedly.
    time.sleep(10)


# See: https://docs.arduino.cc/software/app-lab/tutorials/getting-started/#app-run
# App.run(user_loop=loop)

# Provision always before running.
def take_picture() -> None:
    print("Take picture")
    display_text("hello");

def display_text(text: str) -> None:
    Bridge.call("display_text", text);

Bridge.provide("take_picture", take_picture)

# Run and let the sketch work.
App.run()