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
// const int relay = 26;

// relays
enum RelayType : byte { WATERING,
                        FERTILIZATION };
struct Relay {
  int id;
  RelayType type;
  int pin;
  bool active;
  WaterMode currentWaterMode;
  WaterMode tempWaterMode;
  bool isTempWater;
  EnvMode env;
  int amount;
  int pulses;
};

// array of created relays
const int max_num_relays = 3;
Relay relays[max_num_relays] = {
  { 1, WATERING, 26, true, MEDIUM, MEDIUM, false, INDOOR, 1, 0 },
  { 2, WATERING, 25, false, MEDIUM, MEDIUM, false, INDOOR, 1, 0 },
  { 3, FERTILIZATION, 27, true, MEDIUM, MEDIUM, false, INDOOR, 1, 0 }
};

// last called relay
int last_relay = 0;


// sensors
enum SensorType : byte { SOIL,
                         DHT_SENSOR };
struct Sensor {
  int id;
  int pin;
  SensorType type;
  bool active;
  int relay;
  DHT* dht;  // DHT instance pointer
};

// type of DHT sensor used
#define DHTTYPE DHT11

// array of created sensors
const int max_num_sensors = 6;
Sensor sensors[max_num_sensors] = {
  { 1, 34, SOIL, true, 1, nullptr },
  { 2, 35, SOIL, true, 1, nullptr },
  { 3, 32, SOIL, false, 1, nullptr },
  { 4, 33, SOIL, false, 1, nullptr },
  { 1, 4, DHT_SENSOR, true, 0, nullptr },
  { 2, 2, DHT_SENSOR, false, 0, nullptr }
};


// WiFi and MQTT setup
const char* ssid = "Pity";
const char* password = "";
const char* mqtt = "";

WiFiClient espClient;
PubSubClient client(espClient);

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
    if (command.length() > 7) {
      int relay_id = command.substring(6, 1).toInt();
      relays[relay_id].isTempWater = true;
      last_relay = relay_id;
      // isTempWater = true;
      String tempWatering = command.substring(8);
      setWaterMode(tempWatering, true, relay_id);
    }

    currentStatus = WATER;

  } else if (command.startsWith("FERTILIZE")) {
    int relay_id = command.substring(10, 1).toInt();
    last_relay = relay_id;
    currentStatus = FERTILIZE;

  } else if (command == "IDLE") {
    currentStatus = IDLE;

  } else if (command.startsWith("CHMOD")) {  // change watering mode
    int relay_id = command.substring(6, 1).toInt();
    String wateringMode = command.substring(8);
    setWaterMode(wateringMode, false, relay_id);

  } else if (command.startsWith("SET_ENV")) {  // change environment
    int relay_id = command.substring(8, 1).toInt();
    String envMode = command.substring(10);
    setEnvMode(envMode, relay_id);

  } else if (command.startsWith("SET_FERT_AMOUNT")) {
    int relay_id = command.substring(16, 1).toInt();
    int amount = command.substring(18).toInt();
    setFertAmount(relay_id, amount);

  } else if (command.startsWith("CH_PUMP")) {
    int sensor_id = command.substring(8, 1).toInt();
    int relay_id = command.substring(10, 1).toInt();
    change_relay(sensor_id, relay_id);

  } else if (command == "GET_ALL") {
    send_all_data();
    
  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_command\"}");
  }
}

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(115200);

  // Set relay pins as output and initialize to be off
  for (int i = 0; i < max_num_relays; i++) {
    if (relays[i].active) {
      pinMode(relays[i].pin, OUTPUT);
      digitalWrite(relays[i].pin, HIGH);
    }
  }

  // // Relay pin as output
  // pinMode(relay, OUTPUT);

  // // Initialize relay to be OFF (pumps off)
  // digitalWrite(relay, HIGH);

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

      if (relays[last_relay].isTempWater) {
        modeToUse = relays[last_relay].tempWaterMode;
        relays[last_relay].isTempWater = false;

      } else {
        modeToUse = relays[last_relay].currentWaterMode;
      }

      switch (modeToUse) {
        case LIGHT:
          relays[last_relay].pulses = (relays[last_relay].env == INDOOR) ? 2 : 10;
          break;

        case MEDIUM:
          relays[last_relay].pulses = (relays[last_relay].env == INDOOR) ? 5 : 35;
          break;

        case HEAVY:
          relays[last_relay].pulses = (relays[last_relay].env == INDOOR) ? 10 : 70;
          break;

        case CUSTOM:
          relays[last_relay].pulses = relays[last_relay].amount / 10;  // 1 pulse = approx. 10ml
          break;
      }

      water(relays[last_relay].pulses, last_relay);
      currentStatus = IDLE;
      break;

    case FERTILIZE:
      fertilize(last_relay);
      currentStatus = IDLE;
      break;

    case IDLE:
    default:
      // wait for commands
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
void water(int pulses, int relay_id) {
  if (relays[relay_id].pulses <= 0) {
    client.publish("irrigation/notice", "{\"error\":\"invalid_watering_amount\"}");
    return;
  }

  String msg = "{\"notice\":\"watering_started(";
  msg += pulses * 10;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());

  // Watering in pulses
  for (int i = 0; i < relays[relay_id].pulses; i++) {
    digitalWrite(relays[relay_id].pin, LOW);   // Turn ON pump
    delay(250);                                // Wait for ON duration (approx. 10ml per pulse)
    digitalWrite(relays[relay_id].pin, HIGH);  // Turn OFF pump
    delay(250);                                // Wait for OFF duration
  }

  delay(200);
  client.publish("irrigation/notice", "{\"notice\":\"watering_finished\"}");
}

