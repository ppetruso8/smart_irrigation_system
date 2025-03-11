from flask import Flask, render_template, redirect, request, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, close_db
from flask_session import Session
from functools import wraps
import requests

from forms import SensorForm, LocationForm, RegistrationForm, LoginForm, FertilizationForm, PairingForm, UserDetailsForm, ChangePasswordForm

from datetime import datetime

NODE_RED = "" 

app = Flask(__name__)
app.teardown_appcontext(close_db)      
app.config["SECRET_KEY"] = "my-secret-key"     
# app.config["SESSION_PERMANENT"] = False     
# app.config["SESSION_TYPE"] = "filesystem"   
# Session(app)

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
        self.has_node_red_permission = bool(has_node_red_permission)

@login_manager.user_loader
def load_user(user_id):
    """User loader function"""
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        return User(user["id"], user["username"], user["password"], user["email"], 
                    user["has_node_red_permission"], user["country"])
    return None

# @app.before_request
# def load_logged_in_user():
#     g.user = session.get("username", None)

sensors = {1: {"moisture": 1, "pump": 1, "env": "Indoor", "mode": "Automatic"},
               2: {"moisture": 2, "pump": 2, "env": "Outdoor", "mode": "MANUAL LIGHT"}}

dht_sensors = {1: {"temperature": 1, "humidity": 1}, 2: {"temperature": 2, "humidity": 2}}

fertilization_pumps = {1: {"amount": 50, "last": "2025-10-03 15:00"}, 2: {"amount": 60, "last": "2025-10-03 14:00"}}

@app.route("/", methods = ["GET", "POST"])
@login_required
def index():
    location_form = LocationForm()
    city = None
    # retrieve forecast location data from Node-Red
    # city, country, latitude, longitude = get_location()
    # country = current_user.country
    if not city:
        # default location - Cork
        city = "Cork"
        country = "Ireland"
        latitude = 51.898
        longitude = -8.4706

    location_form.location.default = city
    location_form.process()

    # get coordinates of user-submitted location
    if location_form.validate_on_submit():
        city = location_form.location.data
        lat, long, name, country = get_coordinates(city)

        if lat and long and name and country:
            latitude = float(lat)
            longitude = float(long)
            city = city
            country = country
        else: 
            print("Error updating city data")

        # send city data to raspberry pi
        send_command(f"SET: {city}, {latitude}, {longitude}") 

        return redirect(url_for("index", _anchor="weather"))

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
    # replace weather codes with actual strings
    forecast_hourly["weather_code"] = [weather_codes[code] for code in forecast_hourly["weather_code"]]
    forecast_daily["weather_code"] = [weather_codes[code] for code in forecast_daily["weather_code"]]
    weather_current["weather_code"] = weather_codes[weather_current["weather_code"]]

    # change format of time to more readable
    forecast_hourly["time"] = [datetime.strptime(time, "%Y-%m-%dT%H:%M").strftime("%d %b %Y %H:%M") for time in forecast_hourly["time"]]
    forecast_daily["time"] = [datetime.strptime(time, "%Y-%m-%d").strftime("%d %b %Y") for time in forecast_daily["time"]]

    print(forecast_daily)
    print(forecast_hourly)
 
    # data from node-red
    # sensors, dht_sensors = get_sensors()
    # fertilization_pumps = get_fertilization_pumps()
    
    # create form for each sensor for updating the settings
    forms = {sensor_id: SensorForm(data=data) for sensor_id, data in sensors.items()}
    fertilization_forms = {pump_id: FertilizationForm(data=data) for pump_id, data in fertilization_pumps.items()}

    # default form fill-in
    for sensor_no, sensor in sensors.items():
        form = forms[sensor_no]
        form.pump.default = sensor["pump"]
        form.env.default = sensor["env"]
        form.mode.default = sensor["mode"]
        form.process()

    for pump_no, pump in fertilization_pumps.items():
        form = fertilization_forms[pump_no]
        form.amount.default = pump["amount"]
        form.process()

    if request.method == "POST":
        # updating sensor settings
        if request.form.get("sensor"):
            sensor_no = int(request.form.get("sensor"))

            form = forms.get(sensor_no)

            if form.validate_on_submit():
                new_pump = form.pump.data
                new_env = form.env.data
                new_mode = form.mode.data

                # update Raspberry Pi
                print("Updating Raspberry Pi")
                sensors[sensor_no]["pump"] = new_pump
                sensors[sensor_no]["env"] = new_env
                sensors[sensor_no]["mode"] = new_mode

                forms[sensor_no] = SensorForm(data=sensors[sensor_no])

                return redirect(url_for("index"))
        # updating fertilization setting
        elif request.form.get("fertilization_pump"):
            pump_no = int(request.form.get("fertilization_pump"))

            form = fertilization_forms.get(pump_no)

            if form.validate_on_submit():
                new_amount = form.amount.data

                # update Raspberry Pi
                print("Updating Raspberry Pi")
                fertilization_pumps[pump_no]["amount"] = new_amount

                fertilization_pumps[pump_no] = FertilizationForm(data=fertilization_pumps[pump_no])

                return redirect(url_for("index"))  # refresh the page

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
        
        if not user:     # !!!make into one
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
    logout_user()
    return redirect(url_for("login"))

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    form = PairingForm()
    code = "123456"
    # code = get_pairing_code()
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?;", (current_user.id,)).fetchone()

    if form.validate_on_submit():
        user_code = form.code.data

        if user_code == code:
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

    if request.method == "POST":
        print("POST request received")

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
        user_id = current_user.id
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
def send_command():
    command = request.form.get("command")

    if not command:
        print("No command")
        return redirect(url_for("index"))
        
    print(command)

    if current_user.has_node_red_permission:
        if "READ" in command:
            msg = get_sensors()
        else:
            msg = send_node_red_command(command)
        
        if msg:
            print("Success")
        else:
            print(f"Failed to send command: {command}")
    else:
        print("You don't have permission to control the system.")
    return redirect(url_for("index"))
    
