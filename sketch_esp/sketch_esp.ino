#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

// Status modes
enum StatusMode : byte { IDLE,
                         READ,
                         WATER,
                         FERTILIZE };
StatusMode currentStatus = IDLE;

// Watering modes
enum WaterMode : byte { LIGHT,
                        MEDIUM,
                        HEAVY,
                        CUSTOM };

// Irrigation modes (based on environment)
enum EnvMode : byte { INDOOR,
                      OUTDOOR };
// EnvMode currentEnv = INDOOR;

// WaterMode currentWaterMode = MEDIUM;
// WaterMode tempWaterMode = MEDIUM; // automatic watering mode select
// bool isTempWater = false;

// Variables for watering
// int amount = 1;
// int pulses = 0;

// Pin assignments
// const int pump = 26;

// Pumps
enum PumpType : byte { WATERING,
                       FERTILIZATION };
struct Pump {
  int id;
  PumpType type;
  int pin;
  bool active;
  WaterMode currentWaterMode;
  WaterMode tempWaterMode;
  bool isTempWater;
  EnvMode env;
  int amount;
  int pulses;
};

// Array of created pumps
const int max_num_pumps = 5;
Pump pumps[max_num_pumps] = {
  { 1, WATERING, 25, true, MEDIUM, MEDIUM, false, INDOOR, 1, 0 },
  { 2, WATERING, 26, true, MEDIUM, MEDIUM, false, INDOOR, 1, 0 },
  { 3, WATERING, 27, false, MEDIUM, MEDIUM, false, INDOOR, 1, 0 },
  { 4, FERTILIZATION, 18, true, MEDIUM, MEDIUM, false, INDOOR, 1, 0 },
  { 5, FERTILIZATION, 19, false, MEDIUM, MEDIUM, false, INDOOR, 1, 0 },
};

// Reference for last called pump
int last_pump = 0;


// Sensors
enum SensorType : byte { SOIL,
                         DHT_SENSOR };
struct Sensor {
  int id;
  int pin;
  SensorType type;
  bool active;
  int pump;
  DHT* dht;  // DHT instance pointer
};

// Type of DHT sensor used
#define DHTTYPE DHT11

// Array of created sensors
const int max_num_sensors = 6;
Sensor sensors[max_num_sensors] = {
  { 1, 32, SOIL, true, 1, nullptr },
  { 2, 33, SOIL, true, 2, nullptr },
  { 3, 34, SOIL, false, 1, nullptr },
  { 4, 35, SOIL, false, 3, nullptr },
  { 1, 4, DHT_SENSOR, true, 0, nullptr },   // 0 -> no pump for DHT sensor
  { 2, 16, DHT_SENSOR, false, 0, nullptr } 
};

// Function prototypes
int getPumpIndex(int pump_id);
void reconnect();
void activatePump(int pump_id);
void deactivatePump(int pump_id);
void sendAllData();
void changePump(int sensor_id, int pump_id);

// WiFi and MQTT setup
const char* ssid = "Pity";
const char* password = "";
const char* mqtt = "192.168.8.140";

WiFiClient espClient;
PubSubClient client(espClient);

