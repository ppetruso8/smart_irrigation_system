from flask import Flask, render_template, redirect, request, url_for, session, g
from database import get_db, close_db
from flask_session import Session
# from werkzeug.security import generate_password_hash, check_password_hash
# from forms import
from functools import wraps
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
    return render_template("index.html")

# @app.route("/register", methods = ["GET", "POST"])
# def register():
#     form = RegistrationForm()
#     if form.validate_on_submit():
#         user_id = form.user_id.data
#         password = form.password.data
#         email = form.email.data
#         db = get_db()
#         possible_clashing_user = db.execute("""SELECT * FROM users
#                                                WHERE user_id = ?;""", (user_id,)).fetchone()
#         possible_clashing_email = db.execute("""SELECT * FROM users
#                                                 WHERE email = ?;""", (email,)).fetchone()
#         if possible_clashing_user is not None:
#             form.user_id.errors.append("User id is already taken!")
#         elif possible_clashing_email is not None:
#             form.email.errors.append("Email is already registered!")
#         elif "@" not in email:
#             form.email.errors.append("Enter a valid email address!")
#         else:
#             db.execute("""INSERT INTO users (user_id, password, email)
#                           VALUES (?, ?, ?);""",
#                           (user_id, generate_password_hash(password), email))
#             db.commit()
#             return redirect(url_for("login"))
#     return render_template("register.html", form=form)

# @app.route("/login", methods = ["GET", "POST"])
# def login():
#     form = LoginForm()
#     if form.validate_on_submit():  
#         user_id = form.user_id.data
#         password = form.password.data
#         db = get_db()
#         matching_user = db.execute("""SELECT * FROM users
#                                       WHERE user_id = ?;""", (user_id,)).fetchone()
#         if matching_user is None:
#             form.user_id.errors.append("Unknown user id!")
#         elif not check_password_hash(matching_user["password"], password):
#             form.password.errors.append("Incorrect password!")
#         else:
#             session["user_id"] = user_id
#             next_page = request.args.get("next")
#             if not next_page:
#                 next_page = url_for("index")
#             return redirect(next_page)
#     return render_template("login.html", form=form)

# @app.route("/logout")
# def logout():
#     session.clear()
#     return redirect( url_for("index") )

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