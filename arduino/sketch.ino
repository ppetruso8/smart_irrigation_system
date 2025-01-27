// Pin assignments for relays and sensors
const int relay = 2;
const int soilMoisture = A0;
const int moistureThreshold = 500;  // Calibrate!

// DHT Temperature Sensor
#include <DHT.h>
#define DHTPIN 6
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

void setup() {
  // Initialize serial communication for debugging
  Serial.begin(9600);
  
  // Relay pin as output
  pinMode(relay, OUTPUT);

  // Initialize relay to be OFF (pumps off)
  digitalWrite(relay, HIGH);  // HIGH means off for most relay modules

  // Initialize DHT sensor
  dht.begin();
}

void loop() {
  // Read soil moisture levels
  int moistureValue = analogRead(soilMoisture);

  // Print moisture values
  Serial.print("Soil: ");
  Serial.println(moistureValue);

  // If soil is dry, turn on the pump (need to switch)
  if (moistureValue < moistureThreshold) {
    // delay(150);
    // digitalWrite(relay, LOW);  // Turn ON pump 1
    // Pump pulses
    for (int i = 0; i < 5; i++) {
      digitalWrite(relay, LOW);   // Turn ON pump
      delay(200);      // Wait for ON duration
      digitalWrite(relay, HIGH); // Turn OFF pump
      delay(200);      // Wait for OFF duration
    }
  } else {
    digitalWrite(relay, HIGH); // Turn OFF pump 1
  }

  // Read temperature and humidity
 float humidity = dht.readHumidity();
 float temperature = dht.readTemperature();

  // Print temperature and humidity for debugging
  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" *C");
  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.println(" %");

  // Delay for taking readings
  delay(2000);
}
