# BrailleQ Arduino sketch

The sketch runs on the microcontroller side of the Arduino UNO Q. It reads the
Modulino Buttons module, exchanges events and Braille data with the Linux
application through the Arduino Router Bridge, and draws status information or
one six-dot Braille cell on the LED matrix.

## Hardware

- Arduino UNO Q with its LED matrix.
- Modulino Buttons module at I²C address `0x3E`.
- The Linux-side BrailleQ application running and connected through the Router
  Bridge.

The camera is controlled by the Linux application, not directly by the sketch.

## Controls

| Button | Behaviour |
| --- | --- |
| A | Move one cell backward when a translation is available. |
| B | Clear the current cell, start the photograph indicator and notify Linux to capture an image. |
| C | Move one cell forward when a translation is available. |

Navigation stops at the first and last cell; it does not wrap around. Button
edges are tracked so holding a button does not repeatedly advance the index.

## User-interface states

The sketch maintains four visible states:

1. **Braille:** displays the currently selected cell.
2. **Photograph countdown:** keeps the centre status dot illuminated for five
   seconds after B is pressed.
3. **Loading:** cycles through zero, one, two and three status dots once per
   second while the Linux application works.
4. **Blurry photograph:** displays a cross until the user starts another
   photograph or an accepted translation arrives.

Pressing B sends `take_picture` immediately. The five-second sketch countdown
runs while the Linux-side camera service discards frames to let autofocus
settle. After the countdown, the sketch switches to the loading animation if a
result has not arrived yet.

An accepted Braille transfer cancels countdown, loading and blur indication,
then resets navigation to the first cell.

## LED matrix layout

`BrailleLedMatrixDisplay` uses an 8-row by 13-column grayscale frame. Brightness
value `7` means on and `0` means off.

The Braille cell occupies rows 1, 3 and 5 and columns 9 and 11:

```text
dot 1 (bit 0)      dot 4 (bit 3)
dot 2 (bit 1)      dot 5 (bit 4)
dot 3 (bit 2)      dot 6 (bit 5)
```

Conceptually:

```text
●  ●
●  ●
●  ●
```

The left side of the matrix is reserved for application status:

- Row 3, columns 1, 3 and 5 form the loading indicator.
- The centre of those three positions is the photograph indicator.
- A 5×5 cross in rows 1–5 and columns 1–5 indicates a rejected photograph.

Status drawing and Braille drawing share one internal frame so one area can be
updated without clearing the other unintentionally.

## Braille representation

`BrailleCharacter` stores exactly six Boolean dots in standard Braille order.
Linux sends each cell as a byte, but only the lower six bits are valid:

| Byte bit | Braille dot |
| --- | --- |
| 0 | 1 |
| 1 | 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 6 |

Values are therefore limited to `0..63`. Dots 7 and 8 are not represented by
the current class or display layout.

## Router Bridge protocol

### Sketch to Linux

```text
take_picture()
```

Button B sends this notification. `python/main.py` provides the corresponding
handler and marks a photograph as pending.

### Linux to sketch

```text
blurry_picture()
```

Sets the retry state when the OCR text-region sharpness is unavailable or below
the application threshold.

Braille translations use a three-step transfer:

```text
braille_begin(transfer_id, total_size)
braille_chunk(transfer_id, offset, binary_data)  # repeated as necessary
braille_end(transfer_id)
```

`BrailleReceiver` validates the sequence:

- A transfer must have started before chunks are accepted.
- Every chunk must carry the active transfer ID.
- Every offset must equal the number of bytes already received.
- The final byte count must equal the size declared by `braille_begin`.

Only a complete, valid transfer replaces the translation visible to the user.
The Linux application currently sends chunks containing at most 180 cells.

## Source layout

```text
sketch.ino                              Main setup, button handling and UI state
src/braille/BrailleCharacter.h          Six-dot cell representation
src/bridge/BrailleReceiver.h            Validated chunk receiver
src/bridge/initialize.h                 Linux-to-sketch Bridge registration
src/bridge/take_picture.h               Sketch-to-Linux notification
src/display/BrailleDisplay.h            Display interface
src/display/BrailleLedMatrixDisplay.*   LED matrix implementation
sketch.yaml                             Board platform and library dependencies
```

## Build configuration

`sketch.yaml` selects the `arduino:zephyr` platform and declares the libraries
available to the sketch. The firmware directly includes:

- `Arduino_Modulino`
- `Arduino_LED_Matrix`
- `Arduino_RouterBridge`

The current profile leaves `fqbn` empty because board selection is supplied by
the App Lab environment. If compiling outside App Lab, provide the correct UNO
Q board configuration and the same library versions.

Several sensor libraries are also listed in `sketch.yaml` but are not currently
used by the BrailleQ source. Confirm that App Lab does not require them before
removing them.

## Extending the interface

When adding a display state:

1. Add the operation to `BrailleDisplay`.
2. Implement it in `BrailleLedMatrixDisplay`.
3. Reserve matrix coordinates that do not overwrite the Braille cell unless
   that is intentional.
4. Define precisely which existing states it cancels.
5. Test rapid transitions, including pressing B while another result is
   displayed.

When changing the Bridge protocol, update both `python/main.py` and the
handlers registered in `src/bridge/initialize.h`. Keep the transfer ID and
offset validation so incomplete messages cannot be displayed as a successful
translation.

## Manual validation checklist

Automated firmware tests are not currently present. On hardware, verify:

1. A and C stop correctly at the translation boundaries.
2. B sends exactly one request per press.
3. Countdown changes to loading after five seconds.
4. A rejected photograph shows the cross and a new B press clears it.
5. A successful result starts at its first cell.
6. Every one of the six bits lights the expected physical dot.
7. A translation longer than 180 cells is reconstructed correctly.
8. A second translation completely replaces the first.
