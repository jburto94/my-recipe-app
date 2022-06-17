from flask import redirect, render_template, request, session
from functools import wraps

def login_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if session.get("user_id") is None:
      return redirect("/login", message="You must be logged in to view that")
    return f(*args, **kwargs)
  return decorated_function