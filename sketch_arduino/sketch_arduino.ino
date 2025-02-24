
#include <DHT.h>

// Pin assignments for relays and sensors
const int relay = 2;
const int soilMoisture = A0;
const int moistureThreshold = 500;  // Calibrate!

// DHT Temperature and Humidity Sensor
#define DHTPIN 6
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// Irrigation modes (based on environment)
enum EnvMode : byte {INDOOR, OUTDOOR};
EnvMode currentEnv = INDOOR;

// Status modes
enum StatusMode : byte {IDLE, READ, WATER};
StatusMode currentStatus = IDLE;

// Watering modes
enum WaterMode : byte {LIGHT, MEDIUM, HEAVY, CUSTOM};
WaterMode currentWaterMode = MEDIUM;
WaterMode tempWaterMode = MEDIUM; // automatic watering mode select
bool isTempWater = false;
// Setting up variables for watering
int amount = 1;
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
      currentStatus = READ;
      
    } else if (command.startsWith("WATER")) {
      if (command.length() > 6) {
        // automatic watering
        isTempWater = true;
        String tempWatering = command.substring(6);
        setWaterMode(tempWatering, true);
      }
      
      currentStatus = WATER;
      
    } else if (command == "IDLE") {
      currentStatus = IDLE;
      
    } else if (command.startsWith("CHMOD")) {
      String wateringMode = command.substring(6);
      setWaterMode(wateringMode, false);
      
    } else if (command.startsWith("SET_ENV")) {
      String envMode = command.substring(8);
      setEnvMode(envMode);
      
    } else {
      Serial.println("{\"error\":\"invalid_command\"}");
    }
  }

  // Handle status actions
  switch (currentStatus) {
    case READ:
      takeReading();
      currentStatus = IDLE;
      break;

    case WATER:
      WaterMode modeToUse;
      
      if (isTempWater) {
        modeToUse = tempWaterMode;
        isTempWater = false;
        
      } else {
        modeToUse = currentWaterMode;
        
      }
      
      switch (modeToUse) {
        case LIGHT:
          pulses = (currentEnv == INDOOR) ? 2 : 10;
          break;

        case MEDIUM:
          pulses = (currentEnv == INDOOR) ? 5 : 35;
          break;

        case HEAVY:
          pulses = (currentEnv == INDOOR) ? 10 : 70;
          break;

        case CUSTOM:
          pulses = amount/10; // 1 pulse = approx. 10ml
          break; 
      }

      water(pulses);
      currentStatus = IDLE;
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
    Serial.print("}");
    Serial.println("{\"\error\":\"error_reading_dht_sensor\"}");
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
    Serial.println("{\"error\":\"invalid_watering_amount\"}");
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
  Serial.println("{\"notice\":\"watering_finished\"}");
}

void setWaterMode(String mode, bool temp) {
  if (mode == "LIGHT") {
    if (!temp) {
      currentWaterMode = LIGHT;  
    } else {
      tempWaterMode = LIGHT;
    }
    
  } else if (mode == "MEDIUM") {
    if (!temp) {
      currentWaterMode = MEDIUM;  
    } else {
      tempWaterMode = MEDIUM;
    }
    
  } else if (mode == "HEAVY") {
    if (!temp) {
      currentWaterMode = HEAVY;  
    } else {
      tempWaterMode = HEAVY;
    }
    
  } else if (mode.startsWith("CUSTOM")) {
    // if custom amount is provided
    if (mode.length() > 6) {
      String wateringAmount = mode.substring(7);  //extract the amount of ml for watering
      amount = wateringAmount.toInt();
  
      if (amount <= 0) {
        Serial.println("{\"error\":\"invalid_watering_amount\"}");
        return;
        
      } else if (amount > 1000) {
        // limit max amount to 1l
        amount = 1000;
        mode = "CUSTOM 1000";
      }
    }
    
    if (!temp) {
      currentWaterMode = CUSTOM;  
    } else {
      tempWaterMode = CUSTOM;
    }
    
  } else {
    Serial.println("{\"error\":\"invalid_watering_mode\"}");
    return;
  }

  if (!temp) {
    Serial.print("{\"notice\":\"watering_mode_set(");
  } else {
    Serial.print("{\"notice\":\"temp_watering_mode_set(");
  }
  Serial.print(mode);
  Serial.print(")\"}");
  Serial.println();
}

void setEnvMode(String mode) {
  if (mode == "INDOOR") {
    currentEnv = INDOOR;
    Serial.println("{\"notice\":\"env_set_indoor\"}");
    
  } else if (mode == "OUTDOOR") {
    currentEnv = OUTDOOR;
    Serial.println("{\"notice\":\"env_set_outdoor\"}");
    
  } else {
    Serial.println("{\"error\":\"invalid_env\"}");
  }
}
