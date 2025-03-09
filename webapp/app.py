from flask import Flask, render_template, redirect, request, url_for, session, g
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, close_db
from flask_session import Session
from functools import wraps
import requests

from forms import SensorForm, LocationForm, RegistrationForm, LoginForm

from openmeteopy import OpenMeteo
from openmeteopy.hourly import HourlyForecast
from openmeteopy.daily import DailyForecast
from openmeteopy.options import ForecastOptions
import pandas as pd

import time

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
    def __init__(self, id, username, password_hash):
        """ Initialize user object with id, username, and hash of password
        """
        self.id = id
        self.username = username
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    """User loader function"""
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        return User(user["id"], user["username"], user["password"])
    return None


# @app.before_request
# def load_logged_in_user():
#     g.user = session.get("username", None)


sensors = {1: {"moisture": 1, "temperature": 1, "humidity": 1, "pump": 1, "env": "Indoor", "mode": "Automatic"},
               2: {"moisture": 2, "temperature": 2, "humidity": 2, "pump": 2, "env": "Outdoor", "mode": "MANUAL LIGHT"}}

@app.route("/", methods = ["GET", "POST"])
@login_required
def index():
    location_form = LocationForm()
    
    # temp default location - Cork
    city = "Cork"
    country = "Ireland"
    latitude = 51.898
    longitude = -8.4706

    # retrieve city data from raspberry Pi and replace city

    location_form.location.default = city
    location_form.process()

    # get coordinates for the user input city
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

        return redirect(url_for("index", _anchor="weather"))

    # weather_data = get_weather_api(latitude, longitude)
    weather_current = get_current_weather(latitude, longitude)
    forecast_hourly, forecast_daily = get_forecast(latitude, longitude)

    forecast_hourly = forecast_hourly.iloc[:48] # 48h hourly forecast
    forecast_daily = forecast_daily.iloc[:5]    # 5 day forecast

    # weather code translation dict
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
    forecast_hourly["weathercode"] = forecast_hourly["weathercode"].replace(weather_codes)
    forecast_daily["weathercode"] = forecast_daily["weathercode"].replace(weather_codes)
    weather_current["weather_code"] = weather_codes[weather_current["weather_code"]]
    print(weather_current)

    # ensure time is not an index
    forecast_hourly.reset_index(inplace=True)
    forecast_daily.reset_index(inplace=True)

    # change format of time to more readable
    forecast_hourly['time'] = pd.to_datetime(forecast_hourly['time']).dt.strftime('%d %b %Y %H:%M')  
    forecast_daily['time'] = pd.to_datetime(forecast_daily['time']).dt.strftime('%d %b %Y')
 
    # readings = get_sensors() --> list of dict 
    # sample sensors 
    
    # create form for each sensor for updating the settings
    forms = {sensor_id: SensorForm(data=data) for sensor_id, data in sensors.items()}

    # # change to only if first time ?
    # for sensor_no, sensor in sensors.items():
    #     form = forms[sensor_no]
    #     form.pump.default = sensor["pump"]
    #     form.env.default = sensor["env"]
    #     form.mode.default = sensor["mode"]
    #     form.process()

    if request.method == "POST":
        # updating sensor settings
        if request.form.get("sensor") is not None:
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

                return redirect(url_for("index"))  # refresh the page 

    return render_template("index.html", weather=weather_current, sensors=sensors, hourly=forecast_hourly, 
                           daily=forecast_daily, forms=forms, city=city, country=country,
                           location_form=location_form)

@app.route("/register", methods = ["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        password_verify = form.password2.data
        # email = form.email.data

        if password != password_verify:
            form.password2.errors.append("Submitted passwords don't match!")
            return render_template("register.html", form=form)

        db = get_db()
        possible_clashing_user = db.execute("""SELECT * FROM users
                                               WHERE username = ?;""", (username,)).fetchone()
        # possible_clashing_email = db.execute("""SELECT * FROM users
        #                                         WHERE email = ?;""", (email,)).fetchone()
        if possible_clashing_user is not None:
            form.username.errors.append("Username is already taken!")
        # elif possible_clashing_email is not None:
        #     form.email.errors.append("Email is already registered!")
        # elif "@" not in email:
        #     form.email.errors.append("Enter a valid email address!")
        else:
            db.execute("""INSERT INTO users (username, password)
                          VALUES (?, ?);""",
                          (username, generate_password_hash(password)))
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
        user = db.execute("""SELECT * FROM users
                                      WHERE username = ?;""", (username,)).fetchone()
        
        if not user:     # !!!make into one
            form.username.errors.append("Unknown username!")
        elif not check_password_hash(user["password"], password):
            form.password.errors.append("Incorrect password!")
        else:   # login successful
            user_obj = User(user["id"], user["username"], user["password"])
            login_user(user_obj, remember=True)

            # session["username"] = username

            next_page = request.args.get("next")
            if not next_page:
                next_page = url_for("index")

            return redirect(next_page)
    return render_template("login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    # session.clear()
    return redirect(url_for("login"))

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/statistics")
def statistics():
    return render_template("statistics.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")

@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", error=error)


# def get_weather_api(latitude,longitude):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["temperature_2m", "precipitation", "wind_speed_10m"],
        "current": ["temperature_2m", "relative_humidity_2m"]
    }

    # responses = om.weather_api("https://api.open-meteo.com/v1/forecast", params=params)
    # weather = responses[0]["current_weather"]
    
    response = responses[0]
    # print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
    # print(f"Elevation {response.Elevation()} m asl")
    # print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
    # print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

    # Current values
    current = response.Current()
    current_variables = list(map(lambda i: current.Variables(i), range(0, current.VariablesLength())))
    current_temperature_2m = next(filter(lambda x: x.Variable() == Variable.temperature and x.Altitude() == 2, current_variables))
    current_relative_humidity_2m = next(filter(lambda x: x.Variable() == Variable.relative_humidity and x.Altitude() == 2, current_variables))

    # print(f"Current time {current.Time()}")
    # print(f"Current temperature_2m {current_temperature_2m.Value()}")
    # print(f"Current relative_humidity_2m {current_relative_humidity_2m.Value()}")

    return {
        "temperature": current_temperature_2m.Value(),
        "humidity": current_relative_humidity_2m.Value()
    }

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
    # https://github.com/m0rp43us/openmeteopy/blob/main/readme/WEATHER_FORECAST.md
    # https://github.com/m0rp43us/openmeteopy/blob/main/notebooks/tutorial.ipynb
    hourly = HourlyForecast()     
    hourly = hourly.temperature_2m() 
    hourly = hourly.precipitation()
    hourly = hourly.windspeed_10m()
    hourly = hourly.relativehumidity_2m()
    hourly = hourly.precipitation_probability()
    hourly = hourly.weathercode()

    daily = DailyForecast()
    daily = daily.temperature_2m_max()
    daily = daily.temperature_2m_min()
    daily = daily.precipitation_sum()

    daily = daily.weathercode()
    
    options = ForecastOptions(lat, long, forecast_days=1)
    mgr = OpenMeteo(options, hourly=hourly, daily=daily)
    meteo = mgr.get_pandas()

    return meteo

def get_readings():
    pass

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
