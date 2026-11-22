#include <Wire.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <math.h>

// =====================================================
// WIFI SETTINGS
// =====================================================
const char* ssid = "Purvansh’s iPhone";
const char* password = "12345678";

ESP8266WebServer server(80);
Adafruit_MPU6050 mpu;

// =====================================================
// MPU6050 DATA
// =====================================================
volatile float roll = 0.0;
volatile float pitch = 0.0;

float ax = 0.0;
float ay = 0.0;
float az = 0.0;

// =====================================================
// TIMING
// =====================================================
unsigned long lastMPURead = 0;
unsigned long lastWiFiCheck = 0;
unsigned long lastReconnectAttempt = 0;
unsigned long wifiLostTime = 0;
unsigned long lastSerialPrint = 0;

// MPU update interval
const unsigned long MPU_INTERVAL = 5;       // 5 ms = 200 Hz

// WiFi checking interval
const unsigned long WIFI_CHECK_INTERVAL = 1000;

// Try reconnect every 3 seconds
const unsigned long RECONNECT_INTERVAL = 3000;

// Restart if WiFi remains disconnected too long
const unsigned long WIFI_RESTART_TIME = 60000;

// =====================================================
// WIFI STATE
// =====================================================
bool wifiWasConnected = false;

// =====================================================
// SETUP
// =====================================================
void setup() {

  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("======================================");
  Serial.println(" ESP8266 MPU6050 AIRPLANE CONTROLLER");
  Serial.println("======================================");

  // ===================================================
  // I2C
  // ===================================================

  Wire.begin(D2, D1);     // SDA = D2, SCL = D1

  // Increase I2C speed
  Wire.setClock(400000);

  Serial.println();
  Serial.println("Initializing MPU6050...");

  if (!mpu.begin()) {

    Serial.println("ERROR: MPU6050 NOT FOUND!");

    while (true) {
      delay(1000);
    }
  }

  Serial.println("MPU6050 detected!");

  // ===================================================
  // MPU CONFIGURATION
  // ===================================================

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);

  // Lower filtering = faster response
  mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);

  Serial.println("MPU6050 configured.");

  // ===================================================
  // WIFI CONFIGURATION
  // ===================================================

  Serial.println();
  Serial.println("Configuring WiFi...");

  // Station mode
  WiFi.mode(WIFI_STA);

  // Disable WiFi sleep
  // This can improve responsiveness and stability
  WiFi.setSleepMode(WIFI_NONE_SLEEP);

  // Automatically reconnect
  WiFi.setAutoReconnect(true);

  // Do not store WiFi configuration in flash
  WiFi.persistent(false);

  // Start WiFi
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");

  unsigned long wifiStart = millis();

  while (WiFi.status() != WL_CONNECTED &&
         millis() - wifiStart < 20000) {

    delay(250);
    Serial.print(".");
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {

    wifiWasConnected = true;

    Serial.println("WiFi CONNECTED!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

    Serial.print("Signal strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  }

  else {

    Serial.println("WiFi connection failed.");
    Serial.println("Will continue trying in background.");
  }

  // ===================================================
  // HTTP SERVER
  // ===================================================

  server.on("/", handleRoot);
  server.on("/data", handleData);

  server.begin();

  Serial.println();
  Serial.println("HTTP server started.");
  Serial.println("======================================");
}

// =====================================================
// LOOP
// =====================================================
void loop() {

  unsigned long currentMillis = millis();

  // ===================================================
  // HANDLE WEB REQUESTS
  // ===================================================

  server.handleClient();


  // ===================================================
  // WIFI MANAGEMENT
  // ===================================================

  if (currentMillis - lastWiFiCheck >= WIFI_CHECK_INTERVAL) {

    lastWiFiCheck = currentMillis;

    manageWiFi();
  }


  // ===================================================
  // READ MPU6050
  // ===================================================

  if (currentMillis - lastMPURead >= MPU_INTERVAL) {

    lastMPURead = currentMillis;

    readMPU();
  }


  // ===================================================
  // SERIAL DEBUG
  // ===================================================

  // Do NOT print every MPU reading.
  // Printing too frequently can slow the ESP8266.

  if (currentMillis - lastSerialPrint >= 250) {

    lastSerialPrint = currentMillis;

    Serial.print("Roll: ");
    Serial.print(roll, 2);

    Serial.print(" | Pitch: ");
    Serial.print(pitch, 2);

    Serial.print(" | AX: ");
    Serial.print(ax, 2);

    Serial.print(" | AY: ");
    Serial.print(ay, 2);

    Serial.print(" | AZ: ");
    Serial.print(az, 2);

    Serial.print(" | WiFi: ");

    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("CONNECTED");
    }
    else {
      Serial.print("DISCONNECTED");
    }

    Serial.println();
  }

  // No delay here.
  // This keeps the controller responsive.
}


// =====================================================
// WIFI MANAGEMENT
// =====================================================

void manageWiFi() {

  wl_status_t status = WiFi.status();


  // ===================================================
  // CONNECTED
  // ===================================================

  if (status == WL_CONNECTED) {

    if (!wifiWasConnected) {

      Serial.println();
      Serial.println("********************************");
      Serial.println("WiFi RECONNECTED!");
      Serial.print("IP Address: ");
      Serial.println(WiFi.localIP());
      Serial.print("RSSI: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
      Serial.println("********************************");

      wifiWasConnected = true;
    }

    // Reset lost timer
    wifiLostTime = 0;

    return;
  }


  // ===================================================
  // DISCONNECTED
  // ===================================================

  if (wifiWasConnected) {

    Serial.println();
    Serial.println("!!! WiFi DISCONNECTED !!!");

    wifiWasConnected = false;

    wifiLostTime = millis();
  }


  // ===================================================
  // TRY RECONNECTING
  // ===================================================

  if (millis() - lastReconnectAttempt >= RECONNECT_INTERVAL) {

    lastReconnectAttempt = millis();

    Serial.println("Trying WiFi reconnect...");

    // Do not use disconnect() here.
    // It can make reconnection slower with some hotspots.

    WiFi.begin(ssid, password);
  }


  // ===================================================
  // ESP8266 RESTART
  // ===================================================

  if (wifiLostTime > 0 &&
      millis() - wifiLostTime >= WIFI_RESTART_TIME) {

    Serial.println();
    Serial.println("WiFi unavailable for 60 seconds.");
    Serial.println("Restarting ESP8266...");

    delay(1000);

    ESP.restart();
  }
}


// =====================================================
// READ MPU6050
// =====================================================

void readMPU() {

  sensors_event_t accel;
  sensors_event_t gyro;
  sensors_event_t temp;

  mpu.getEvent(&accel, &gyro, &temp);


  // ===================================================
  // STORE ACCELERATION
  // ===================================================

  ax = accel.acceleration.x;
  ay = accel.acceleration.y;
  az = accel.acceleration.z;


  // ===================================================
  // CALCULATE ROLL
  // ===================================================

  roll = atan2(
    ay,
    az
  ) * 180.0 / PI;


  // ===================================================
  // CALCULATE PITCH
  // ===================================================

  pitch = atan2(
    -ax,
    sqrt(
      ay * ay +
      az * az
    )
  ) * 180.0 / PI;
}


// =====================================================
// ROOT PAGE
// =====================================================

void handleRoot() {

  String html;

  html.reserve(1500);

  html += "<!DOCTYPE html>";
  html += "<html>";
  html += "<head>";

  html += "<meta name='viewport' ";
  html += "content='width=device-width,initial-scale=1'>";

  html += "<title>ESP8266 MPU6050 Controller</title>";

  html += "</head>";

  html += "<body>";

  html += "<h1>MPU6050 Airplane Controller</h1>";

  html += "<h2>Orientation</h2>";

  html += "<p>Roll: ";
  html += String(roll, 2);
  html += " degrees</p>";

  html += "<p>Pitch: ";
  html += String(pitch, 2);
  html += " degrees</p>";

  html += "<h2>WiFi</h2>";

  html += "<p>Status: ";

  if (WiFi.status() == WL_CONNECTED) {
    html += "CONNECTED";
  }
  else {
    html += "DISCONNECTED";
  }

  html += "</p>";

  if (WiFi.status() == WL_CONNECTED) {

    html += "<p>IP: ";
    html += WiFi.localIP().toString();
    html += "</p>";

    html += "<p>RSSI: ";
    html += String(WiFi.RSSI());
    html += " dBm</p>";
  }

  html += "<p><a href='/data'>JSON Data</a></p>";

  html += "</body>";
  html += "</html>";

  server.send(200, "text/html", html);
}


// =====================================================
// JSON DATA
// =====================================================

void handleData() {

  // Compact JSON for faster transmission

  String json;

  json.reserve(100);

  json += "{\"roll\":";
  json += String(roll, 2);

  json += ",\"pitch\":";
  json += String(pitch, 2);

  json += "}";

  // Tell browser/client not to keep old data
  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");

  server.sendHeader("Pragma", "no-cache");

  server.sendHeader("Expires", "0");

  server.send(200, "application/json", json);
}