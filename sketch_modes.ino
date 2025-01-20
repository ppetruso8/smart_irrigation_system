#include <DHT.h>

// Pin assignments for relays and sensors
const int relay = 2;
const int soilMoisture = A0;
const int moistureThreshold = 500;  // Calibrate!

// DHT Temperature and Humidity Sensor
#define DHTPIN 6
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

enum Mode : byte {IDLE, READ, WATER};
Mode currentMode = IDLE;

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(9600);
  
  // Relay pin as output
  pinMode(relay, OUTPUT);

  // Initialize relay to be OFF (pumps off)
  digitalWrite(relay, HIGH);

  // Initialize temperature and humidity sensor
  dht.begin();
}

void loop() {  
  // Read from serial port
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    // Select mode based on read command
    if (command == "READ") {
      currentMode = READ;
    } else if (command = "WATER") {
      currentMode = WATER;
    } else if (command = "IDLE") {
      currentMode = IDLE;
    }
  }

  // Handle modes
  switch (currentMode) {
    case READ:
      takeReading();
      currentMode = IDLE;
      break;

    case WATER:
      water();
      // add code to check in ime x to see if moisture level improved
      currentMode = IDLE;
      break;

    case IDLE:
    default:
      // wait for commands - how?
      delay(100);
      break;
  }
  
}

// Read sensors
void takeReading() {
  // Read soil moisture level
  int moistureValue = analogRead(soilMoisture);
  // Read temperature and humidity
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();

  // Print readings for Raspberry Pi
  Serial.print("SOIL: ");
  Serial.println(moistureValue);
  Serial.print("TEMP: ");
  Serial.println(temperature);
  Serial.print("HUM: ");
  Serial.println(humidity);
}

// Watering
void water() {
  // ADD DIFFERENT VOLUMES OF WATER
  
  // Watering in pulses (5)
  for (int i = 0; i < 5; i++) {
    digitalWrite(relay, LOW);   // Turn ON pump
    delay(200);                 // Wait for ON duration
    digitalWrite(relay, HIGH);  // Turn OFF pump
    delay(200);                 // Wait for OFF duration
  }

  Serial.println("WATER_FINISH");
}
