#include <LiquidCrystal.h>

// ── Pins ─────────────────────────────────────────────────────────────────────
LiquidCrystal lcd(7, 8, 9, 10, 11, 12);  // RS, EN, D4, D5, D6, D7

#define LCD_CONTRAST  6   // PWM contrast on V0 — wire LCD pin 3 to Arduino D6
#define LED_RED       2
#define LED_YELLOW    3
#define LED_GREEN     4
#define LED_BLUE      5

// Tune 0-255: lower = darker text. 80 is a good starting point.
#define CONTRAST_VAL  80

void setup() {
  Serial.begin(9600);

  // Contrast via PWM — no pot needed
  pinMode(LCD_CONTRAST, OUTPUT);
  analogWrite(LCD_CONTRAST, CONTRAST_VAL);

  // LCD init
  lcd.begin(16, 2);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Chess Ready!");
  lcd.setCursor(0, 1);
  lcd.print("Waiting...");

  // LED pins
  pinMode(LED_RED,    OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN,  OUTPUT);
  pinMode(LED_BLUE,   OUTPUT);

  // All LEDs off at start
  digitalWrite(LED_RED,    LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_GREEN,  LOW);
  digitalWrite(LED_BLUE,   LOW);
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.length() == 0) return;

    // ── LCD command ───────────────────────────────────────────────────────
    // Format from Python: LCD:line1|line2
    if (cmd.startsWith("LCD:")) {
      String content = cmd.substring(4);
      int sep = content.indexOf('|');
      String line1 = (sep >= 0) ? content.substring(0, sep) : content;
      String line2 = (sep >= 0) ? content.substring(sep + 1) : "";

      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print(line1.substring(0, 16));
      lcd.setCursor(0, 1);
      lcd.print(line2.substring(0, 16));

    // ── LED on ────────────────────────────────────────────────────────────
    // Format: LED_ON:2  (pin number)
    } else if (cmd.startsWith("LED_ON:")) {
      int pin = cmd.substring(7).toInt();
      if (pin >= 2 && pin <= 5) digitalWrite(pin, HIGH);

    // ── LED off ───────────────────────────────────────────────────────────
    // Format: LED_OFF:2  (pin number)
    } else if (cmd.startsWith("LED_OFF:")) {
      int pin = cmd.substring(8).toInt();
      if (pin >= 2 && pin <= 5) digitalWrite(pin, LOW);

    // ── Contrast adjust ───────────────────────────────────────────────────
    // Format: CONTRAST:80  (0-255, optional runtime tuning)
    } else if (cmd.startsWith("CONTRAST:")) {
      int val = cmd.substring(9).toInt();
      analogWrite(LCD_CONTRAST, constrain(val, 0, 255));
    }
  }
}
