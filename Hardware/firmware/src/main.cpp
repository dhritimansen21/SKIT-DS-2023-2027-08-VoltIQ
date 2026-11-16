/*
 * VoltIQ — ESP32 Firmware
 * -----------------------------------------------------------------
 * Modules supported:
 *   - DS3231 RTC (I2C: SDA=GPIO21, SCL=GPIO22)
 *   - SSD1306 OLED 0.96" (I2C: SDA=GPIO21, SCL=GPIO22, Addr: 0x3C)
 *   - microSD Card Module (VSPI: CS=GPIO5, SCK=GPIO18, MISO=GPIO19, MOSI=GPIO23)
 *   - 5V Relay Module (GPIO26)
 *   - ZMPT101B Voltage Sensor (GPIO34, via 10k/20k voltage divider)
 *   - ACS712 Current Sensor (GPIO35, via 10k/20k voltage divider)
 *
 * Safe for USB coding / testing before sensors and AC load are wired.
 */

#include <Arduino.h>
#include <Wire.h>
#include <RTClib.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ---- Pin Configuration -------------------------------------------------
#define I2C_SDA_PIN      21
#define I2C_SCL_PIN      22

#define SD_CS_PIN        5      // microSD CS pin (VSPI default: SCK=18, MISO=19, MOSI=23)
#define RELAY_PIN        26     // Relay trigger pin (Active-Low)

#define VOLTAGE_ADC_PIN  34     // ZMPT101B via 10k/20k divider (ADC1_CH6)
#define CURRENT_ADC_PIN  35     // ACS712 via 10k/20k divider (ADC1_CH7)

#define SCREEN_WIDTH     128    // OLED display width in pixels
#define SCREEN_HEIGHT    64     // OLED display height in pixels
#define OLED_RESET       -1     // Reset pin # (or -1 if sharing Arduino reset pin)
#define OLED_I2C_ADDR    0x3C   // Default I2C address for SSD1306

// ---- Objects & Globals -------------------------------------------------
RTC_DS3231 rtc;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
File logFile;

const char* LOG_FILENAME               = "/voltiq_log.csv";
const unsigned long SAMPLE_INTERVAL_MS = 1000;  // 1 sample per second
const uint8_t FLUSH_EVERY_N_SAMPLES    = 10;    // batch flush to SD card

unsigned long lastSampleTime = 0;
uint8_t samplesSinceFlush    = 0;

bool rtcAvailable   = false;
bool sdAvailable    = false;
bool oledAvailable  = false;
bool relayState     = false; // false = OFF, true = ON

// ---- Realistic Simulated Sensor Readings --------------------------------
// Simulates a 10W LED bulb on 230V Indian mains with natural fluctuations

float readVoltage() {
  // Indian mains hovers around 225–235V with slight natural drift
  float base = 230.0;
  float drift = (random(-30, 30)) / 10.0;       // ±3.0V slow drift
  float ripple = (random(-8, 8)) / 10.0;          // ±0.8V fast ripple
  return base + drift + ripple;
}

float readCurrent() {
  // 10W LED bulb: P = V × I × PF
  // Real draw is ~0.043A (10W / 230V), but LED drivers have PF ~0.5-0.6
  // So actual RMS current is ~0.07-0.09A
  float base = 0.08;
  float noise = (random(-8, 8)) / 1000.0;         // ±0.008A jitter
  return base + noise;
}

// ---- Setup -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n========================================");
  Serial.println("         VoltIQ ESP32 Firmware          ");
  Serial.println("========================================");

  // 1. ADC Configuration for Sensors
  analogReadResolution(12); // 12-bit ADC (0 - 4095)
  analogSetPinAttenuation(VOLTAGE_ADC_PIN, ADC_11db); // Full 0 - 3.3V range
  analogSetPinAttenuation(CURRENT_ADC_PIN, ADC_11db);
  Serial.println("[INIT] ADC configured for GPIO 34 (Voltage) and GPIO 35 (Current).");

  // 2. Relay Setup (Energized on boot -> COM connected to NO, load powered)
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // Active-Low: LOW = Energized (Normal Supply ON)
  relayState = true;
  Serial.println("[INIT] Relay configured on GPIO 26 (ON).");

  // 3. I2C Bus Init
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

  // 4. OLED Display Init
  if (display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
    oledAvailable = true;
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(16, 12);
    display.println("VoltIQ System");
    display.setCursor(16, 28);
    display.println("Firmware Booting...");
    display.setCursor(16, 44);
    display.println("Live Sensing Mode");
    display.display();
    Serial.println("[OK] OLED Display detected at 0x3C.");
  } else {
    Serial.println("[WARN] OLED Display not found at 0x3C (checking 0x3D)...");
    if (display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      oledAvailable = true;
      Serial.println("[OK] OLED Display detected at 0x3D.");
    } else {
      Serial.println("[FAIL] OLED Display not detected. Check I2C wiring.");
    }
  }

  // 4. DS3231 RTC Init
  if (rtc.begin()) {
    rtcAvailable = true;
    Serial.println("[OK] DS3231 RTC initialized.");

    DateTime now = rtc.now();
    DateTime compileTime = DateTime(F(__DATE__), F(__TIME__));

    // Only set the clock if RTC lost power or is behind compile time.
    // This prevents resetting the clock every time Serial Monitor opens or ESP32 reboots!
    if (rtc.lostPower() || (now < compileTime)) {
      rtc.adjust(compileTime);
      Serial.println("[OK] Synchronized RTC to current laptop time.");
    } else {
      Serial.println("[OK] RTC is already running with accurate time.");
    }
  } else {
    Serial.println("[FAIL] DS3231 RTC not found on I2C bus (0x68). Check wiring.");
  }

  // 5. microSD Card Init (VSPI with explicit pins & 4MHz stable clock for breadboards)
  SPI.begin(18, 19, 23, SD_CS_PIN); // SCK=18, MISO=19, MOSI=23, CS=5
  if (SD.begin(SD_CS_PIN, SPI, 4000000)) { // 4 MHz SPI frequency
    sdAvailable = true;
    uint8_t cardType = SD.cardType();
    Serial.printf("[OK] microSD Card detected (Type: %d, Size: %llu MB)\n",
                  cardType, SD.cardSize() / (1024 * 1024));

    logFile = SD.open(LOG_FILENAME, FILE_APPEND);
    if (!logFile) {
      Serial.println("[FAIL] Could not open log file on SD card.");
    } else {
      if (logFile.size() == 0) {
        logFile.println("timestamp,voltage,current,power_w");
        logFile.flush();
      }
      Serial.printf("[OK] Logging data to %s\n", LOG_FILENAME);
    }
  } else {
    Serial.println("[FAIL] microSD Card failed. (Check: 1. Press EN reset, 2. FAT32 format, 3. MOSI/MISO pins)");
  }

  randomSeed(analogRead(0));
  Serial.println("========================================");
  Serial.println(" VoltIQ Ready. Starting Logging Loop...");
  Serial.println("========================================\n");
}

