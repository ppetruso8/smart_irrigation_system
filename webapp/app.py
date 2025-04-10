from flask import Flask, render_template, redirect, request, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, close_db
from flask_session import Session
import requests

from forms import SensorForm, LocationForm, RegistrationForm, LoginForm, FertilizationForm, PairingForm, UserDetailsForm, ChangePasswordForm

from datetime import datetime, timedelta
import pandas as pd
import json, os

NODE_RED = "http://127.0.0.1:1880/"

DEFAULT_CODE = 123987

app = Flask(__name__)
app.teardown_appcontext(close_db)      
app.config["SECRET_KEY"] = "my-secret-key"     
app.config["SESSION_PERMANENT"] = False     
app.config["SESSION_TYPE"] = "filesystem"   
Session(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login" 

class User(UserMixin): 
    """ Class to represent user
    Inherits from UserMixin, which provides default implementations for all required properties and methods.
    """
    def __init__(self, id, username, email, country, password_hash, has_node_red_permission = 0):
        """ Initialize user object with id, username, and hash of password
        """
        self.id = id
        self.username = username
        self.email = email
        self.country = country
        self.password_hash = password_hash
        self.has_node_red_permission = has_node_red_permission

@login_manager.user_loader
def load_user(user_id):
    """User loader function"""
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        return User(user["id"], user["username"], user["email"], user["country"],
                    user["password"], user["has_node_red_permission"])
    return None


@app.route("/", methods = ["GET", "POST"])
@login_required
def index():
    # display message about pairing the device
    if current_user.has_node_red_permission == 0:
        flash("You don't have permission to control the system. Please pair the Raspberry Pi device in settings first.")

    location_form = LocationForm()

    # retrieve forecast location data from Node-Red
    city, country, latitude, longitude = get_location() 
    
    # check if location setting changed
    if "city" in session and (city != session["city"] or city.replace("+", " ") != session["city"]):
        session["last_weather_update"] = None
        session["last_cur_weather_update"] = None
    
    if city and "+" in city:
        city.replace("+", " ")
    
    # set default location - Cork
    if not city or "location" not in session:
        city = "Cork"
        country = "Ireland"
        latitude = 51.898
        longitude = -8.4706
        session["location"] = (city, country, latitude, longitude)
        session["last_weather_update"] = None
        session["last_cur_weather_update"] = None

    # user changing location
    if location_form.validate_on_submit():
        city = location_form.location.data
        lat, long, name, country = get_coordinates(city)

        if lat and long and name and country:
            latitude = float(lat)
            longitude = float(long)
            city = city
            country = country

            session["location"] = (city, country, latitude, longitude)
            session["last_weather_update"] = None
            session["last_cur_weather_update"] = None

            # send location data to Node-Red
            send_command(f"SET_LOC {city.replace(' ', '+')} {country} {latitude} {longitude}") 
        else: 
            flash("Error updating location.")

        return redirect(url_for("index", _anchor="weather"))
    
    # prefill the form
    location_form.location.default = city
    location_form.process()

    weather_current = get_current_weather(latitude, longitude)
    forecast_hourly, forecast_daily = get_forecast(latitude, longitude)

    # weather code translation dictionary
    weather_codes = {0: "Clear Sky", 1: "Mainly Clear Sky", 2: "Partly Cloudy", 3: "Cloudy",
                     45: "Fog", 48: "Depositing Rime Fog", 51: "Light Drizzle", 
                     53: "Moderate Drizzle", 55: "Dense Drizzle", 56: "Light Freezing Drizzle",
                     57: "Dense Freezing Drizzle", 61: "Slight Rain", 63: "Moderate Rain",
                     65: "Heavy Rain", 66: "Light Freezing Rain", 67: "Heavy Freezing Rain",
                     71: "Slight Snowfall", 73: "Moderate Snowfall", 75: "Heavy Snowfall",
                     77: "Snow Grains", 80: "Slight Rain Showers", 81: "Moderate Rain Showers",
                     82: "Violent Rain Showers", 85: "Slight Snow Showers", 86: "Heavy Snow Showers",
                     95: "Thunderstorms", 96: "Thunderstorm with Slight Hail", 
                     99: "Thunderstorm with Heavy Hail"}
    
    try:
        # replace weather codes with actual strings
        forecast_hourly["weather_code"] = [weather_codes[code] for code in forecast_hourly["weather_code"]]
        forecast_daily["weather_code"] = [weather_codes[code] for code in forecast_daily["weather_code"]]
        weather_current["weather_code"] = weather_codes[weather_current["weather_code"]]
        # change format of time to more readable
        forecast_hourly["time"] = [datetime.strptime(time, "%Y-%m-%dT%H:%M").strftime("%d %b %Y %H:%M") for time in forecast_hourly["time"]]
        forecast_daily["time"] = [datetime.strptime(time, "%Y-%m-%d").strftime("%d %b %Y") for time in forecast_daily["time"]]
    except:
        pass

    # data from node-red
    sensors, dht_sensors, water_pumps, fertilization_pumps = get_data()
    
    # create form for each sensor for updating the settings
    forms = {sensor_id: SensorForm(data=data) for sensor_id, data in sensors.items()}
    fertilization_forms = {pump_id: FertilizationForm(data=data) for pump_id, data in fertilization_pumps.items()}

    # prefill sensor forms with data
    for sensor_id, sensor in sensors.items():
        form = forms[sensor_id]
        form.env.default = sensor["env"].lower().capitalize()
        form.mode.default = sensor["mode"].lower().capitalize()

        if sensor["mode"].upper() == "CUSTOM":
            pump_id = sensor["pump"]
            form.custom_amount.default = session["pumps_water"][pump_id]["amount"]
            
        form.process()
      
    # prefill fertilization forms with data
    for pump_no, pump in fertilization_pumps.items():
        form = fertilization_forms[pump_no]
        form.amount.default = pump["amount"]
        form.process()

    if request.method == "POST":
        # updating sensor settings
        if request.form.get("sensor"):
            sensor_id = int(request.form.get("sensor"))

            form = SensorForm(request.form)

            if form.validate_on_submit():
                new_env = form.env.data
                new_mode = form.mode.data

                pump_id = session["sensors_soil"][sensor_id]["pump"]

                # update session and Node-Red
                session["sensors_soil"][sensor_id]["env"] = new_env
                session["sensors_soil"][sensor_id]["mode"] = new_mode

                if new_mode == "Automatic":
                    new_mode = "AUTO"

                send_command(f"SET_ENV {pump_id} {new_env.upper()}")

                if new_mode == "Custom":
                    custom_amount = form.custom_amount.data

                    if custom_amount:
                        # validate input type
                        try:
                            custom_amount = int(custom_amount)
                        except Exception as e:
                            form.custom_amount.errors.append("Custom amount must be a number.")
                            return render_template("index.html", weather=weather_current, sensors=sensors, hourly=forecast_hourly, 
                                daily=forecast_daily, forms=forms, city=city, country=country,
                                location_form=location_form, dht_sensors=dht_sensors, pumps=fertilization_pumps,
                                pump_forms=fertilization_forms, zip=zip)
                        
                        # validate amount
                        if custom_amount < 10 and custom_amount > 1000:
                            form.custom_amount.errors.append("Custom amount must be between 10ml and 1000ml.")
                            return render_template("index.html", weather=weather_current, sensors=sensors, hourly=forecast_hourly, 
                                daily=forecast_daily, forms=forms, city=city, country=country,
                                location_form=location_form, dht_sensors=dht_sensors, pumps=fertilization_pumps,
                                pump_forms=fertilization_forms, zip=zip)

                        session["pumps_water"][pump_id]["amount"] = custom_amount
                        send_command(f"CHMOD {pump_id} CUSTOM {custom_amount}")
                else:
                    send_command(f"CHMOD {pump_id} {new_mode.upper()}")

                forms[sensor_id] = SensorForm(data=session["sensors_soil"][sensor_id])

                return redirect(url_for("index"))
            else:
                flash(f"There was a problem while updating data: {form.errors}")
        
        # updating fertilization setting
        elif request.form.get("fertilization_pump"):
            pump_no = int(request.form.get("fertilization_pump"))
            form = FertilizationForm(request.form)

            if request.form.get("amount"):
                form.amount.data = int(request.form.get("amount"))

            if form.validate_on_submit():
                new_amount = int(form.amount.data)

                # update session and Node-Red
                print("Updating Raspberry Pi")
                session["pumps_fert"][pump_no]["amount"] = new_amount
                send_command(f"SET_FERT_AMOUNT {pump_no} {new_amount}")

                session["pumps_fert"][pump_no] = FertilizationForm(data=session["pumps_fert"][pump_no])

                return redirect(url_for("index"))
            else:
                flash(f"There was a problem while updating data: {form.errors}")

    return render_template("index.html", weather=weather_current, sensors=sensors, hourly=forecast_hourly, 
                           daily=forecast_daily, forms=forms, city=city, country=country,
                           location_form=location_form, dht_sensors=dht_sensors, pumps=fertilization_pumps,
                           pump_forms=fertilization_forms, zip=zip)

@app.route("/register", methods = ["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        password_verify = form.password2.data

        if password != password_verify:
            form.password2.errors.append("Submitted passwords don't match!")
            return render_template("register.html", form=form)

        db = get_db()
        possible_clashing_user = db.execute("SELECT * FROM users WHERE username = ?;", (username,)).fetchone()
        possible_clashing_email = db.execute("SELECT * FROM users WHERE email = ?;", (email,)).fetchone()

        if possible_clashing_user is not None:
            form.username.errors.append("Username is already taken!")
        elif possible_clashing_email is not None:
            form.email.errors.append("Email is already registered!")
        elif "@" not in email:
            form.email.errors.append("Enter a valid email address!")
        else:
            db.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?);",
                        (username, generate_password_hash(password), email))
            db.commit()
            return redirect(url_for("login"))
    return render_template("register.html", form=form)

@app.route("/login", methods = ["GET", "POST"])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():  
        username = form.username.data
        password = form.password.data

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?;", (username,)).fetchone()
        
        if not user:
            form.password.errors.append("Incorrect information!")
        elif not check_password_hash(user["password"], password):
            form.password.errors.append("Incorrect information!")
        else:   # login successful
            user_obj = User(user["id"], user["username"], user["email"], user["country"], user["password"], user["has_node_red_permission"])
            login_user(user_obj, remember=True)

            next_page = request.args.get("next")
            if not next_page:
                next_page = url_for("index")

            return redirect(next_page)
    return render_template("login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    return redirect(url_for("login"))

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    global DEFAULT_CODE

    form = PairingForm()
    code = int(get_pairing_code())

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?;", (current_user.id,)).fetchone()

    if form.validate_on_submit():
        user_code = int(form.code.data)
        if user_code == code or (user_code == DEFAULT_CODE and not is_default_code_used()):
            if is_default_code_used() == False:
                set_default_code_used(True)
            
            db = get_db()
            db.execute("UPDATE users SET has_node_red_permission = 1 where id = ?", (current_user.id,))
            db.commit()
            return redirect(url_for("settings"))
        else:
            form.code.errors.append("Invalid pairing code")

    return render_template("settings.html", form=form, user=user, current_user=current_user)

@app.route("/unpair", methods = ["GET", "POST"])
@login_required
def unpair():
    db = get_db()
    db.execute("UPDATE users SET has_node_red_permission = 0 where id = ?", (current_user.id,))
    db.commit()
    current_user.has_node_red_permission = 0
    return redirect(url_for("settings"))
    

@app.route("/edit_account",  methods = ["GET", "POST"])
@login_required
def edit_account():
    form = UserDetailsForm()

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?;", (current_user.id,)).fetchone()

    if request.method == "GET":
        form.email.default = user["email"]
        form.country.default = user["country"]
        form.process()  

    if form.validate_on_submit():
        email = form.email.data
        country = form.country.data
        confirm_password = form.confirm_password.data

        if check_password_hash(user["password"], confirm_password):
            if len(email) != 0 and email != user["email"]:
                possible_clashing_email = db.execute("SELECT * FROM users WHERE email = ?;", (email,)).fetchone()
                if possible_clashing_email is not None:
                    form.email.errors.append("Email is already registered!")
                    return render_template("edit_account.html", form=form)
                elif "@" not in email:
                    form.email.errors.append("Enter a valid email address!")
                    return render_template("edit_account.html", form=form)
                else:
                    db.execute("UPDATE users SET email = ? WHERE id = ?;", (email, current_user.id))
                    db.commit()
                    current_user.email = email

            if country != user["country"]:
                db.execute("UPDATE users SET country = ? WHERE id = ?;", (country, current_user.id))
                db.commit()
                current_user.country = country
            return redirect(url_for("settings"))
        else:
            form.confirm_password.errors.append("Incorrect password!")
    return render_template("edit_account.html", form=form)

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    message = ""
    if form.validate_on_submit():
        new_password = form.password.data
        confirm_password = form.confirm_password.data

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?;", (current_user.id,)).fetchone()

        if check_password_hash(user["password"], confirm_password):
            if len(new_password) != 0:
                if check_password_hash(user["password"], new_password):
                    form.password2.errors.append("New password must be different from the current password.")
                    return render_template("change_password.html", form=form)
                else:
                    new_password = generate_password_hash(new_password)
                    db.execute("""UPDATE users
                                  SET password = ?
                                  WHERE id = ?;""", (new_password, current_user.id))
                    db.commit()
                    current_user.password = new_password
                    message = "Your password was successfully changed."
        else:
            form.confirm_password.errors.append("Incorrect password!")
    return render_template("change_password.html", form=form, message=message)

@app.route("/statistics")
@login_required
def statistics():
    return render_template("statistics.html")

@app.route("/send_command", methods=["POST"])
@login_required
def send_command(command = None):
    if not command:
        command = request.form.get("command")

    print(f"Command to be sent: {command}")

    if not command:
        flash("Error obtaining command.")
        return redirect(url_for("index"))   

    if current_user.has_node_red_permission == 1:
        if "GET_ALL" in command:
            send_node_red_command("GET_ALL")
            msg = get_data()
            return redirect(url_for("index"))

        elif "WATER" in command:
            sensor = int(command.split()[1])
            pump = session["sensors_soil"][sensor]["pump"]
            command = f"WATER {pump} {sensor}"

        elif "FERTILIZE" in command:
            pump = int(command.split()[1])
            command = f"FERTILIZE {pump}"

        msg = send_node_red_command(command)

        if msg:
            print("Command sent successfully.")
        else:
            flash(f"Failed to send command: {command}")
    else:
        flash("You don't have permission to control the system. Please pair the Raspberry Pi device in settings first.")
    return redirect(url_for("index"))

@app.route("/stats_data")
def stats_data():
    data = pd.read_csv("../readings.csv")
    data = data.dropna()
    data["timestamp"] = pd.to_datetime(data["timestamp"], format="%d/%m/%Y %H:%M")
    
    # filter latest 10 days
    latest = data["timestamp"].max()
    start = latest - pd.Timedelta(days = 10)
    data = data[data["timestamp"] >= start]
    
    # prepare data for AnyChart
    data["timestamp"] = data["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    data_dict = data.to_dict(orient="records")
    
    # average soil moisture per sensor
    avg_moisture = data.groupby([data["timestamp"].str[:10], "sensor"])
    avg_moisture = avg_moisture["soil_moisture"].mean().reset_index()
    avg_moisture = avg_moisture.to_dict(orient="records")
    
    # total watering
    watering = data["watering_amount_ml"].sum()

    return jsonify({
        "data": data_dict,
        "avg_moisture": avg_moisture,
        "watering": f"{watering}"
    })

@app.route("/set_fert_schedule", methods=["POST"])
def set_fert_schedule():
    pump_id = request.form.get("pump_id")
    interval = int(request.form.get("interval"))

    if interval > 0:
        command = f"SET_SCHEDULE {pump_id} {interval}"
        send_command(command)
    
    return redirect(url_for("index"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", error=error)

""" Weather API """
def get_current_weather(lat, long):
    # use cached data if request made within 30 minutes from last request
    if "last_cur_weather_update" in session and session["last_cur_weather_update"]:
        last_update = datetime.strptime(session["last_cur_weather_update"], "%Y-%m-%dT%H:%M:%S")
        if datetime.now() - last_update < timedelta(hours=1):
            return session["cur_weather"]

    # Weather information is provided by https://open-meteo.com, (CC BY 4.0) https://creativecommons.org/licenses/by/4.0/, with changes to output format
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={long}&current=temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,precipitation_probability"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        if response.status_code == 200:
            data = response.json()
            session["cur_weather"] = data["current"]
            session["last_cur_weather_update"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            return data["current"]
           
    except Exception as e:
        flash(f"Weather API error: {e}")

    except requests.exceptions.RequestException as e:
        if response and response.status_code != 200:
            flash(f"Error retrieving the weather data: {response.status_code}")
    
    return None

def get_forecast(lat, long):
    # use cached data if request made within 30 minutes from last request
    if "last_weather_update" in session and session["last_weather_update"]:
        last_update = datetime.strptime(session["last_weather_update"], "%Y-%m-%dT%H:%M:%S")
        if datetime.now() - last_update < timedelta(hours=1):
            return session["weather_hourly"], session["weather_daily"]  

    # Weather information is provided by https://open-meteo.com, (CC BY 4.0) https://creativecommons.org/licenses/by/4.0/, with changes to output format 
    url=f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={long}&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        if response.status_code == 200:
            data = response.json()
            
            # 2-day hourly forecast
            data["hourly"]["time"] = data["hourly"]["time"][:48]
            data["hourly"]["temperature_2m"] = data["hourly"]["temperature_2m"][:48]
            data["hourly"]["relative_humidity_2m"] = data["hourly"]["relative_humidity_2m"][:48]
            data["hourly"]["precipitation_probability"] = data["hourly"]["precipitation_probability"][:48]
            data["hourly"]["precipitation"] = data["hourly"]["precipitation"][:48]
            data["hourly"]["weather_code"] = data["hourly"]["weather_code"][:48]

            # 5-day daily forecast
            data["daily"]["time"] = data["daily"]["time"][:5]
            data["daily"]["weather_code"] = data["daily"]["weather_code"][:5]
            data["daily"]["temperature_2m_max"] = data["daily"]["temperature_2m_max"][:5]
            data["daily"]["temperature_2m_min"] = data["daily"]["temperature_2m_min"][:5]
            data["daily"]["precipitation_probability_max"] = data["daily"]["precipitation_probability_max"][:5]
            data["daily"]["precipitation_sum"] = data["daily"]["precipitation_sum"][:5]

            session["weather_hourly"] = data["hourly"]
            session["weather_daily"] = data["daily"]
            session["last_weather_update"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            return data["hourly"], data["daily"]
        
    except requests.exceptions.RequestException as e:
        if response and response.status_code != 200:
            flash(f"Error retrieving the weather API data: {response.status_code}")

    return None, None

def get_coordinates(city):
    city = city.strip()
    city = city.replace(" ", "+")

    # Location data is provided by https://open-meteo.com, (CC BY 4.0) https://creativecommons.org/licenses/by/4.0/, with changes to output format
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=10&language=en&format=json"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        if response.status_code == 200:
            data = response.json()
            data = data["results"][0]
            return data["latitude"], data["longitude"], data["name"], data["country"]
        else:
            flash(f"Error retrieving the location data from API data: {response.status_code}")
    
    except requests.exceptions.RequestException as e:
        if response and response.status_code != 200:
            flash(f"Error retrieving the location data from API: {response.status_code}")
    
    return None,None,None,None

""" Raspberry Pi communication """
def send_node_red_command(command):
    """ Send command to Node-Red using HTTP POST request
    """
    payload = {"command": command}
    response = None

    try:
        response = requests.post(f"{NODE_RED}control", json=payload)
        if response.status_code == 200:
            return "Success"
    except Exception as e:
        if response and response.status_code == 200:
            return "Success"
        else:
            print(f"Error sending command to Node-Red: {response.status_code}")
            return None

def get_data():
    """ Retrieve sensor data from Node-Red using HTTP GET request
    """
    response = None

    try:
        response = requests.get(f"{NODE_RED}data")

        if response.status_code == 200:
            data = response.json()

            sensors_soil = {}
            sensors_dht = {}
            pumps_water = {}
            pumps_fert = {}

            next_fert = data.get("fertSchedule", {})
            last_fert = data.get("fert", {})
            sensor_mapping = data.get("mappings", {})

            # extract all pumps
            pump_data = {pump["id"]: pump for pump in data.get("pumps") if pump.get("active") == 1}

            # categorise sensors
            for sensor in data.get("sensors"):
                if sensor.get("active") == 1:
                    if sensor["type"] == "SOIL":
                        pump = pump_data.get(sensor["pump"]) 
                        dht_mapping = sensor_mapping.get(str(sensor["id"]), "No Data")
                        
                        sensors_soil[sensor["id"]] = {
                            "moisture": sensor["moisture"],
                            "pump": sensor["pump"],
                            "env": pump["env"],
                            "mode": pump["currentWaterMode"],
                            "dht": dht_mapping
                        }
                    elif sensor["type"] == "DHT_SENSOR":
                        sensors_dht[sensor["id"]] = {
                            "temperature": sensor["temperature"],
                            "humidity": sensor["humidity"]
                        }

            # categorise pumps
            for pump_id, pump in pump_data.items():
                if pump["type"] == "WATERING":
                    pumps_water[pump_id] = {
                        "type": pump["type"],
                        "mode": pump["currentWaterMode"],
                        "amount": pump["amount"],
                        "env": pump["env"] 
                    }
                elif pump["type"] == "FERTILIZATION":             
                    last = None
                    next = None

                    if last_fert != {}:
                        last = last_fert.get(str(pump_id), {}).get("timestamp", "No data")
                    
                    if next_fert != {}:
                        next = next_fert.get(str(pump_id)).get("next", None)

                        if next:
                            next = datetime.strptime(next, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%d/%m/%Y")

                    pumps_fert[pump_id] = {
                        "amount": pump["amount"],
                        "last": last,
                        "env": pump["env"],
                        "next": next
                    }

            session["sensors_soil"] = sensors_soil
            session["sensors_dht"] = sensors_dht
            session["pumps_water"] = pumps_water
            session["pumps_fert"] = pumps_fert

            return sensors_soil, sensors_dht, pumps_water, pumps_fert
    except Exception as e:
        if response and response.status_code == 200:
            return "Success"
        elif response and response.status_code != 200:
            flash(f"Error fetching sensor data from Node-Red: {response.status_code}")
            return {}, {}, {}, {}
        else:
            flash(f"Error fetching sensor data from Node-Red: {e}")
            return {}, {}, {}, {}

def get_location():
    """ Get selected location for forecast from Node-Red
    """
    response = None
    try:
        response = requests.get(f"{NODE_RED}location")

        if response.status_code == 200:
            data = response.json()
            city = data.get("city")
            country = data.get("country")
            latitude = data.get("latitude")
            longitude = data.get("longitude")

            session["city"] = city

            return city, country, latitude, longitude
        
        elif response.status_code == 404:
            print("No location set in Node-Red. Location set to default - Cork")
            return None, None, None, None
        
    except Exception as e:
        if response and response.status_code == 200:
            return "Success"
        elif response and response.status_code != 200:
            flash(f"Failed to retrieve location from Node-RED: {response.status_code}")
            return None, None, None, None
        else:
            flash(f"Failed to retrieve location from Node-RED: {e}")
            return None, None, None, None

def get_pairing_code():
    """Obtain pairing code from Raspberry Pi
    """
    response = None
    
    try:
        response = requests.get(f"{NODE_RED}pair")

        if response.status_code == 200:
            data = response.json()
            code = data.get("code", 000000)
            return code
    except Exception as e:
        if response and response.status_code != 200:
            flash(f"Error fetching pairing code from Node-Red: {response.status_code}")
            return None
        else:
            flash(f"Error fetching pairing code from Node-Red: {e}")
            return None

def is_default_code_used():
    """Read file containing usage status of default code used for pairing the Raspberry Pi device
    """
    with open("../device_pairing.json", "r") as f:
        data = json.load(f)

    return data.get("default_used", False)

def set_default_code_used(used):
    """Set the usage status of default code used for pairing the Raspberry Pi device as True
    """
    with open("../device_pairing.json", "w") as f:
        json.dump({"default_used": True}, f)
