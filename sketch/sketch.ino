#include "src/braille/BrailleCharacter.h"
#include "src/display/BrailleLedMatrixDisplay.h"
#include "src/bridge/initialize.h"
#include "src/bridge/take_picture.h"

#include <Arduino_Modulino.h>

ModulinoButtons buttons{0x3E};

Arduino_LED_Matrix matrix;

void setup() {
  BrailleQ::bridge::initialize();
  
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();

  Serial.begin(115200);

  Modulino.begin();

  buttons.begin();
}

void testLedMatrixBraille() {
  BrailleQ::BrailleCharacter up{
    true, false, false,
    true, false, false
  };
  BrailleQ::BrailleCharacter middle{
    false, true, false,
    false, true, false
  };
  BrailleQ::BrailleCharacter down{
    false, false, true,
    false, false, true
  };
  BrailleQ::BrailleCharacter left{
    true, true, true,
    false, false, false
  };
  BrailleQ::BrailleCharacter right{
    false, false, false,
    true, true, true
  };
  BrailleQ::BrailleCharacter all{
    true, true, true,
    true, true, true
  };
  BrailleQ::BrailleLedMatrixDisplay display{matrix};
  delay(1000);
  display.draw(up);
  delay(1000);
  display.draw(middle);
  delay(1000);
  display.draw(down);
  delay(1000);
  display.draw(left);
  delay(1000);
  display.draw(right);
  delay(1000);
  display.draw(all);
}

constexpr BrailleQ::BrailleCharacter alphabet[] = {
    {1, 0, 0, 0, 0, 0}, // a  1
    {1, 1, 0, 0, 0, 0}, // b  12
    {1, 0, 0, 1, 0, 0}, // c  14
    {1, 0, 0, 1, 1, 0}, // d  145
    {1, 0, 0, 0, 1, 0}, // e  15
    {1, 1, 0, 1, 0, 0}, // f  124
    {1, 1, 0, 1, 1, 0}, // g  1245
    {1, 1, 0, 0, 1, 0}, // h  125
    {0, 1, 0, 1, 0, 0}, // i  24
    {0, 1, 0, 1, 1, 0}, // j  245

    {1, 0, 1, 0, 0, 0}, // k  13
    {1, 1, 1, 0, 0, 0}, // l  123
    {1, 0, 1, 1, 0, 0}, // m  134
    {1, 0, 1, 1, 1, 0}, // n  1345
    {1, 0, 1, 0, 1, 0}, // o  135
    {1, 1, 1, 1, 0, 0}, // p  1234
    {1, 1, 1, 1, 1, 0}, // q  12345
    {1, 1, 1, 0, 1, 0}, // r  1235
    {0, 1, 1, 1, 0, 0}, // s  234
    {0, 1, 1, 1, 1, 0}, // t  2345

    {1, 0, 1, 0, 0, 1}, // u  136
    {1, 1, 1, 0, 0, 1}, // v  1236
    {0, 1, 0, 1, 1, 1}, // w  2456
    {1, 0, 1, 1, 0, 1}, // x  1346
    {1, 0, 1, 1, 1, 1}, // y  13456
    {1, 0, 1, 0, 1, 1}, // z  1356
};

int textIndex = 0;

bool pressedA = false;
bool pressedB = false;
bool pressedC = false;

void loop() {
  BrailleQ::BrailleLedMatrixDisplay display{matrix};
  // for (char c = 'a'; c <= 'z'; ++c) {
  //   display.draw(alphabet[c - 'a']);
  //   delay(1000);
  // }
  BrailleQ::BrailleCharacter up{
    true, false, false,
    true, false, false
  };
  BrailleQ::BrailleCharacter middle{
    false, true, false,
    false, true, false
  };
  BrailleQ::BrailleCharacter down{
    false, false, true,
    false, false, true
  };
  BrailleQ::BrailleCharacter none{
    false, false, false,
    false, false, false
  };
  buttons.update();

  if (BrailleQ::bridge::displayText.update()) {
    textIndex = 0;
  }

  const auto& text = BrailleQ::bridge::displayText.text();
  
  if (!pressedA && buttons.isPressed('A')) {
    if (textIndex > 0) --textIndex;
  }

  if (!pressedC && buttons.isPressed('C')) {
    if (textIndex + 1 < text.size()) ++textIndex;
  }
  
  if (!pressedB && buttons.isPressed('B')) {
    BrailleQ::bridge::take_picture();
  }

  pressedA = buttons.isPressed('A');
  pressedB = buttons.isPressed('B');
  pressedC = buttons.isPressed('C');

  if (text.empty() || text[textIndex] == ' ') display.draw(none); 
  else display.draw(alphabet[text[textIndex] - 'a']);
  
  delay(20);
}