// MQTT callback function
void callback(char* topic, byte* payload, unsigned int length) {
  // Read the obtained message
  String command = "";
  for (unsigned int i = 0; i < length; i++) {
    command += (char)payload[i];
  }

  command.trim();

  // Confirm command on serial
  Serial.print("Received command: ");
  Serial.println(command);

  // Change mode or execute command
  if (command == "READ") {
    currentStatus = READ;

  } else if (command.startsWith("WATER")) {
    int pump_id = command.substring(6,7).toInt();
    int pump_index = getPumpIndex(pump_id);
    last_pump = pump_index;
    // automatic watering
    if (command.length() > 7) {
      pumps[pump_index].isTempWater = true;
      // isTempWater = true;
      String tempWatering = command.substring(8);
      setWaterMode(tempWatering, true, pump_index);
    }

    currentStatus = WATER;

  } else if (command.startsWith("FERTILIZE")) {
    int pump_id = command.substring(10, 11).toInt();
    int pump_index = getPumpIndex(pump_id);
    last_pump = pump_index;
    currentStatus = FERTILIZE;

  } else if (command.startsWith("IDLE")) {
    currentStatus = IDLE;

  } else if (command.startsWith("CHMOD")) {  // change watering mode
    int pump_id = command.substring(6, 7).toInt();
    int pump_index = getPumpIndex(pump_id);
    String wateringMode = command.substring(8);
    setWaterMode(wateringMode, false, pump_index);

  } else if (command.startsWith("SET_ENV")) {  // change environment
    int pump_id = command.substring(8, 9).toInt();
    int pump_index = getPumpIndex(pump_id);
    String envMode = command.substring(10);
    setEnvMode(envMode, pump_index);

  } else if (command.startsWith("SET_FERT_AMOUNT")) {
    int pump_id = command.substring(16, 17).toInt();
    int pump_index = getPumpIndex(pump_id);
    int amount = command.substring(18).toInt();
    setFertAmount(pump_index, amount);

  } else if (command.startsWith("CH_PUMP")) {
    int sensor_id = command.substring(8, 9).toInt();
    int pump_id = command.substring(10, 11).toInt();
    int pump_index = getPumpIndex(pump_id);
    changePump(sensor_id, pump_index);

  } else if (command == "GET_ALL") {
    sendAllData();
    
  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_command\"}");
  }
}

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(115200);

  // Set station mode (ESP connecting to access point)
  // WiFi.mode(WIFI_STA);
  // Enable power saving mode for WiFi
  // WiFi.setSleep(true);

  // Initialize default pump pins and set to be off (HIGH)
  for (int i = 0; i < max_num_pumps; i++) {
    if (pumps[i].active) {
      pinMode(pumps[i].pin, OUTPUT);
      digitalWrite(pumps[i].pin, HIGH);
    }
  }

  // // pump pin as output
  // pinMode(pump, OUTPUT);

  // // Initialize pump to be OFF (pumps off)
  // digitalWrite(pump, HIGH);

  // Initialize temperature and humidity sensors
  for (int i = 0; i < max_num_sensors; i++) {
    if (sensors[i].type == DHT_SENSOR) {
      sensors[i].dht = new DHT(sensors[i].pin, DHTTYPE);
      sensors[i].dht->begin();
    }
  }

  // WiFi connection
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {  // wait until connected
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
  // Ensure MQTT connection is established
  if (!client.connected()) {
    reconnect();
    Serial.println("Reconnecting..");
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

      if (pumps[last_pump].isTempWater) {
        modeToUse = pumps[last_pump].tempWaterMode;
        pumps[last_pump].isTempWater = false;

      } else {
        modeToUse = pumps[last_pump].currentWaterMode;
      }

      switch (modeToUse) {
        case LIGHT:
          pumps[last_pump].pulses = (pumps[last_pump].env == INDOOR) ? 2 : 10;
          break;

        case MEDIUM:
          pumps[last_pump].pulses = (pumps[last_pump].env == INDOOR) ? 5 : 35;
          break;

        case HEAVY:
          pumps[last_pump].pulses = (pumps[last_pump].env == INDOOR) ? 10 : 70;
          break;

        case CUSTOM:
          pumps[last_pump].pulses = pumps[last_pump].amount / 10;  // 1 pulse = approx. 10ml
          break;
      }

      water(pumps[last_pump].pulses, last_pump);
      currentStatus = IDLE;
      break;

    case FERTILIZE:
      fertilize(last_pump);
      currentStatus = IDLE;
      break;

    case IDLE:
    default:
      // switch into light sleep mode - wakes up upon receival of MQTT message 
      // Serial.println("Switching into light sleep");
      // esp_light_sleep_start(); 
      // Serial.println("Woke up from light sleep");
      break;
  }
}

// Get sensors' data
void takeReading() {
  // Create array of sensors for the output message
  String msg = "{\"sensors\": [";

  for (int i = 0; i < max_num_sensors; i++) {
    // Determine if sensor is active
    if (sensors[i].type == SOIL) {
      int moistureValue = analogRead(sensors[i].pin);

      if (moistureValue > 500) {
        sensors[i].active = true;
      } else {
        sensors[i].active = false;
      }

    } else if (sensors[i].type == DHT_SENSOR && sensors[i].dht != nullptr) {
      float humidity = sensors[i].dht->readHumidity();
      float temperature = sensors[i].dht->readTemperature();

      if (!isnan(humidity) && !isnan(temperature)) {
        sensors[i].active = true;
      } else {
        sensors[i].active = false;
      }
    }

    // Obtain readings if sensor is active
    if (sensors[i].active) {
      if (i != 0) {
        msg += ",";
      }

      msg += "{\"id\":";
      msg += sensors[i].id;
      msg += ",\"type\":\"";
      msg += (sensors[i].type == SOIL ? "SOIL" : "DHT_SENSOR");
      msg += "\",\"pump\":";
      msg += sensors[i].pump;

      if (sensors[i].type == SOIL) {
        int moistureValue = analogRead(sensors[i].pin);
        msg += ",\"moisture\":";
        msg += moistureValue;
      } else if (sensors[i].type == DHT_SENSOR && sensors[i].dht != nullptr) {
        float humidity = sensors[i].dht->readHumidity();
        float temperature = sensors[i].dht->readTemperature();
        msg += ",\"humidity\":";
        msg += humidity;
        msg += ",\"temperature\":";
        msg += temperature;
      }

    msg += "}";

    } else {
      continue;
    }     
  }
  msg += "]}";

  client.publish("irrigation/readings", msg.c_str());
}


