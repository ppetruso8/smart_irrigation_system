# from email.policy import default
from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, PasswordField, RadioField, SelectField, TextAreaField, IntegerField, HiddenField
from wtforms.validators import InputRequired, EqualTo, Length

class SensorForm(FlaskForm):
    sensor = IntegerField()
    pump = IntegerField("Pump", validators=[InputRequired()])
    env = SelectField("Environment", choices=["Indoor", "Outdoor"])
    mode = SelectField("Watering Mode", choices=["Automatic", "Manual Light", "Manual Normal", "Manual Heavy"])
    submit = SubmitField("Update Settings")