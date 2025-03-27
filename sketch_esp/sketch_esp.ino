#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <esp_wifi.h>

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
                        CUSTOM,
                        AUTO };

// Irrigation modes (based on environment)
enum EnvMode : byte { INDOOR,
                      OUTDOOR };

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

// Array of created pumps (default initialization)
const int max_num_pumps = 8;
Pump pumps[max_num_pumps] = {
  { 1, WATERING, 25, true, AUTO, MEDIUM, false, INDOOR, 1, 0 },
  { 2, WATERING, 26, true, AUTO, MEDIUM, false, INDOOR, 1, 0 },
  { 3, WATERING, 27, false, AUTO, MEDIUM, false, INDOOR, 1, 0 },
  { 4, WATERING, 21, false, AUTO, MEDIUM, false, INDOOR, 1, 0 },
  { 5, FERTILIZATION, 18, true, MEDIUM, MEDIUM, false, INDOOR, 50, 5 },
  { 6, FERTILIZATION, 19, false, MEDIUM, MEDIUM, false, INDOOR, 50, 5 },
  { 7, FERTILIZATION, 22, false, MEDIUM, MEDIUM, false, INDOOR, 50, 5 },
  { 8, FERTILIZATION, 23, false, MEDIUM, MEDIUM, false, INDOOR, 50, 5 }
};

// Reference for last called pump and sensor
int last_pump = 0;
int last_sensor = 0; 


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

// Array of created sensors (default initialization)
const int max_num_sensors = 6;
Sensor sensors[max_num_sensors] = {
  { 1, 32, SOIL, true, 1, nullptr },
  { 2, 33, SOIL, true, 2, nullptr },
  { 3, 34, SOIL, false, 3, nullptr },
  { 4, 35, SOIL, false, 4, nullptr },
  { 5, 4, DHT_SENSOR, true, 0, nullptr },   // 0 -> no pump for DHT sensor
  { 6, 5, DHT_SENSOR, false, 0, nullptr } 
};

// Function prototypes
int getPumpIndex(int pump_id);
void reconnect();
void activatePump(int pump_i);
void deactivatePump(int pump_i);
void sendAllData();
void changePump(int sensor_id, int pump_i);
void changeStatus(bool activate, String type, int id);
int getSensorIndex(int sensor_id);

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
    last_sensor = command.substring(8,9).toInt();

    // automatic watering from Node-RED
    if (command.length() > 10) {
      pumps[pump_index].isTempWater = true;
      String tempWatering = command.substring(10);
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

  } else if (command.startsWith("SET_STATUS")) {
    // SET_STATUS 0/1 P/S id
    bool activate = command.substring(11,12).toInt();
    String type = command.substring(13,14);
    int id = command.substring(15,16).toInt();
    changeStatus(activate, type, id);

  } else if (String(topic) == "irrigation/sleep") {
    if (command == "SLEEP") {
      // Put ESP into sleep mode between midnight and 4am
      Serial.println("Starting deep sleep until 4am");
      esp_sleep_enable_timer_wakeup(4*3600*1000000);
      esp_deep_sleep_start();
    }
  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_command\"}");
  }
}

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(115200);

  // Set station mode (ESP connecting to access point)
  WiFi.mode(WIFI_STA);
  // Enable power saving mode for WiFi
  WiFi.setSleep(true);
  esp_wifi_set_ps(WIFI_PS_MIN_MODEM);

  // Initialize default pump pins and set to be off (HIGH)
  for (int i = 0; i < max_num_pumps; i++) {
    if (pumps[i].active) {
      pinMode(pumps[i].pin, OUTPUT);
      digitalWrite(pumps[i].pin, HIGH);
    }
  }

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
  Serial.println("Connected to WiFi");

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
    Serial.println("Reconnecting MQTT...");
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

      water(pumps[last_pump].pulses, last_pump, last_sensor);
      currentStatus = IDLE;
      break;

    case FERTILIZE:
      fertilize(last_pump);
      currentStatus = IDLE;
      break;

    case IDLE:
    default:
      delay(1000);
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

      // Handle noise
      if (moistureValue > 500) {
        sensors[i].active = true;
      } else {
        sensors[i].active = false;
      }

    } else if (sensors[i].type == DHT_SENSOR && sensors[i].dht != nullptr) {
      // // SAMPLE DATA REMOVE
      // float humidity;
      // float temperature;
      // if (sensors[i].id == 5) {
      //   humidity = 40.0;
      //   temperature = 20.1;
      // } else {
      float humidity = sensors[i].dht->readHumidity();
      float temperature = sensors[i].dht->readTemperature();
      // }

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
        // // sample data REMOVE
        // if (sensors[i].id == 5) {
        //   float humidity = 40.0;
        //   float temperature = 20.1;
        //   msg += ",\"humidity\":";
        //   msg += humidity;
        //   msg += ",\"temperature\":";
        //   msg += temperature;
        // }

        // else {
        float humidity = sensors[i].dht->readHumidity();
        float temperature = sensors[i].dht->readTemperature();
        msg += ",\"humidity\":";
        msg += humidity;
        msg += ",\"temperature\":";
        msg += temperature;
        // }
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
void water(int pulses, int pump_i, int sensor_id) {
  if (!pumps[pump_i].active) {
    activatePump(pump_i);
  }

  String msg = "{\"notice\":\"watering_started(";
  msg += pumps[pump_i].id;
  msg += ",";
  msg += sensor_id;
  msg += ",";
  msg += pulses * 10;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());

  // Watering in pulses
  for (int i = 0; i < pumps[pump_i].pulses; i++) {
    digitalWrite(pumps[pump_i].pin, LOW);   // Turn ON pump
    delay(250);                             // Wait for ON duration (approx. 10ml per pulse)
    digitalWrite(pumps[pump_i].pin, HIGH);  // Turn OFF pump
    delay(250);                             // Wait for OFF duration
  }

  delay(1000);
  client.publish("irrigation/notice", "{\"notice\":\"watering_finished\"}");
}