// Watering
void water(int pulses, int pump_id) {
  if (!pumps[pump_id].active) {
    activatePump(pump_id);
  }

  String msg = "{\"notice\":\"watering_started(";
  msg += pumps[pump_id].id;
  msg += ",";
  msg += pulses * 10;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());

  // Watering in pulses
  for (int j = 0; j < pumps[pump_id].pulses; j++) {
    digitalWrite(pumps[pump_id].pin, LOW);   // Turn ON pump
    delay(250);                                // Wait for ON duration (approx. 10ml per pulse)
    digitalWrite(pumps[pump_id].pin, HIGH);  // Turn OFF pump
    delay(250);                                // Wait for OFF duration
  }

  delay(1000);
  client.publish("irrigation/notice", "{\"notice\":\"watering_finished\"}");
}

// Fertilization
void fertilize(int pump_id) {
  for (int i = 0; i < max_num_pumps; i++) {
    if (pumps[i].id == pump_id) {
      if (pumps[i].amount <= 0) {
        client.publish("irrigation/notice", "{\"error\":\"invalid_fertilization_amount\"}");
        return;
      }

      if (!pumps[i].active) {
        activatePump(pump_id);
      }

      pumps[i].pulses = pumps[i].amount / 10;

      String msg = "{\"notice\":\"fertilization_started(";
      msg += pumps[i].amount;
      msg += ")\"}";

      client.publish("irrigation/notice", msg.c_str());

      // Fertilization in pulses
      for (int j = 0; j < pumps[i].pulses; j++) {
        digitalWrite(pumps[i].pin, LOW);   // Turn ON pump
        delay(250);                                // Wait for ON duration (approx. 10ml per pulse)
        digitalWrite(pumps[i].pin, HIGH);  // Turn OFF pump
        delay(250);                                // Wait for OFF duration
      }

      delay(200);
      client.publish("irrigation/notice", "{\"notice\":\"fertilization_finished\"}");
      
      break;
    }
  }
}

