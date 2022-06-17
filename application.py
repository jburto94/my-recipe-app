from flask import Flask, render_template, request, session, redirect
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required
import requests
from tempfile import mkdtemp

import os
import re

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('API_KEY')
uri = os.getenv("DATABASE_URL")  # or other relevant config var
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
# rest of connection code using the connection string `uri`

app = Flask(__name__)

# Connect to DB
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# users table creation
class User(db.Model):
  __tablename__ = 'users'
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(30), unique=True)
  hashed_password = db.Column(db.String(3000))

  def __init__(self,username,hashed_password):
    self.username = username
    self.hashed_password = hashed_password


# users_recipes table creation
class UserRecipe(db.Model):
  __tablename__ = 'users_recipes'
  id = db.Column(db.Integer, primary_key=True)
  recipe_id = db.Column(db.Integer)
  user_id = db.Column(db.Integer)

  def __init__(self,recipe_id, user_id):
    self.recipe_id = recipe_id
    self.user_id = user_id

url = "https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com/"

headers = {
  'x-rapidapi-host': "spoonacular-recipe-food-nutrition-v1.p.rapidapi.com",
  'x-rapidapi-key': API_KEY,
  }

search = "recipes/search"
randomFind = "recipes/random"


# List random recipes and render search form
@app.route('/')
def search_page():
  querystring = { 'number': 30 }
  response = requests.request('GET', url + randomFind, headers=headers, params=querystring).json()
  return render_template('search.html', recipes=response['recipes'])


# Get list of recipes based on search query
@app.route('/recipes')
def get_recipes():
  querystring = {"number":request.args['quantity'], "query":request.args['recipes'], "diet":request.args['diet']}
  response = requests.request("GET", url + search, headers=headers, params=querystring).json()
  return render_template('recipes.html', recipes=response['results'])


# Get list of user's saved recipes
@app.route('/my-recipes')
@login_required
def my_recipes():
  # Get the recipe id of each of the user's saved recipes
  user_id = session["user_id"]
  user_recipes = UserRecipe.query.filter_by(user_id=user_id).all()
  saved_recipes = []
  for recipe in user_recipes:
    saved_recipes.append(recipe.recipe_id)
  # Call API for each recipe and add response to recipes list
  recipes = []
  for recipe_id in saved_recipes:
    recipe_info_endpoint = "recipes/{0}/information".format(recipe_id)
    response = requests.request("GET", url + recipe_info_endpoint, headers=headers).json()
    recipes.append(response)

  return render_template('my-recipes.html', recipes=recipes)


# Detailed recipe page
@app.route('/recipe')
def get_recipe():
  recipe_id = request.args['id']
  recipe_info_endpoint = "recipes/{0}/information".format(recipe_id)

  recipe_info = requests.request("GET", url + recipe_info_endpoint, headers=headers).json()
  recipe_headers = {
      'x-rapidapi-host': "spoonacular-recipe-food-nutrition-v1.p.rapidapi.com",
      'x-rapidapi-key': API_KEY,
      'accept': "text/html"
  }
  recipe_ingredients = recipe_info['extendedIngredients']

  if session.get("user_id"):
    recipe_id = recipe_info["id"]
    user_id = session["user_id"]
    user_recipe = UserRecipe.query.filter_by(user_id=user_id, recipe_id=recipe_id).first()
    if user_recipe:
      saved = True
    else:
      saved = False
    return render_template('recipe.html', recipe=recipe_info, ingredients=recipe_ingredients, saved=saved)

  return render_template('recipe.html', recipe=recipe_info, ingredients=recipe_ingredients)


# Register new user
@app.route("/register", methods=["GET", "POST"])
def register():
  # Forget any user_id
  session.clear()
  if request.method == "POST":
    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")
    user_exist = User.query.filter_by(username=username).first()
    # Ensure Username is no blank

    if not username:
      return render_template('register.html', message='Please enter a username')
    # Ensure username does not already exist
    elif user_exist:
      return render_template('register.html', message='Username already exists')
    # Check if password and confirmation are not blank
    if not password or not confirmation:
      return render_template('register.html', message='Please enter a password and confirmation')
    # Check if password and confirmation match
    elif password != confirmation:
      return render_template('register.html', message='Password does not match confirmation')
    # Create user into database
    new_user = User(username, generate_password_hash(password))
    db.session.add(new_user)
    db.session.commit()
    return redirect('/login')
  else:
    return render_template('register.html')

# Log in user
@app.route("/login", methods=["GET", "POST"])
def login():
  # User reached route via POST (as by submitting a form via POST)
  if request.method == "POST":
    # Query database for username
    username = request.form.get("username")
    password = request.form.get("password")
    user_exist = User.query.filter_by(username=username).first()
    # Ensure username exists and password is correct
    if not user_exist:
      return render_template('login.html', message='Invalid username')
    elif not check_password_hash(user_exist.hashed_password, password):
      return render_template('login.html', message="Invalid username/password")
    # Remember which user has logged in
    session["user_id"] = user_exist.id
    # Redirect user to home page
    return redirect("/")
  # User reached route via GET (as by clicking a link or via redirect)
  else:
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    # Forget any user_id
    session.clear()
    # Redirect user to login form
    return redirect("/")


@app.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():
  user = User.query.filter_by(id=session["user_id"]).first()
  if request.method == "POST":
    password = request.form.get("password")
    new_password = request.form.get("new-password")
    confirmation = request.form.get("confirmation")
    # Check if entered password matches current password
    if not check_password_hash(user.hashed_password, password):
      return render_template("reset-password.html", message="Current password incorrect")
    # Check if new password and confirmation match
    elif confirmation != new_password:
      return render_template("reset-password.html", message="New password does not match confirmation")
    # Update user's password
    else:
      user.hashed_password = generate_password_hash(new_password)
      db.session.commit()
      return redirect("/")
  else:
    return render_template("reset-password.html")


@app.route("/save-recipe", methods=["POST"])
@login_required
def save_recipe():
  recipe_id = request.form.get("save-recipe")
  user_id = session["user_id"]
  user_recipe = UserRecipe.query.filter_by(user_id=user_id, recipe_id=recipe_id).first()
  if not user_recipe:
    new_user_recipe = UserRecipe(recipe_id, user_id)
    db.session.add(new_user_recipe)
    db.session.commit()
    return redirect("/recipe?id=" + recipe_id)
  else:
    return redirect("/recipe?id=" + recipe_id)


@app.route("/remove-recipe", methods=["POST"])
@login_required
def remove_recipe():
  recipe_id = request.form.get("remove-recipe")
  user_id = session["user_id"]
  user_recipe = UserRecipe.query.filter_by(user_id=user_id, recipe_id=recipe_id).first()
  if user_recipe:
    db.session.delete(user_recipe)
    db.session.commit()
    return redirect("/recipe?id=" + recipe_id)
  else:
    return redirect("/recipe?id=" + recipe_id)

if __name__ == '__main__':
  app.run()