// Fertilization
void fertilize(int pump_i) {
  if (pumps[pump_i].amount <= 0) {
    client.publish("irrigation/notice", "{\"error\":\"invalid_fertilization_amount\"}");
    return;
  }

  if (!pumps[pump_i].active) {
    activatePump(pump_i);
  }

  pumps[pump_i].pulses = pumps[pump_i].amount / 10;

  String msg = "{\"notice\":\"fertilization_started(";
  msg += pumps[pump_i].id;
  msg += ",";
  msg += pumps[pump_i].amount;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());

  // Fertilization in pulses
  for (int i = 0; i < pumps[pump_i].pulses; i++) {
    digitalWrite(pumps[pump_i].pin, LOW);   // Turn ON pump
    delay(250);                             // Wait for ON duration (approx. 10ml per pulse)
    digitalWrite(pumps[pump_i].pin, HIGH);  // Turn OFF pump
    delay(250);                             // Wait for OFF duration
  }

  msg = "{\"notice\":\"fertilization_finished(";
  msg += pumps[pump_i].id;
  msg += ")\"}";

  delay(200);
  client.publish("irrigation/notice", msg.c_str());
}

// Change watering mode for pump
void setWaterMode(String mode, bool temp, int pump_i) {
  if (mode == "LIGHT") {
    if (!temp) {
      pumps[pump_i].currentWaterMode = LIGHT;
    } else {
      pumps[pump_i].tempWaterMode = LIGHT;
    }

  } else if (mode == "MEDIUM") {
    if (!temp) {
      pumps[pump_i].currentWaterMode = MEDIUM;
    } else {
      pumps[pump_i].tempWaterMode = MEDIUM;
    }

  } else if (mode == "HEAVY") {
    if (!temp) {
      pumps[pump_i].currentWaterMode = HEAVY;
    } else {
      pumps[pump_i].tempWaterMode = HEAVY;
    }
  }
    else if (mode == "AUTO") {
    if (!temp) {
      pumps[pump_i].currentWaterMode = AUTO;
    }

  } else if (mode.startsWith("CUSTOM")) {
    // If custom amount is provided
    if (mode.length() > 6) {
      String wateringAmount = mode.substring(7);  //extract the amount of ml for watering
      int amount = wateringAmount.toInt();

      if (amount < 10) {
        client.publish("irrigation/notice", "{\"error\":\"invalid_watering_amount\"}");
        return;

      } else if (amount > 1000) {
        // Limit max amount to 1l
        pumps[pump_i].amount = 1000;
        mode = "CUSTOM 1000";

      } else {
        pumps[pump_i].amount = amount;
      }
    }

    if (!temp) {
      pumps[pump_i].currentWaterMode = CUSTOM;
    } else {
      pumps[pump_i].tempWaterMode = CUSTOM;
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
void setEnvMode(String mode, int pump_i) {
  String msg = "{\"notice\":\"env_set(";
  if (mode == "INDOOR") {
    pumps[pump_i].env = INDOOR;

    msg += pumps[pump_i].id;
    msg += ",indoor)\"}";
    client.publish("irrigation/notice", msg.c_str());

  } else if (mode == "OUTDOOR") {
    pumps[pump_i].env = OUTDOOR;

    msg += pumps[pump_i].id;
    msg += ",outdoor)\"}";
    client.publish("irrigation/notice", msg.c_str());

  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_env\"}");
  }
}

// Change amount of ml used for fertilization
void setFertAmount(int pump_i, int amount) {
  if (amount <= 0) {
    client.publish("irrigation/notice", "{\"error\":\"invalid_fertilization_amount\"}");
    return;

  } else if (amount > 1000) {
    amount = 1000;
  }
  
  pumps[pump_i].amount = amount;
  String msg = "{\"notice\":\"fertilization_amount_set(";
  msg += pumps[pump_i].id;
  msg += ",";
  msg += amount;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());
}

// Change pump assignment for the sensor
void changePump(int sensor_id, int pump_i) {
  int sensor_index = getSensorIndex(sensor_id);

  int old_pump = sensors[sensor_index].pump;

  activatePump(pump_i);

  sensors[sensor_index].pump = pumps[pump_i].id;
  String msg = "{\"notice\":\"pump_set(";
  msg += pumps[pump_i].id;
  msg += ")_sensor(";
  msg += sensor_id;
  msg += ")\"}";
  client.publish("irrigation/notice", msg.c_str());

  // Deactivate old pump if not used
  bool keep_pump_active = false;
  for (int i = 0; i < max_num_sensors; i++) {
    if (i == sensor_id) {
      continue;
    }

    if (old_pump == sensors[i].pump && sensors[i].active) {
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
  // Pumps
  String msg_pumps = "{\"pumps\":[";

  for (int i = 0; i < max_num_pumps; i++) {
    if (i != 0) {
        msg_pumps += ",";
    }
    msg_pumps += "{\"id\":" + String(pumps[i].id) + ",";
    msg_pumps += "\"type\":\"" + String((pumps[i].type == WATERING) ? "WATERING" : "FERTILIZATION") + "\",";
    msg_pumps += "\"pin\":" + String(pumps[i].pin) + ",";
    msg_pumps += "\"active\":" + String(pumps[i].active) + ",";
    msg_pumps += "\"currentWaterMode\":\"" + String(
        (pumps[i].currentWaterMode == LIGHT) ? "LIGHT" :
        (pumps[i].currentWaterMode == MEDIUM) ? "MEDIUM" :
        (pumps[i].currentWaterMode == HEAVY) ? "HEAVY" : 
        (pumps[i].currentWaterMode == AUTO) ? "AUTO" : "CUSTOM") + "\",";
    msg_pumps += "\"env\":\"" + String((pumps[i].env == INDOOR) ? "INDOOR" : "OUTDOOR") + "\",";
    msg_pumps += "\"amount\":" + String(pumps[i].amount) + "}";
  }

  msg_pumps += "]}";

  client.publish("irrigation/data", msg_pumps.c_str());

  // Sensors
  float humidity = -1;
  float temperature = -1;

  String msg_sensors = "{\"sensors\":[";

  for (int i = 0; i < max_num_sensors; i++) {
    if (i != 0) {
        msg_sensors += ",";
    }

    msg_sensors += "{\"id\":" + String(sensors[i].id) + ",";
    msg_sensors += "\"pin\":" + String(sensors[i].pin) + ",";
    msg_sensors += "\"active\":" + String(sensors[i].active) + ",";
    msg_sensors += "\"type\":\"" + String((sensors[i].type == SOIL) ? "SOIL" : "DHT_SENSOR") + "\",";

    if (sensors[i].type == SOIL) {
      msg_sensors += "\"pump\":" + String(sensors[i].pump) + ",";
      msg_sensors += "\"moisture\":" + String(analogRead(sensors[i].pin)) + "}";

    } else if (sensors[i].type == DHT_SENSOR && sensors[i].dht != nullptr) {
      // SAMPLE DATA REMOVE
      // if (sensors[i].id == 5) {
      //   humidity = 40.0;
      //   temperature = 20.1;
      // }
      // else {
      humidity = sensors[i].dht->readHumidity();
      temperature = sensors[i].dht->readTemperature();
      // }
      
      if (isnan(humidity)) {
        humidity = -1;
      }
      if (isnan(temperature)) {
        temperature = -1;
      } 
    
      msg_sensors += "\"humidity\":" + String(humidity) + ",";
      msg_sensors += "\"temperature\":" + String(temperature) + "}";
      
    }
  }

  msg_sensors += "]}";

  delay(2000);
  client.publish("irrigation/data", msg_sensors.c_str());
}

// Activate pump if not active
void activatePump(int pump_i) {
  if (!pumps[pump_i].active) {
      pinMode(pumps[pump_i].pin, OUTPUT);
      digitalWrite(pumps[pump_i].pin, HIGH);
      pumps[pump_i].active = true;

      String msg = "{\"notice\":\"pump_set(";
      msg += pumps[pump_i].id;
      msg += ")\"}";
      client.publish("irrigation/notice", msg.c_str());
  }
}

// Deactivate pump
void deactivatePump(int pump_i) {
  pumps[pump_i].active = false;
  // Change pump pin mode to INPUT to preserve battery
  pinMode(pumps[pump_i].pin, INPUT); 
  digitalWrite(pumps[pump_i].pin, LOW);

  String msg = "{\"notice\":\"pump_unset(";
  msg += pumps[pump_i].id;
  msg += ")\"}";
  client.publish("irrigation/notice", msg.c_str());
}

// Retrieve index of a pump with id pump_id from array pumps
int getPumpIndex(int pump_id) {
  for (int i = 0; i < max_num_pumps; i++) {
    if (pumps[i].id == pump_id) {
      return i;
    }
  }
  return -1;
}

// Retrieve index of a sensor with id sensor_id from array sensors
int getSensorIndex(int sensor_id) {
  for (int i = 0; i < max_num_sensors; i++) {
    if (sensors[i].id == sensor_id) {
      return i;
    }
  }
  return -1;
}

// Activate or Deactivate pump or sensor
void changeStatus(bool activate, String type, int id) {
  if (type == "P") {  // pump
    int pump_i = getPumpIndex(id);

    if (activate) {
      activatePump(pump_i);
    } else {
      deactivatePump(pump_i);
    }
    
  } else if (type == "S") {   // sensor
    int pump_i = getSensorIndex(id);
    sensors[pump_i].active = activate;

    String msg = "{\"notice\":\"sensor(";
    msg += id;
    msg += ")_status_set(";
    msg += activate;
    msg += ")\"}";
    client.publish("irrigation/notice", msg.c_str());
  } 
}

// Reconnect to MQTT broker
void reconnect() {
  Serial.println("Establishing MQTT connection");
  while (!client.connected()) {
    if (client.connect("ESP32Client")) {
      client.setBufferSize(1024);
      Serial.println("MQTT connection established");
      client.subscribe("irrigation/control");
      client.subscribe("irrigation/sleep");
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.println(client.state());

      delay(1000);
      Serial.println("Trying again");
    }
  }
}