import serial
import time

mositure_threshold = 500 # calibrate!

# open connection with Arduino
arduino = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
time.sleep(2)

# change arduino mode (IDLE, WATER, READ)
def change_mode(mode):
    arduino.write((mode + '\n').encode())
    print(f"Mode changed request sent to arduino: {mode}")

# read arduino response from serial
def read_arduino():
    while arduino.in_waiting:
        response = arduino.readline().decode().strip()
        print(f"Arduino response: {response}")
        return response
    return None

# working loop
# while True:
def main():
    change_mode("READ")
    time.sleep(2)

    moisture = None
    temperature = None
    humidity = None

    for i in range(3):
        response = read_arduino()
        if response:
            if response.startswith("SOIL"):
                moisture = int(response.split(":")[1])
            elif response.startswith("TEMP"):
                temperature = float(response.split(":")[1])
            elif response.startswith("HUM"):
                humidity = float(response.split(":")[1])

    # save reading
    with open("/home/pi/fyp/readings.csv", "a") as file:
        file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{moisture},{temperature},{humidity}\n")
    
    if moisture and moisture < mositure_threshold:
        while moisture < mositure_threshold:
            print("Watering plant.")
            change_mode("WATER")

            time.sleep(120) # wait to check again

            change_mode("READ")
            response = read_arduino()

            if response:
                if response.startswith("SOIL"):
                    moisture = int(response.split(":")[1])
            else:
                print("No response.")
                break

        # save current moisture level reading
        with open("/home/pi/fyp/readings.csv", "a") as file:
            file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{moisture},,\n")

    else:
        print("No watering needed.")

    

if __name__ == "__main__":
    main()