@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", error=error)

""" Weather API """
def get_current_weather(lat, long):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={long}&current=temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,precipitation_probability"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data["current"]
    else:
        print(f"Error retrieving the weather API data: {response.status_code}")

    return None

def get_forecast(lat, long):  
    url=f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={long}&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        
        # 48-hours hourly forecast
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

        return data["hourly"], data["daily"]
    else:
        print(f"Error retrieving the weather API data: {response.status_code}")

    return None

def get_coordinates(city):
    city = city.strip()
    city = city.replace(" ", "+")
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=10&language=en&format=json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        data = data["results"][0]
        return data["latitude"], data["longitude"], data["name"], data["country"]
    else:
        print(f"Error retrieving the weather API data: {response.status_code}")
    
    return None,None,None,None

""" Raspberry Pi communication """
def send_node_red_command(command):
    """ Send command to Node-Red using HTTP POST request
    """
    payload = {"command": command}
    print(f"COMMAND SENT: {command}")
    return None
    # response = requests.post(f"{NODE_RED}/control", json=payload)

    # if response.status_code == 200:
    #     print(response)
    #     return response.json()
    # else:
    #     print(f"Error sending command to Node-Red: {response.status_code}")
    # return None

def get_sensors():
    """ Retrieve sensor data from Node-Red using HTTP GET request
    """
    response = requests.get(f"{NODE_RED}/sensor-data")

    if response.status_code == 200:
        print(response)
        return response.json()
    else:
        print(f"Error fetching sensor data from Node-Red: {response.status_code}")

    # UPDATE DICTS
    return None

def get_location():
    """ Get selected location for forecast from Node-Red
    """
    response = requests.post(f"{NODE_RED}/location")

    if response.status_code == 200:
        print(response)
        return response.json()
    else:
        print(f"Error sending command to Node-Red: {response.status_code}")
    return None

def get_fertilization_pumps():
    """ Retrieve sensor data from Node-Red using HTTP GET request
    """
    response = requests.get(f"{NODE_RED}/fertilization")

    if response.status_code == 200:
        print(response)
        return response.json()
    else:
        print(f"Error fetching sensor data from Node-Red: {response.status_code}")
    return None

def get_pairing_code():
    """Obtain pairing code from Raspberry Pi
    """
    response = requests.get(f"{NODE_RED}/pair")

    if response.status_code == 200:
        print(response)
        return response.json()
    else:
        print(f"Error fetching sensor data from Node-Red: {response.status_code}")
    return None