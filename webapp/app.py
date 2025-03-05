from flask import Flask, render_template, redirect, request, url_for, session, g
from database import get_db, close_db
from flask_session import Session
import requests
# from werkzeug.security import generate_password_hash, check_password_hash
from forms import SensorForm
from functools import wraps

from openmeteopy import OpenMeteo
from openmeteopy.hourly import HourlyForecast
from openmeteopy.daily import DailyForecast
from openmeteopy.options import ForecastOptions
import pandas as pd

import time

app = Flask(__name__)
app.teardown_appcontext(close_db)      
app.config["SECRET_KEY"] = "my-secret-key"     
app.config["SESSION_PERMANENT"] = False     
app.config["SESSION_TYPE"] = "filesystem"   
Session(app)

# @app.before_request
# def load_logged_in_user():
#     g.user = session.get("user_id", None)

@app.route("/", methods = ["GET", "POST"])
def index():
    # https://pypi.org/project/openmeteo-requests/
    # API info MAKE CUSTOMIZABLE FROM DASHBOARD
    longitude = -8.4706
    latitude = 51.898
    
    # weather_data = get_weather_api(latitude, longitude)
    weather_current = get_current_weather(latitude, longitude)
    forecast_hourly, forecast_daily = get_forecast(latitude, longitude)

    # 48h hourly forecast
    forecast_hourly = forecast_hourly.iloc[:48]
    # 5 day forecast
    forecast_daily = forecast_daily.iloc[:5]

    # weather code translation 
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
    weather_current["weathercode"] = weather_codes[weather_current["weathercode"]]

    print(weather_current)
    # ensure time is not an index
    forecast_hourly.reset_index(inplace=True)
    forecast_daily.reset_index(inplace=True)

    # change format of time to more readable
    forecast_hourly['time'] = pd.to_datetime(forecast_hourly['time']).dt.strftime('%d %b %Y %H:%M')  
    forecast_daily['time'] = pd.to_datetime(forecast_daily['time']).dt.strftime('%d %b %Y')

    print(forecast_daily)
 
    # convert dataframe into HTML table
    # hourly_html = forecast_hourly.to_html(classes='table table-striped', border = 0)
    # daily_html = forecast_daily.to_html(classes='table table-striped', border = 0)

    # readings = get_sensors() --> list of dict 
    # sample sensor reading
    sensor = {"sensor_no": 1, "moisture": 1, "temperature": 1, "humidity": 1, "brightness": 1, "pump": 1, "env": "INDOOR", "mode": "Automatic"}
    sensor2 = {"sensor_no": 2, "moisture": 2, "temperature": 2, "humidity": 2, "brightness": 2, "pump": 2, "env": "OUTDOOR", "mode": "MANUAL LIGHT"}
    sensors = [sensor, sensor2]

    # create form for each sensor for updating the settings
    forms = {sensor["sensor_no"]: SensorForm(data=sensor) for sensor in sensors}

    if request.method == "POST":
        sensor_no = request.form.get("sensor")

        if sensor_no is not None:
            print(type(sensor_no))
            sensor_no = int(sensor_no)
        else:
            print("Error")

        form = forms.get(sensor_no)

        if form.validate_on_submit():
            new_pump = form.pump.data
            new_env = form.env.data
            new_mode = form.mode.data

            # Update Raspberry Pi
            print("Updating Raspberry Pi")
            sensor = sensors[sensor_no-1]
            sensor["pump"] = new_pump
            sensor["env"] = new_env
            sensor["mode"] = new_mode

            return redirect(url_for("index"))  # Refresh the page after submission

    return render_template("index.html", weather=weather_current, sensors=sensors, 
                           hourly=forecast_hourly, daily=forecast_daily, forms=forms)

# @app.route("/register", methods = ["GET", "POST"])
# def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user_id = form.user_id.data
        password = form.password.data
        email = form.email.data
        db = get_db()
        possible_clashing_user = db.execute("""SELECT * FROM users
                                               WHERE user_id = ?;""", (user_id,)).fetchone()
        possible_clashing_email = db.execute("""SELECT * FROM users
                                                WHERE email = ?;""", (email,)).fetchone()
        if possible_clashing_user is not None:
            form.user_id.errors.append("User id is already taken!")
        elif possible_clashing_email is not None:
            form.email.errors.append("Email is already registered!")
        elif "@" not in email:
            form.email.errors.append("Enter a valid email address!")
        else:
            db.execute("""INSERT INTO users (user_id, password, email)
                          VALUES (?, ?, ?);""",
                          (user_id, generate_password_hash(password), email))
            db.commit()
            return redirect(url_for("login"))
    return render_template("register.html", form=form)

# @app.route("/login", methods = ["GET", "POST"])
# def login():
    form = LoginForm()
    if form.validate_on_submit():  
        user_id = form.user_id.data
        password = form.password.data
        db = get_db()
        matching_user = db.execute("""SELECT * FROM users
                                      WHERE user_id = ?;""", (user_id,)).fetchone()
        if matching_user is None:
            form.user_id.errors.append("Unknown user id!")
        elif not check_password_hash(matching_user["password"], password):
            form.password.errors.append("Incorrect password!")
        else:
            session["user_id"] = user_id
            next_page = request.args.get("next")
            if not next_page:
                next_page = url_for("index")
            return redirect(next_page)
    return render_template("login.html", form=form)

# @app.route("/logout")
# def logout():
    session.clear()
    return redirect( url_for("index") )

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
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={long}&current_weather=true"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data["current_weather"]
    else:
        print(f"Error retrieving the weather API data: {response.status_code}")

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