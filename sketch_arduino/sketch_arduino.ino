
#include <DHT.h>

// Pin assignments for relays and sensors
const int relay = 2;
const int soilMoisture = A0;
const int moistureThreshold = 500;  // Calibrate!

// DHT Temperature and Humidity Sensor
#define DHTPIN 6
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// Action modes
enum Mode : byte {IDLE, READ, WATER};
Mode currentMode = IDLE;

// Watering modes
enum WaterMode : byte {LIGHT, MEDIUM, HEAVY, CUSTOM};
WaterMode currentWaterMode = MEDIUM;
// Setting up variables for watering
int amount = 0;
int pulses = 0;

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

    // Change mode or execute command
    if (command == "READ") {
      currentMode = READ;
    } else if (command == "WATER") {
      currentMode = WATER;
    } else if (command == "IDLE") {
      currentMode = IDLE;
    } else if (command.startsWith("CHMOD")) {
      String wateringMode = command.substring(6);
      setWaterMode(wateringMode);
    }
  }

  // Handle Action Modes
  switch (currentMode) {
    case READ:
      takeReading();
      currentMode = IDLE;
      break;

    case WATER:  
      switch (currentWaterMode) {
        case LIGHT:
          pulses = 2; // approx. 20ml of water - smaller indoor plants
          break;

        case MEDIUM:
          pulses = 5; // approx. 50ml of water - bigger plants (average setting)
          break;

        case HEAVY:
          pulses = 10; // approx. 100ml of water - deep watering
          break;

        case CUSTOM:
          pulses = amount/10; // 1 pulse = approx. 10ml
          break; 
      }

      water(pulses);
           
      // add code to check in time x to see if moisture level improved
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
  
  // Print soil moisture reading
  Serial.print("{\"soil\":");
  Serial.print(moistureValue);

  // Read temperature and humidity
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();

  if (isnan(humidity) || isnan(temperature)) {
    Serial.print("{\"\error\":\"error_reading_dht_sensor\"}");
    Serial.println();
    return;
  }

  // Print readings for Raspberry Pi
  Serial.print(",\"temp\":");
  Serial.print(temperature);
  Serial.print(",\"hum\":");
  Serial.print(humidity);
  Serial.print("}");
  Serial.println();
}


// Watering
void water(int pulses) {
  if (pulses <= 0) {
    Serial.print("{\"error\":\"invalid_watering_amount\"}");
    Serial.println();
    return;
  }

  
  Serial.print("{\"notice\":\"watering_started(");
  Serial.print(pulses*10); // 1 pulse = approx. 10ml
  Serial.print(")\"}");
  Serial.println();
  
  
  
  // Watering in pulses
  for (int i = 0; i < pulses; i++) {
    digitalWrite(relay, LOW);   // Turn ON pump
    delay(250);                 // Wait for ON duration (approx. 10ml per pulse)
    digitalWrite(relay, HIGH);  // Turn OFF pump
    delay(250);                 // Wait for OFF duration
  }

  delay(200);
  
  Serial.print("{\"notice\":\"watering_finished\"}");
  Serial.println();
}

void setWaterMode(String mode) {
  if (mode == "LIGHT") {
    currentWaterMode = LIGHT;
  } else if (mode == "MEDIUM") {
    currentWaterMode = MEDIUM;
  } else if (mode == "HEAVY") {
    currentWaterMode = HEAVY;
  } else if (mode.startsWith("CUSTOM")) {
    currentWaterMode = CUSTOM;
    String wateringAmount = mode.substring(7);  //extract the amount of ml for watering
    amount = wateringAmount.toInt();
  }
}
