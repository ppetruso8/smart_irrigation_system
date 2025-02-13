from flask import Flask, render_template, redirect, request, url_for, session, g
from database import get_db, close_db
from flask_session import Session
import requests
# from werkzeug.security import generate_password_hash, check_password_hash
# from forms import
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

@app.route("/")
def index():
    # https://pypi.org/project/openmeteo-requests/
    # API info MAKE CUSTOMIZABLE FROM DASHBOARD
    longitude = -8.4706
    latitude = 51.898

    # weather_data = get_weather_api(latitude, longitude)
    weather_current = get_current_weather(latitude, longitude)
    forecast_hourly, forecast_daily = get_forecast(latitude, longitude)
    
    forecast_hourly = forecast_hourly.iloc[:48]

    hourly_html = forecast_hourly.to_html(classes='table table-striped', border = 0)
    daily_html = forecast_daily.to_html(classes='table table-striped', border = 0)

    print(hourly_html)
    # sample reading
    reading = {"moisture": 1, "temperature": 1, "humidity": 1, "brightness": 1}

    return render_template("index.html", weather=weather_current, reading=reading, hourly=hourly_html, daily=daily_html)

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

@app.route("/logout")
def logout():
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