// Change watering mode for pump
void setWaterMode(String mode, bool temp, int pump_id) {
  if (mode == "LIGHT") {
    if (!temp) {
      pumps[pump_id].currentWaterMode = LIGHT;
    } else {
      pumps[pump_id].tempWaterMode = LIGHT;
    }

  } else if (mode == "MEDIUM") {
    if (!temp) {
      pumps[pump_id].currentWaterMode = MEDIUM;
    } else {
      pumps[pump_id].tempWaterMode = MEDIUM;
    }

  } else if (mode == "HEAVY") {
    if (!temp) {
      pumps[pump_id].currentWaterMode = HEAVY;
    } else {
      pumps[pump_id].tempWaterMode = HEAVY;
    }

  } else if (mode.startsWith("CUSTOM")) {
    // If custom amount is provided
    if (mode.length() > 6) {
      String wateringAmount = mode.substring(7);  //extract the amount of ml for watering
      int amount = wateringAmount.toInt();

      if (amount <= 0) {
        client.publish("irrigation/notice", "{\"error\":\"invalid_watering_amount\"}");
        return;

      } else if (amount > 1000) {
        // Limit max amount to 1l
        pumps[pump_id].amount = 1000;
        mode = "CUSTOM 1000";

      } else {
        pumps[pump_id].amount = amount;
      }
    }

    if (!temp) {
      pumps[pump_id].currentWaterMode = CUSTOM;
    } else {
      pumps[pump_id].tempWaterMode = CUSTOM;
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

// Set environment type for pump
void setEnvMode(String mode, int pump_id) {
  if (mode == "INDOOR") {
    pumps[pump_id].env = INDOOR;
    client.publish("irrigation/notice", "{\"notice\":\"env_set_indoor\"}");

  } else if (mode == "OUTDOOR") {
    pumps[pump_id].env = OUTDOOR;
    client.publish("irrigation/notice", "{\"notice\":\"env_set_outdoor\"}");

  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_env\"}");
  }
}

// Change amount of ml used for fertilization
void setFertAmount(int pump_id, int amount) {
  if (amount <= 0) {
    client.publish("irrigation/notice", "{\"error\":\"invalid_fertilization_amount\"}");
    return;

  } else if (amount > 1000) {
    amount = 1000;
  }
  
  pumps[pump_id].amount = amount;
  String msg = "{\"notice\":\"fertilization_amount_set(";
  msg += amount;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());
}

// Change pump assignment for the sensor
void changePump(int sensor_id, int pump_id) {
  for (int i = 0; i < max_num_sensors; i++) {
    if (sensors[i].id == sensor_id) {
      sensor_id = i;
      break;
    }
  }

  int old_pump = sensors[sensor_id].pump;

  activatePump(pump_id);

  sensors[sensor_id].pump = pumps[pump_id].id;
  String msg = "{\"notice\":\"sensor(";
  msg += sensor_id;
  msg += ")_pump_set(";
  msg += pumps[pump_id].id;
  msg += ")\"}";
  client.publish("irrigation/notice", msg.c_str());

  // Deactivate old pump if not used
  bool keep_pump_active = false;
  for (int i = 0; i < max_num_sensors; i++) {
    if (i == sensor_id) {
      continue;
    }

    if (old_pump == sensors[i].pump) {
      keep_pump_active = true;
      break;
    }
  }

  if (!keep_pump_active) {
    deactivatePump(getPumpIndex(old_pump));
  }
}

// Send data about pumps and sensors
void sendAllData() {
  // Active pumps
  String msg_pumps = "{\"pumps\":[";

  for (int i = 0; i < max_num_pumps; i++) {
      if (pumps[i].active) {
          if (i != 0) {
              msg_pumps += ",";
          }
          msg_pumps += "{\"id\":" + String(pumps[i].id) + ",";
          msg_pumps += "\"type\":\"" + String((pumps[i].type == WATERING) ? "WATERING" : "FERTILIZATION") + "\",";
          msg_pumps += "\"pin\":" + String(pumps[i].pin) + ",";
          msg_pumps += "\"currentWaterMode\":\"" + String(
              (pumps[i].currentWaterMode == LIGHT) ? "LIGHT" :
              (pumps[i].currentWaterMode == MEDIUM) ? "MEDIUM" :
              (pumps[i].currentWaterMode == HEAVY) ? "HEAVY" : "CUSTOM") + "\",";
          msg_pumps += "\"env\":\"" + String((pumps[i].env == INDOOR) ? "INDOOR" : "OUTDOOR") + "\",";
          msg_pumps += "\"amount\":" + String(pumps[i].amount) + "}";
      }
  }

  msg_pumps += "]}";

  client.publish("irrigation/data/pumps", msg_pumps.c_str());

  String msg_sensors = "{";

  // active sensors
  msg_sensors += "\"sensors\":[";

  for (int i = 0; i < max_num_sensors; i++) {
      if (sensors[i].active) {
          if (i != 0) {
              msg_sensors += ",";
          }

          msg_sensors += "{\"id\":" + String(sensors[i].id) + ",";
          msg_sensors += "\"pin\":" + String(sensors[i].pin) + ",";
          msg_sensors += "\"type\":\"" + String((sensors[i].type == SOIL) ? "SOIL" : "DHT_SENSOR") + "\",";
          msg_sensors += "\"pump\":" + String(sensors[i].pump) + "}";
      }
  }

  msg_sensors += "]}";

  delay(1000);
  client.publish("irrigation/data/sensors", msg_sensors.c_str());
}

// Activate pump if not active
void activatePump(int pump_id) {
  if (!pumps[pump_id].active) {
      pinMode(pumps[pump_id].pin, OUTPUT);
      digitalWrite(pumps[pump_id].pin, HIGH);
      pumps[pump_id].active = true;
      Serial.print("Pump ");
      Serial.print(pump_id);
      Serial.println(" activated.");
  }
}

// Deactivate pump
void deactivatePump(int pump_id) {
  pumps[pump_id].active = false;
  // Change pump pin mode to INPUT to preserve battery
  pinMode(pumps[pump_id].pin, INPUT); 
  digitalWrite(pumps[pump_id].pin, LOW);
}

int getPumpIndex(int pump_id) {
  for (int i = 0; i < max_num_pumps; i++) {
    if (pumps[i].id == pump_id) {
      return i;
    }
  }
  return -1;
}

// Reconnect to MQTT broker
void reconnect() {
  while (!client.connected()) {
    if (client.connect("ESP32Client")) {
      client.setBufferSize(512);
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