void fertilize(int relay_id) {
  if (relays[relay_id].amount <= 0) {
    client.publish("irrigation/notice", "{\"error\":\"invalid_fertilization_amount\"}");
    return;
  }

  relays[relay_id].pulses = relays[relay_id].amount / 10;

  String msg = "{\"notice\":\"fertilization_started(";
  msg += relays[relay_id].amount;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());

  // Fertilization in pulses
  for (int i = 0; i < relays[relay_id].pulses; i++) {
    digitalWrite(relays[relay_id].pin, LOW);   // Turn ON pump
    delay(250);                                // Wait for ON duration (approx. 10ml per pulse)
    digitalWrite(relays[relay_id].pin, HIGH);  // Turn OFF pump
    delay(250);                                // Wait for OFF duration
  }

  delay(200);
  client.publish("irrigation/notice", "{\"notice\":\"fertilization_finished\"}");
}

void setWaterMode(String mode, bool temp, int relay_id) {
  if (mode == "LIGHT") {
    if (!temp) {
      relays[relay_id].currentWaterMode = LIGHT;
    } else {
      relays[relay_id].tempWaterMode = LIGHT;
    }

  } else if (mode == "MEDIUM") {
    if (!temp) {
      relays[relay_id].currentWaterMode = MEDIUM;
    } else {
      relays[relay_id].tempWaterMode = MEDIUM;
    }

  } else if (mode == "HEAVY") {
    if (!temp) {
      relays[relay_id].currentWaterMode = HEAVY;
    } else {
      relays[relay_id].tempWaterMode = HEAVY;
    }

  } else if (mode.startsWith("CUSTOM")) {
    // if custom amount is provided
    if (mode.length() > 6) {
      String wateringAmount = mode.substring(7);  //extract the amount of ml for watering
      int amount = wateringAmount.toInt();

      if (amount <= 0) {
        client.publish("irrigation/notice", "{\"error\":\"invalid_watering_amount\"}");
        return;

      } else if (amount > 1000) {
        // limit max amount to 1l
        relays[relay_id].amount = 1000;
        mode = "CUSTOM 1000";

      } else {
        relays[relay_id].amount = amount;
      }
    }

    if (!temp) {
      relays[relay_id].currentWaterMode = CUSTOM;
    } else {
      relays[relay_id].tempWaterMode = CUSTOM;
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

void setEnvMode(String mode, int relay_id) {
  if (mode == "INDOOR") {
    relays[relay_id].env = INDOOR;
    client.publish("irrigation/notice", "{\"notice\":\"env_set_indoor\"}");

  } else if (mode == "OUTDOOR") {
    relays[relay_id].env = OUTDOOR;
    client.publish("irrigation/notice", "{\"notice\":\"env_set_outdoor\"}");

  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_env\"}");
  }
}

void setFertAmount(int relay_id, int amount) {
  if (amount <= 0) {
    client.publish("irrigation/notice", "{\"error\":\"invalid_fertilization_amount\"}");
    return;

  } else if (amount > 1000) {
    amount = 1000;
  }

  relays[relay_id].amount = amount;
  String msg = "{\"notice\":\"fertilization_amount_set(";
  msg += amount;
  msg += ")\"}";

  client.publish("irrigation/notice", msg.c_str());
}

void change_relay(int sensor_id, int relay_id) {
  bool exists = false;
  for (int i = 0; i < max_num_relays; i++) {
    if (relays[i].id == relay_id) {
      exists = true;
      relays[i].active = true;
      break;
    }
  }

  if (exists) {
    sensors[sensor_id].relay = relay_id;
    String msg = "{\"notice\":\"sensor(";
    msg += sensor_id;
    msg += ")_relay_set(";
    msg += relay_id;
    msg += ")\"}";
    client.publish("irrigation/notice", msg.c_str());

  } else {
    client.publish("irrigation/notice", "{\"error\":\"invalid_relay\"}");
    return;
  }
}

void send_all_data() {
  String json = "{";

  // active pumps
  json += "\"pumps\":[";

  for (int i = 0; i < max_num_relays; i++) {
      if (relays[i].active) {
          if (i != 0) {
              json += ",";
          }
          json += "{\"id\":" + String(relays[i].id) + ",";
          json += "\"type\":\"" + String((relays[i].type == WATERING) ? "WATERING" : "FERTILIZATION") + "\",";
          json += "\"pin\":" + String(relays[i].pin) + ",";
          json += "\"currentWaterMode\":\"" + String(
              (relays[i].currentWaterMode == LIGHT) ? "LIGHT" :
              (relays[i].currentWaterMode == MEDIUM) ? "MEDIUM" :
              (relays[i].currentWaterMode == HEAVY) ? "HEAVY" : "CUSTOM") + "\",";
          json += "\"env\":\"" + String((relays[i].env == INDOOR) ? "INDOOR" : "OUTDOOR") + "\",";
          json += "\"amount\":" + String(relays[i].amount) + "}";
      }
  }

  json += "],";

  // active sensors
  json += "\"sensors\":[";

  for (int i = 0; i < max_num_sensors; i++) {
      if (sensors[i].active) {
          if (i != 0) {
              json += ",";
          }

          json += "{\"id\":" + String(sensors[i].id) + ",";
          json += "\"pin\":" + String(sensors[i].pin) + ",";
          json += "\"type\":\"" + String((sensors[i].type == SOIL) ? "SOIL" : "DHT_SENSOR") + "\",";
          json += "\"relay\":" + String(sensors[i].relay) + "}";
      }
  }

  json += "]}";

  client.publish("irrigation/data", json.c_str());

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