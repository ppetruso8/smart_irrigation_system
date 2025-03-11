#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

// Pin assignments 
const int relay = 26;

// sensors
enum SensorType : byte {SOIL, DHT_SENSOR};
struct Sensor {
  int id;
  int pin;
  SensorType type;
  bool active;
  DHT* dht;   // DHT instance pointer 
};

// array of created sensors
const int max_num_sensors = 6;
Sensor sensors[max_num_sensors] = {
  {1, 34, SOIL, true, nullptr},
  {2, 35, SOIL, true, nullptr},
  {3, 32, SOIL, false, nullptr},
  {4, 33, SOIL, false, nullptr},
  {1, 4, DHT_SENSOR, true, nullptr},
  {2, 2, DHT_SENSOR, false, nullptr}
};

// DHT Temperature and Humidity Sensor
#define DHTTYPE DHT11

// WiFi and MQTT setup
const char* ssid = "Pity";
const char* password = "";
const char* mqtt = "";

WiFiClient espClient;
PubSubClient client(espClient);

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

// Variables for watering
int amount = 1;
int pulses = 0;

// MQTT callback function
void callback(char* topic, byte* payload, unsigned int length) {
  // read the message
  String command = "";
  for (unsigned int i = 0; i < length; i++) {
    command += (char)payload[i];
  }

  command.trim();

  // confirm command on serial
  Serial.print("Received command: ");
  Serial.println(command);

  // change mode or execute command
    if (command == "READ") {
      currentStatus = READ;
      
    } else if (command.startsWith("WATER")) {
      // automatic watering
      if (command.length() > 6) {
        isTempWater = true;
        String tempWatering = command.substring(6);
        setWaterMode(tempWatering, true);
      }
      
      currentStatus = WATER;
      
    } else if (command == "IDLE") {
      currentStatus = IDLE;
      
    } else if (command.startsWith("CHMOD")) {     // change watering mode
      String wateringMode = command.substring(6);
      setWaterMode(wateringMode, false);
      
    } else if (command.startsWith("SET_ENV")) {   // change environment
      String envMode = command.substring(8);
      setEnvMode(envMode);
      
    } else {
      client.publish("irrigation/notice", "{\"error\":\"invalid_command\"}");
    }
}

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(115200);
  
  // Relay pin as output
  pinMode(relay, OUTPUT);

  // Initialize relay to be OFF (pumps off)
  digitalWrite(relay, HIGH);

  // Initialize temperature and humidity sensor
  for (int i = 0; i < max_num_sensors; i++) {
    if (sensors[i].active && sensors[i].type == DHT_SENSOR) {
        sensors[i].dht = new DHT(sensors[i].pin, DHTTYPE);
        sensors[i].dht->begin();
      }
  }

  // WiFi connection
  WiFi.begin(ssid, password);
  
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) { // wait until connected
    delay(500);
    Serial.print(".");
  }
  Serial.println("connected");

  // MQTT
  client.setServer(mqtt, 1883);
  client.setCallback(callback);
  reconnect();

  // Subscribe to topic
  client.subscribe("irrigation/control");
}

void loop() {  
  // Ensure MQTT works
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Perform action based on set mode
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
  // create array of sensors
  String msg = "{\"sensors\": [";
  for (int i = 0; i < max_num_sensors; i++) {
    if (!sensors[i].active) {
      continue; 
    }

    if (i != 0) {
      msg += ",";
    }

    msg += "{\"id\":"; 
    msg += sensors[i].id; 
    msg += ",\"type\":\"";
    msg += (sensors[i].type == SOIL ? "SOIL" : "DHT_SENSOR");
    msg += "\",";

    // soil moisture sensors
    if (sensors[i].type == SOIL) {
      int moistureValue = analogRead(sensors[i].pin);
      msg += "\"moisture\":"; 
      msg += moistureValue;
    }

    // dht sensor
    else if (sensors[i].type == DHT_SENSOR && sensors[i].dht != nullptr) {
      float humidity = sensors[i].dht->readHumidity();
      float temperature = sensors[i].dht->readTemperature();

      // Check if reading failed
      if (isnan(humidity) || isnan(temperature)) {
        client.publish("irrigation/notice", "{\"error\":\"error_reading_dht_sensor\"}");
        msg += "\"error\":\"NA\"";
      } else {
        msg += "\"humidity\":"; 
        msg += humidity; 
        msg += ",\"temperature\":"; 
        msg += temperature;
      }
    }
    msg += "}";
  }
  msg += "]}";
  client.publish("irrigation/readings", msg.c_str());
}


// Watering
void water(int pulses) {
  if (pulses <= 0) {
    client.publish("irrigation/notice", "{\"error\":\"invalid_watering_amount\"}");
    return;
  }
  
  String msg = "{\"notice\":\"watering_started(";
  msg += pulses*10;
  msg += ")\"}";
  
  client.publish("irrigation/notice", msg.c_str());
  
  // Watering in pulses
  for (int i = 0; i < pulses; i++) {
    digitalWrite(relay, LOW);   // Turn ON pump
    delay(250);                 // Wait for ON duration (approx. 10ml per pulse)
    digitalWrite(relay, HIGH);  // Turn OFF pump
    delay(250);                 // Wait for OFF duration
  }

  delay(200);
  client.publish("irrigation/notice", "{\"notice\":\"watering_finished\"}");
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
        client.publish("irrigation/notice", "{\"error\":\"invalid_watering_amount\"}");
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
    client.publish("irrigation/notice", "{\"error\":\"invalid_watering_mode\"}");
    return;
  }

  String msg;
  if (!temp) {
    msg += "{\"notice\":\"watering_mode_set(";
  } else {
    msg += "{\"notice\":\"temp_watering_mode_set(";
  }
  msg += mode;
  msg += ")\"}";
  client.publish("irrigation/notice", msg.c_str());
}

void setEnvMode(String mode) {
  if (mode == "INDOOR") {
    currentEnv = INDOOR;
    client.publish("irrigation/notice", "{\"notice\":\"env_set_indoor\"}");
    
  } else if (mode == "OUTDOOR") {
    currentEnv = OUTDOOR;
    client.publish("irrigation/notice", "{\"notice\":\"env_set_outdoor\"}");
    
  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_env\"}");
  }
}

// Reconnect to MQTT broker
void reconnect() {
  while (!client.connected()) {
    if (client.connect("ESP32Client")) {
      Serial.println("MQTT connection established");
      client.subscribe("irrigation/control");
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.println(client.state());
    
      delay(5000);
      Serial.println("Trying again");
    }
  }
}
