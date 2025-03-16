# from email.policy import default
from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, PasswordField, SelectField, TextAreaField, IntegerField
from wtforms.validators import InputRequired, EqualTo, Length, NumberRange

class SensorForm(FlaskForm):
    sensor = IntegerField()
    env = SelectField("Environment:", choices=["Indoor", "Outdoor"])
    mode = SelectField("Watering Mode:", choices=["Automatic", "Light", "Normal", "Heavy"])
    submit = SubmitField("Update Settings")

class FertilizationForm(FlaskForm):
    fertilization_pump = IntegerField()
    amount = IntegerField("Amount (ml):", validators=[InputRequired(), NumberRange(10,250)])
    submit = SubmitField("Update Setting")

class LocationForm(FlaskForm):
    location = StringField("Current Location:", validators=[InputRequired()])
    submit = SubmitField("Update Location")

class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired(), Length(min=4, max=25)])
    email = StringField("Email", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=5)])
    password2 = PasswordField("Confirm Password:", 
        validators=[InputRequired(), EqualTo("password", message="Passwords must match!")])
    submit = SubmitField("Register")

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Login")

class PairingForm(FlaskForm):
    code = StringField("Pairing code:", validators=[InputRequired(), Length(min=6, max=6)])
    submit = SubmitField("Submit")

class UserDetailsForm(FlaskForm):
    email = StringField("Email address:")
    country = SelectField("Country:",
    choices= [
            "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", 
            "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", 
            "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", 
            "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", 
            "Chad", "Chile", "China", "Colombia", "Comoros", "Congo, Democratic Republic of the", "Congo, Republic of the", 
            "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czechia", "Denmark", "Djibouti", "Dominica", "Dominican Republic", 
            "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", 
            "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", 
            "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", 
            "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", 
            "Korea, North", "Korea, South", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", 
            "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", 
            "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", 
            "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", 
            "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", 
            "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", 
            "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", 
            "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", 
            "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Sudan", "Spain", 
            "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", 
            "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Türkiye", "Turkmenistan", 
            "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", 
            "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe", "Not Provided"
        ])

    confirm_password = PasswordField("Confirm password to save details:", validators=[InputRequired()])
    submit = SubmitField("Submit")

class ChangePasswordForm(FlaskForm):
    password = PasswordField("New password:")
    password2 = PasswordField("Confirm new password:", validators=[EqualTo("password", message="Passwords must match!")])
    confirm_password = PasswordField("Confirm password to save details:", validators=[InputRequired()])
    submit = SubmitField("Submit")