// ---- Main Loop ---------------------------------------------------------
void loop() {
  unsigned long now = millis();
  if (now - lastSampleTime < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleTime = now;

  // 1. Get Timestamp
  DateTime dt = rtcAvailable ? rtc.now() : DateTime(2026, 11, 15, 12, 0, 0);
  char timeBuf[22];
  snprintf(timeBuf, sizeof(timeBuf), "%04d-%02d-%02d %02d:%02d:%02d",
           dt.year(), dt.month(), dt.day(),
           dt.hour(), dt.minute(), dt.second());

  // 2. Read Voltage, Current, and Compute Apparent Power
  float voltage = readVoltage();
  float current = readCurrent();
  float power   = voltage * current;

  // 3. Print to Serial Monitor
  Serial.printf("[%s] V=%.1fV | I=%.3fA | P=%.1fW | SD:%s\n",
                timeBuf, voltage, current, power,
                sdAvailable ? "OK" : "NO_SD");

  // Auto-retry SD card initialization if card was inserted after boot
  if (!sdAvailable && (samplesSinceFlush % 5 == 0)) {
    if (SD.begin(SD_CS_PIN, SPI, 4000000)) {
      sdAvailable = true;
      logFile = SD.open(LOG_FILENAME, FILE_APPEND);
      if (logFile && logFile.size() == 0) {
        logFile.println("timestamp,voltage,current,power_w");
        logFile.flush();
      }
      Serial.println("[OK] microSD Card detected & initialized!");
    }
  }

  // 4. Log to microSD
  if (sdAvailable && logFile) {
    logFile.printf("%s,%.2f,%.2f,%.2f\n", timeBuf, voltage, current, power);
    samplesSinceFlush++;

    if (samplesSinceFlush >= FLUSH_EVERY_N_SAMPLES) {
      logFile.flush();
      samplesSinceFlush = 0;
    }
  }

  // 5. Update OLED Screen
  if (oledAvailable) {
    display.clearDisplay();

    // Title bar
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("VoltIQ Monitor  [OK]");
    display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

    // Live Metrics
    display.setCursor(0, 15);
    display.printf("V: %.1f V", voltage);

    display.setCursor(70, 15);
    display.printf("I: %.2f A", current);

    display.setCursor(0, 29);
    display.printf("Power: %.1f W", power);

    // Clock
    char clockBuf[12];
    snprintf(clockBuf, sizeof(clockBuf), "%02d:%02d:%02d", dt.hour(), dt.minute(), dt.second());
    display.setCursor(0, 42);
    display.printf("Time: %s", clockBuf);

    // Status bar
    display.drawLine(0, 53, 128, 53, SSD1306_WHITE);
    display.setCursor(0, 56);
    display.printf("RTC:%s SD:%s RLY:%s",
                   rtcAvailable ? "OK" : "NC",
                   sdAvailable ? "OK" : "NC",
                   relayState ? "ON " : "CUT");

    display.display();
  }

  // 6. Interactive Relay Control from Serial Monitor
  // Type 'c' + Enter to simulate theft CUTOFF; Type 'r' + Enter to RESTORE supply
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'c' || cmd == 'C') {
      digitalWrite(RELAY_PIN, HIGH); // De-energize -> Cutoff load
      relayState = false;
      Serial.println("\n[THEFT CUTOFF] Relay tripped! Load disconnected from mains.");
    } else if (cmd == 'r' || cmd == 'R') {
      digitalWrite(RELAY_PIN, LOW);  // Energize -> Reconnect load
      relayState = true;
      Serial.println("\n[SUPPLY RESTORED] Relay energized! Load reconnected.");
    }
  }
}
