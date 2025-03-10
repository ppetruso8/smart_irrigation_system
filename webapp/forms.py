# from email.policy import default
from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, PasswordField, SelectField, TextAreaField, IntegerField
from wtforms.validators import InputRequired, EqualTo, Length, NumberRange

class SensorForm(FlaskForm):
    sensor = IntegerField()
    pump = IntegerField("Pump:", validators=[InputRequired()])
    env = SelectField("Environment:", choices=["Indoor", "Outdoor"])
    mode = SelectField("Watering Mode:", choices=["Automatic", "Manual Light", "Manual Normal", "Manual Heavy"])
    submit = SubmitField("Update Settings")

class FertilizationForm(FlaskForm):
    fertilization_pump = IntegerField()
    amount = IntegerField("Amount (mm):", validators=[InputRequired(), NumberRange(10,250)])
    submit = SubmitField("Fertilize")

class LocationForm(FlaskForm):
    location = StringField("Current Location:", validators=[InputRequired()])
    submit = SubmitField("Update Location")

class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired(), Length(min=4, max=25)])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=5)])
    password2 = PasswordField("Confirm Password:", 
        validators=[InputRequired(), EqualTo("password", message="Passwords must match!")])
    submit = SubmitField("Register")

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Login")